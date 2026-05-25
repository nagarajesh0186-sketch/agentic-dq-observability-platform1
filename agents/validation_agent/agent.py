"""Validation Agent — executes DQ SQL and captures pass/fail results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog

from schemas.models import DQRule, DQRunResult
from tools.bigquery.client import BigQueryClient
from tools.bigquery.execution import ensure_dq_infrastructure, execute_dq_ruleset, get_run_summary

logger = structlog.get_logger(__name__)


class ValidationAgent:
    """Executes generated DQ SQL and persists structured results to BigQuery."""

    def __init__(self, bq_client: BigQueryClient, dq_project: str, dq_dataset: str) -> None:
        self._bq_client = bq_client
        self._dq_project = dq_project
        self._dq_dataset = dq_dataset
        self._log = logger.bind(agent="ValidationAgent")

    async def run(
        self,
        session_id: str,
        rules: list[DQRule],
        rule_set_version_id: str,
        run_id: str | None = None,
        concurrency: int = 10,
        consolidated_sp_name: str | None = None,
    ) -> DQRunResult:
        """Execute DQ rules and return aggregated run results.

        If `consolidated_sp_name` is provided, the execution uses a single CALL
        to the consolidated stored procedure. Otherwise falls back to per-rule execution.
        """
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        started_at = datetime.utcnow()

        self._log.info(
            "validation_start",
            session_id=session_id,
            run_id=run_id,
            rule_count=len(rules),
            mode="consolidated_sp" if consolidated_sp_name else "per_rule",
        )

        await ensure_dq_infrastructure(self._bq_client, self._dq_project, self._dq_dataset)

        if consolidated_sp_name:
            # Single CALL executes the full consolidated procedure
            # SP parameter is p_run_id (prefixed to avoid conflict with output column 'run_id')
            call_sql = (
                f"CALL `{self._dq_project}.{self._dq_dataset}.{consolidated_sp_name}`"
                f"('{run_id}')"
            )
            try:
                await self._bq_client.execute_ddl(call_sql)
                self._log.info("consolidated_sp_executed", sp=consolidated_sp_name, run_id=run_id)
            except Exception as exc:
                self._log.error("consolidated_sp_execution_failed", error=str(exc))
            skipped = 0
        else:
            # Per-rule fallback — each INSERT uses @run_id parameter
            active_rules = [r for r in rules if r.is_active and r.generated_sql]
            skipped = len(rules) - len(active_rules)
            if skipped > 0:
                self._log.warning("rules_skipped", count=skipped)
            rule_dicts = [self._rule_to_dict(rule) for rule in active_rules]
            await execute_dq_ruleset(
                self._bq_client, rule_dicts, run_id,
                concurrency=concurrency,
                dq_project=self._dq_project,
                dq_dataset=self._dq_dataset,
            )

        # Compute summary
        summary = await get_run_summary(
            self._bq_client, run_id, self._dq_project, self._dq_dataset
        )

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        run_result = DQRunResult(
            run_id=run_id,
            session_id=session_id,
            rule_set_version_id=rule_set_version_id,
            total_rules=summary["total_rules"] + skipped,
            passed=summary["passed"],
            failed=summary["failed"],
            errors=summary["errors"],
            skipped=summary["skipped"] + skipped,
            pass_rate=summary["pass_rate"],
            health_score=summary["health_score"],
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
        )

        self._log.info(
            "validation_complete",
            run_id=run_id,
            passed=run_result.passed,
            failed=run_result.failed,
            health_score=run_result.health_score,
        )

        return run_result

    @staticmethod
    def _rule_to_dict(rule: DQRule) -> dict[str, Any]:
        return {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "rule_category": rule.rule_category.value,
            "severity": rule.severity.value,
            "threshold": rule.threshold,
            "project_id": rule.project_id,
            "dataset_name": rule.dataset_name,
            "table_name": rule.table_name,
            "column_name": rule.column_name,
            "generated_sql": rule.generated_sql,
            "parameters": rule.parameters,
        }
