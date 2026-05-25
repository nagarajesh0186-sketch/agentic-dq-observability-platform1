"""Reporting Agent — creates BigQuery views for BI consumption."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from schemas.bq_schemas import REPORTING_VIEWS, format_view
from schemas.models import ReportingView
from tools.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)


class ReportingAgent:
    """Creates and refreshes BigQuery reporting views for BI tools."""

    def __init__(self, bq_client: BigQueryClient, dq_project: str, dq_dataset: str) -> None:
        self._bq_client = bq_client
        self._dq_project = dq_project
        self._dq_dataset = dq_dataset
        self._log = logger.bind(agent="ReportingAgent")

    async def run(self) -> list[ReportingView]:
        """Create all standard reporting views in BigQuery."""
        self._log.info(
            "reporting_start",
            project=self._dq_project,
            dataset=self._dq_dataset,
        )

        created_views: list[ReportingView] = []

        for view_name, view_sql_template in REPORTING_VIEWS.items():
            view = await self._create_view(view_name, view_sql_template)
            if view:
                created_views.append(view)

        self._log.info("reporting_complete", views_created=len(created_views))
        return created_views

    async def _create_view(self, view_name: str, sql_template: str) -> ReportingView | None:
        """Create a single BigQuery view, replacing any existing definition."""
        sql = format_view(sql_template, self._dq_project, self._dq_dataset)

        try:
            await self._bq_client.execute_dml(sql)
            self._log.info("view_created", view=view_name)

            return ReportingView(
                view_name=view_name,
                view_sql=sql,
                description=self._view_description(view_name),
                created_at=datetime.utcnow(),
            )
        except Exception as exc:
            self._log.error("view_creation_failed", view=view_name, error=str(exc))
            return None

    async def refresh_materialized_view(self, view_name: str) -> bool:
        """Refresh a materialized view by re-running the underlying SELECT."""
        mv_table = f"{view_name}_mv"
        full_view_id = f"`{self._dq_project}.{self._dq_dataset}.{view_name}`"
        full_mv_id = f"`{self._dq_project}.{self._dq_dataset}.{mv_table}`"

        sql = f"""
        CREATE OR REPLACE TABLE {full_mv_id}
        AS SELECT * FROM {full_view_id}
        """
        try:
            await self._bq_client.execute_dml(sql)
            self._log.info("materialized_view_refreshed", view=mv_table)
            return True
        except Exception as exc:
            self._log.error("materialized_view_refresh_failed", view=mv_table, error=str(exc))
            return False

    async def get_executive_kpi(self) -> dict[str, Any]:
        """Query the executive KPI view and return results."""
        sql = f"SELECT * FROM `{self._dq_project}.{self._dq_dataset}.v_dq_executive_kpi` LIMIT 1"
        try:
            rows = await self._bq_client.execute_query(sql)
            return rows[0] if rows else {}
        except Exception as exc:
            self._log.error("kpi_query_failed", error=str(exc))
            return {}

    async def get_table_health(self) -> list[dict[str, Any]]:
        """Query the table health view."""
        sql = f"SELECT * FROM `{self._dq_project}.{self._dq_dataset}.v_dq_table_health` ORDER BY health_score ASC LIMIT 100"
        try:
            return await self._bq_client.execute_query(sql)
        except Exception as exc:
            self._log.error("table_health_query_failed", error=str(exc))
            return []

    async def get_trend_data(self, days: int = 30) -> list[dict[str, Any]]:
        """Query the trend analysis view."""
        sql = f"""
        SELECT * FROM `{self._dq_project}.{self._dq_dataset}.v_dq_trend_analysis`
        WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
        ORDER BY run_date DESC
        LIMIT 1000
        """
        try:
            return await self._bq_client.execute_query(sql)
        except Exception as exc:
            self._log.error("trend_query_failed", error=str(exc))
            return []

    async def get_failed_rules(self) -> list[dict[str, Any]]:
        """Query the failed rules view (last 7 days, deduplicated to latest failure per rule)."""
        sql = f"SELECT * FROM `{self._dq_project}.{self._dq_dataset}.v_dq_failed_rules` ORDER BY severity DESC, execution_time DESC LIMIT 500"
        try:
            return await self._bq_client.execute_query(sql)
        except Exception as exc:
            self._log.error("failed_rules_query_failed", error=str(exc))
            return []

    async def get_freshness_report(self) -> list[dict[str, Any]]:
        """Query the freshness report view."""
        sql = f"SELECT * FROM `{self._dq_project}.{self._dq_dataset}.v_dq_freshness_report` ORDER BY table_name"
        try:
            return await self._bq_client.execute_query(sql)
        except Exception as exc:
            self._log.error("freshness_query_failed", error=str(exc))
            return []

    async def setup_views(self) -> dict[str, bool]:
        """Create or replace all reporting views. Returns per-view success map."""
        from tools.bigquery.setup import ensure_dq_views
        return await ensure_dq_views(self._bq_client, self._dq_project, self._dq_dataset)

    @staticmethod
    def _view_description(view_name: str) -> str:
        descriptions = {
            "v_dq_executive_kpi": "Executive KPI snapshot: overall pass rate, health score, critical failures",
            "v_dq_table_health": "Per-table health score, last run time, and open failures",
            "v_dq_trend_analysis": "Daily/weekly pass/fail trends per rule type over 30 days",
            "v_dq_freshness_report": "Freshness lag per table vs. SLA target",
            "v_dq_failed_rules": "All active failures with severity and time-to-resolve",
        }
        return descriptions.get(view_name, f"DQ reporting view: {view_name}")
