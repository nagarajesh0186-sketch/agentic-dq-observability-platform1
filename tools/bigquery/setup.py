"""BigQuery infrastructure setup — idempotently creates DQ tables and reporting views."""

from __future__ import annotations

import structlog

from schemas.bq_schemas import REPORTING_VIEWS, TABLE_SCHEMAS, format_view
from tools.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)

_PARTITION_FIELDS: dict[str, str] = {
    "dq_results": "execution_time",
    "dq_workflow_state": "created_at",
    "dq_rule_config": "created_at",
    "dq_rule_versions": "created_at",
    "dq_audit_log": "timestamp",
    "dq_execution_log": "started_at",
    "dq_monitoring_config": "created_at",
}

_CLUSTERING_FIELDS: dict[str, list[str]] = {
    "dq_results": ["table_name", "rule_type", "severity"],
    "dq_workflow_state": ["session_id", "current_stage"],
    "dq_rule_config": ["table_name", "rule_category", "severity"],
    "dq_rule_versions": ["session_id", "approval_status"],
    "dq_audit_log": ["session_id", "action"],
    "dq_execution_log": ["session_id", "run_id"],
    "dq_monitoring_config": ["table_name"],
}


async def ensure_dq_tables(
    bq_client: BigQueryClient, project: str, dataset: str
) -> dict[str, bool]:
    """Create all DQ platform tables if they don't already exist. Returns per-table success map."""
    results: dict[str, bool] = {}
    for table_name, schema in TABLE_SCHEMAS.items():
        table_id = f"{project}.{dataset}.{table_name}"
        try:
            await bq_client.create_table_if_not_exists(
                table_id=table_id,
                schema=schema,
                partition_field=_PARTITION_FIELDS.get(table_name),
                clustering_fields=_CLUSTERING_FIELDS.get(table_name),
            )
            logger.info("table_ensured", table=table_name)
            results[table_name] = True
        except Exception as exc:
            logger.warning("table_creation_failed", table=table_name, error=str(exc))
            results[table_name] = False
    return results


async def ensure_dq_views(
    bq_client: BigQueryClient, project: str, dataset: str
) -> dict[str, bool]:
    """Create or replace all DQ reporting views. Returns per-view success map."""
    results: dict[str, bool] = {}
    for view_name, view_sql_template in REPORTING_VIEWS.items():
        sql = format_view(view_sql_template, project, dataset)
        try:
            await bq_client.execute_ddl(sql)
            logger.info("view_ensured", view=view_name)
            results[view_name] = True
        except Exception as exc:
            logger.warning("view_creation_failed", view=view_name, error=str(exc))
            results[view_name] = False
    return results
