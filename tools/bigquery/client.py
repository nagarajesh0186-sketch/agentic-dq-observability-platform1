"""Async BigQuery client wrapper with retry, logging, and connection management."""

from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import structlog
from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from configs.settings import get_settings

logger = structlog.get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="bq-worker")
_client_instance: Optional[BigQueryClient] = None


def _retryable_gcp_error(exc: BaseException) -> bool:
    retryable = (
        gcp_exceptions.ServiceUnavailable,
        gcp_exceptions.InternalServerError,
        gcp_exceptions.TooManyRequests,
        gcp_exceptions.DeadlineExceeded,
    )
    return isinstance(exc, retryable)


class BigQueryClient:
    """Thread-safe async wrapper around the synchronous BigQuery client."""

    def __init__(self, project_id: Optional[str] = None) -> None:
        settings = get_settings()
        self._project_id = project_id or settings.gcp.project_id
        self._client: Optional[bigquery.Client] = None  # lazy — avoids auth at import time
        self._log = logger.bind(project=self._project_id)

    def _get_client(self) -> bigquery.Client:
        if self._client is None:
            self._client = bigquery.Client(project=self._project_id)
        return self._client

    @property
    def project_id(self) -> str:
        return self._project_id

    async def _run_sync(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, functools.partial(fn, *args, **kwargs))

    @retry(
        retry=retry_if_exception_type((
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.InternalServerError,
            gcp_exceptions.TooManyRequests,
            gcp_exceptions.DeadlineExceeded,
        )),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def execute_query(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
        timeout: float = 300.0,
    ) -> list[dict[str, Any]]:
        """Execute a parameterized query and return rows as dicts."""
        bq_params: list[ScalarQueryParameter] = []
        if params:
            for name, value in params.items():
                bq_type = self._infer_bq_type(value)
                bq_params.append(ScalarQueryParameter(name, bq_type, value))

        job_config = QueryJobConfig(query_parameters=bq_params)

        self._log.info("executing_query", sql_preview=sql[:120])

        def _run() -> list[dict[str, Any]]:
            job = self._get_client().query(sql, job_config=job_config, timeout=timeout)
            result = job.result(timeout=timeout)
            return [dict(row) for row in result]

        rows = await self._run_sync(_run)
        self._log.info("query_complete", row_count=len(rows))
        return rows

    async def execute_dml(
        self, sql: str, params: Optional[dict[str, Any]] = None, timeout: float = 300.0
    ) -> int:
        """Execute a parameterized DML statement and return rows affected."""
        bq_params: list[ScalarQueryParameter] = []
        if params:
            for name, value in params.items():
                bq_params.append(ScalarQueryParameter(name, self._infer_bq_type(value), value))

        job_config = QueryJobConfig(query_parameters=bq_params)

        self._log.info("executing_dml", sql_preview=sql[:120])

        def _run() -> int:
            job = self._get_client().query(sql, job_config=job_config, timeout=timeout)
            job.result(timeout=timeout)
            return job.num_dml_affected_rows or 0

        rows_affected = await self._run_sync(_run)
        self._log.info("dml_complete", rows_affected=rows_affected)
        return rows_affected

    async def execute_ddl(self, sql: str, timeout: float = 300.0) -> None:
        """Execute a DDL statement (CREATE, DROP, ALTER, CREATE PROCEDURE, etc.).

        Unlike execute_dml, this uses a plain QueryJobConfig with no
        query_parameters — BigQuery rejects parameterized DDL.
        """
        self._log.info("executing_ddl", sql_preview=sql[:120])

        def _run() -> None:
            job = self._get_client().query(sql, job_config=QueryJobConfig(), timeout=timeout)
            job.result(timeout=timeout)

        await self._run_sync(_run)
        self._log.info("ddl_complete")

    async def insert_rows(
        self, table_id: str, rows: list[dict[str, Any]], skip_invalid: bool = False
    ) -> None:
        """Streaming insert rows into a BigQuery table."""
        if not rows:
            return

        self._log.info("inserting_rows", table=table_id, count=len(rows))

        def _run() -> list[dict[str, Any]]:
            table = self._get_client().get_table(table_id)
            errors = self._get_client().insert_rows_json(table, rows, skip_invalid_rows=skip_invalid)
            return errors

        errors = await self._run_sync(_run)
        if errors:
            raise RuntimeError(f"BigQuery streaming insert errors for {table_id}: {errors}")

        self._log.info("insert_complete", table=table_id)

    async def table_exists(self, project: str, dataset: str, table: str) -> bool:
        """Return True if the table exists."""
        full_id = f"{project}.{dataset}.{table}"
        try:
            await self._run_sync(self._get_client().get_table, full_id)
            return True
        except gcp_exceptions.NotFound:
            return False

    async def create_table_if_not_exists(
        self,
        table_id: str,
        schema: list[bigquery.SchemaField],
        partition_field: Optional[str] = None,
        clustering_fields: Optional[list[str]] = None,
        time_partitioning_type: str = "DAY",
    ) -> None:
        """Create a BigQuery table with the given schema if it does not already exist."""
        table = bigquery.Table(table_id, schema=schema)

        if partition_field:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field=partition_field,
            )
        if clustering_fields:
            table.clustering_fields = clustering_fields

        def _run() -> None:
            self._get_client().create_table(table, exists_ok=True)

        await self._run_sync(_run)
        self._log.info("table_ensured", table=table_id)

    async def get_table_row_count(self, table_id: str) -> int:
        """Return the approximate row count for a table."""
        try:
            table = await self._run_sync(self._get_client().get_table, table_id)
            return table.num_rows or 0
        except gcp_exceptions.NotFound:
            return 0

    async def dry_run_query(self, sql: str) -> dict[str, Any]:
        """Perform a dry run to estimate bytes processed and validate SQL."""
        job_config = QueryJobConfig(dry_run=True, use_query_cache=False)

        def _run() -> dict[str, Any]:
            job = self._get_client().query(sql, job_config=job_config)
            return {
                "valid": True,
                "bytes_processed": job.total_bytes_processed,
                "estimated_cost_usd": (job.total_bytes_processed or 0) / 1e12 * 6.25,
            }

        try:
            return await self._run_sync(_run)
        except gcp_exceptions.BadRequest as exc:
            return {"valid": False, "error": str(exc), "bytes_processed": 0}

    @staticmethod
    def _infer_bq_type(value: Any) -> str:
        if isinstance(value, bool):
            return "BOOL"
        if isinstance(value, int):
            return "INT64"
        if isinstance(value, float):
            return "FLOAT64"
        return "STRING"

    async def close(self) -> None:
        if self._client is not None:
            await self._run_sync(self._client.close)


def get_bq_client(project_id: Optional[str] = None) -> BigQueryClient:
    """Return a shared BigQueryClient singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = BigQueryClient(project_id=project_id)
    return _client_instance
