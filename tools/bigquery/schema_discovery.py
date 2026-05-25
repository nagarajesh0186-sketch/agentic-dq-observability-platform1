"""Metadata discovery and column profiling via BigQuery INFORMATION_SCHEMA."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from tools.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)

_COLUMNS_SQL = """
SELECT
    column_name,
    data_type,
    is_nullable,
    ordinal_position,
    column_default
FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = '{table}'
ORDER BY ordinal_position
"""

_TABLE_OPTIONS_SQL = """
SELECT
    option_name,
    option_value
FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLE_OPTIONS`
WHERE table_name = '{table}'
"""

_PARTITIONS_SQL = """
SELECT
    partition_id,
    total_rows,
    total_logical_bytes,
    last_modified_time
FROM `{project}.{dataset}.INFORMATION_SCHEMA.PARTITIONS`
WHERE table_name = '{table}'
ORDER BY last_modified_time DESC
LIMIT 10
"""

_TABLE_ROW_COUNT_SQL = """
SELECT COUNT(*) AS row_count
FROM `{project}.{dataset}.{table}`
"""

_COLUMN_PROFILE_SQL = """
SELECT
    COUNT(*) AS total_count,
    COUNTIF({col} IS NULL) AS null_count,
    COUNT(DISTINCT CAST({col} AS STRING)) AS distinct_count,
    CAST(MIN(CAST({col} AS STRING)) AS STRING) AS min_value,
    CAST(MAX(CAST({col} AS STRING)) AS STRING) AS max_value,
    ARRAY(
        SELECT CAST({col} AS STRING)
        FROM `{project}.{dataset}.{table}`
        WHERE {col} IS NOT NULL
        LIMIT 5
    ) AS sample_values
FROM `{project}.{dataset}.{table}`
"""

_NUMERIC_PROFILE_SQL = """
SELECT
    COUNT(*) AS total_count,
    COUNTIF({col} IS NULL) AS null_count,
    COUNT(DISTINCT {col}) AS distinct_count,
    CAST(MIN({col}) AS STRING) AS min_value,
    CAST(MAX({col}) AS STRING) AS max_value,
    ROUND(AVG(CAST({col} AS FLOAT64)), 4) AS avg_value,
    ARRAY(
        SELECT CAST({col} AS STRING)
        FROM `{project}.{dataset}.{table}`
        WHERE {col} IS NOT NULL
        LIMIT 5
    ) AS sample_values
FROM `{project}.{dataset}.{table}`
"""

_CLUSTERING_SQL = """
SELECT
    column_name,
    clustering_ordinal_position
FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = '{table}'
  AND clustering_ordinal_position IS NOT NULL
ORDER BY clustering_ordinal_position
"""


async def get_table_columns(
    client: BigQueryClient, project: str, dataset: str, table: str
) -> list[dict[str, Any]]:
    """Return column metadata from INFORMATION_SCHEMA.COLUMNS."""
    sql = _COLUMNS_SQL.format(project=project, dataset=dataset, table=table)
    return await client.execute_query(sql)


async def get_table_options(
    client: BigQueryClient, project: str, dataset: str, table: str
) -> dict[str, str]:
    """Return table options (description, labels, etc.)."""
    sql = _TABLE_OPTIONS_SQL.format(project=project, dataset=dataset, table=table)
    rows = await client.execute_query(sql)
    return {r["option_name"]: r["option_value"] for r in rows}


async def get_partition_info(
    client: BigQueryClient, project: str, dataset: str, table: str
) -> list[dict[str, Any]]:
    """Return recent partition information."""
    sql = _PARTITIONS_SQL.format(project=project, dataset=dataset, table=table)
    try:
        return await client.execute_query(sql)
    except Exception as exc:
        logger.warning("partition_info_unavailable", table=table, error=str(exc))
        return []


async def get_all_tables(
    client: BigQueryClient, project: str, dataset: str
) -> list[str]:
    """Return all table names in a dataset."""
    sql = f"""
    SELECT table_name
    FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLES`
    WHERE table_type = 'BASE TABLE'
    ORDER BY table_name
    """
    rows = await client.execute_query(sql)
    return [r["table_name"] for r in rows]


async def get_row_count(
    client: BigQueryClient, project: str, dataset: str, table: str
) -> int:
    """Return approximate row count for a table."""
    sql = _TABLE_ROW_COUNT_SQL.format(project=project, dataset=dataset, table=table)
    rows = await client.execute_query(sql)
    return rows[0]["row_count"] if rows else 0


async def profile_column(
    client: BigQueryClient,
    project: str,
    dataset: str,
    table: str,
    column_name: str,
    data_type: str,
) -> dict[str, Any]:
    """Profile a single column: null rate, distinct count, min/max, samples."""
    is_numeric = data_type.upper() in (
        "INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC",
        "DECIMAL", "BIGDECIMAL",
    )
    template = _NUMERIC_PROFILE_SQL if is_numeric else _COLUMN_PROFILE_SQL

    sql = template.format(
        project=project, dataset=dataset, table=table, col=f"`{column_name}`"
    )
    try:
        rows = await client.execute_query(sql)
        if not rows:
            return _empty_profile(column_name, data_type)

        row = rows[0]
        total = row.get("total_count", 0) or 1
        null_count = row.get("null_count", 0) or 0
        distinct_count = row.get("distinct_count", 0) or 0

        return {
            "column_name": column_name,
            "data_type": data_type,
            "total_count": total,
            "null_count": null_count,
            "null_rate": round(null_count / total, 4),
            "distinct_count": distinct_count,
            "cardinality_ratio": round(distinct_count / max(total, 1), 4),
            "min_value": row.get("min_value"),
            "max_value": row.get("max_value"),
            "avg_value": row.get("avg_value"),
            "sample_values": list(row.get("sample_values") or [])[:5],
        }
    except Exception as exc:
        logger.warning("column_profile_failed", column=column_name, error=str(exc))
        return _empty_profile(column_name, data_type)


async def profile_table(
    client: BigQueryClient,
    project: str,
    dataset: str,
    table: str,
    columns: list[dict[str, Any]],
    concurrency: int = 8,
) -> dict[str, Any]:
    """Profile all columns in a table concurrently."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _profile_with_sem(col: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await profile_column(
                client, project, dataset, table,
                col["column_name"], col["data_type"],
            )

    tasks = [_profile_with_sem(col) for col in columns]
    profiles = await asyncio.gather(*tasks)

    return {
        "project_id": project,
        "dataset_id": dataset,
        "table_name": table,
        "columns": profiles,
    }


async def get_table_metadata(
    client: BigQueryClient, project: str, dataset: str, table: str
) -> dict[str, Any]:
    """Retrieve full table metadata including columns, options, and partition info."""
    log = logger.bind(project=project, dataset=dataset, table=table)
    log.info("fetching_table_metadata")

    columns_task = get_table_columns(client, project, dataset, table)
    options_task = get_table_options(client, project, dataset, table)
    partitions_task = get_partition_info(client, project, dataset, table)
    row_count_task = get_row_count(client, project, dataset, table)
    clustering_task = _get_clustering_info(client, project, dataset, table)

    columns, options, partitions, row_count, clustering = await asyncio.gather(
        columns_task, options_task, partitions_task, row_count_task, clustering_task
    )

    partition_col = None
    if partitions:
        partition_col = _detect_partition_column(columns)

    total_bytes = sum(p.get("total_logical_bytes", 0) or 0 for p in partitions)

    return {
        "project_id": project,
        "dataset_id": dataset,
        "table_name": table,
        "full_table_id": f"{project}.{dataset}.{table}",
        "row_count": row_count,
        "size_bytes": total_bytes,
        "partition_column": partition_col,
        "clustering_columns": clustering,
        "columns": columns,
        "table_options": options,
        "description": options.get("description", ""),
        "labels": _parse_labels(options.get("labels", "")),
    }


async def _get_clustering_info(
    client: BigQueryClient, project: str, dataset: str, table: str
) -> list[str]:
    sql = _CLUSTERING_SQL.format(project=project, dataset=dataset, table=table)
    try:
        rows = await client.execute_query(sql)
        return [r["column_name"] for r in rows]
    except Exception:
        return []


def _detect_partition_column(columns: list[dict[str, Any]]) -> Optional[str]:
    date_type_hints = ("DATE", "TIMESTAMP", "DATETIME")
    date_name_hints = ("date", "timestamp", "created", "updated", "partition", "dt", "ts")
    for col in columns:
        dtype = col.get("data_type", "").upper()
        cname = col.get("column_name", "").lower()
        if any(h in dtype for h in date_type_hints):
            if any(h in cname for h in date_name_hints):
                return col["column_name"]
    return None


def _parse_labels(labels_str: str) -> dict[str, str]:
    if not labels_str or labels_str == "NULL":
        return {}
    try:
        import json
        return json.loads(labels_str)
    except Exception:
        return {}


def _empty_profile(column_name: str, data_type: str) -> dict[str, Any]:
    return {
        "column_name": column_name,
        "data_type": data_type,
        "total_count": 0,
        "null_count": 0,
        "null_rate": 0.0,
        "distinct_count": 0,
        "cardinality_ratio": 0.0,
        "min_value": None,
        "max_value": None,
        "avg_value": None,
        "sample_values": [],
    }
