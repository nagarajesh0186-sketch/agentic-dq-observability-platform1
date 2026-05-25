"""SQL Generation Agent — Stage 6 of the DQ workflow.

Redesigned (Nov 2025):
  - No Jinja2 templates. SQL is built programmatically from DQRule objects
    by tools.sql_tools.sql_generator.DQSQLGenerator.
  - Per-rule generated_sql is a standalone INSERT (with @run_id), used for
    inspection in dq_rule_config and as a fallback execution path.
  - The consolidated stored procedure is ONE CREATE OR REPLACE PROCEDURE
    containing a single INSERT with all rule SELECTs UNIONed together.
    No per-rule BEGIN/EXCEPTION wrapping is needed — every rule emits the
    same uniform row shape and the UNION ALL is one BigQuery job.
  - Custom (CUST_*) rules retain their user-supplied generated_sql verbatim.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog

from agents.base import BaseAgent
from prompts.sql_generation_agent import (
    SQL_GENERATION_PROMPT_V1,
    SQL_GENERATION_SYSTEM_PROMPT_V1,
)
from schemas.models import DQRule
from tools.bigquery.client import BigQueryClient
from tools.sql_tools.sql_generator import DQSQLGenerator, get_sql_generator
from tools.sql_tools.validator import validate_sql_syntax

logger = structlog.get_logger(__name__)


class SQLGenerationAgent(BaseAgent):
    """Generates executable BigQuery SQL for every approved DQ rule."""

    def __init__(self, dq_project: str, dq_dataset: str) -> None:
        super().__init__(
            agent_name="SQLGenerationAgent",
            system_prompt=SQL_GENERATION_SYSTEM_PROMPT_V1,
        )
        self._dq_project = dq_project
        self._dq_dataset = dq_dataset
        self._gen: DQSQLGenerator = get_sql_generator(dq_project, dq_dataset)

    # ------------------------------------------------------------------
    # Pipeline entry — populates rule.generated_sql for every rule
    # ------------------------------------------------------------------

    async def run(
        self,
        rules: list[DQRule],
        table_metadata: dict[str, Any],
        run_id: str | None = None,
        output_formats: list[str] | None = None,
    ) -> list[DQRule]:
        """Render generated_sql for each rule (standalone INSERT form)."""
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self._log.info("sql_generation_start", rule_count=len(rules), run_id=run_id)

        for rule in rules:
            if rule.generated_sql and rule.rule_id.startswith("CUST_"):
                # Custom rules: preserve user-supplied SQL verbatim.
                self._log.info("preserving_custom_sql", rule_id=rule.rule_id)
                continue

            sql = self._gen.standalone_insert(rule)
            if not sql:
                # Generator does not yet support this rule — try Claude fallback.
                sql = await self._generate_from_claude(rule, table_metadata, run_id)
                if not sql:
                    self._log.warning("no_sql_generated", rule_id=rule.rule_id)
                    continue

            valid, err = validate_sql_syntax(sql)
            if not valid:
                self._log.warning("generated_sql_invalid", rule_id=rule.rule_id, error=err)
            rule.generated_sql = sql

        generated = sum(1 for r in rules if r.generated_sql)
        self._log.info("sql_generation_complete", generated=generated, total=len(rules))
        return rules

    # ------------------------------------------------------------------
    # Claude fallback — only invoked when the rule category is not yet
    # supported by the programmatic generator
    # ------------------------------------------------------------------

    async def _generate_from_claude(
        self, rule: DQRule, metadata: dict[str, Any], run_id: str
    ) -> str | None:
        prompt = SQL_GENERATION_PROMPT_V1.format(
            rule_json=json.dumps(rule.model_dump(), indent=2, default=str),
            metadata_json=json.dumps(metadata, indent=2, default=str)[:3000],
            dq_project=self._dq_project,
            dq_dataset=self._dq_dataset,
            run_id=run_id,
        )
        try:
            result = await self._call_claude_json(prompt)
            return result.get("sql")
        except Exception as exc:
            self._log.error("claude_sql_generation_failed", rule_id=rule.rule_id, error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Persistence: store rule configs (+ generated SQL) to dq_rule_config
    # ------------------------------------------------------------------

    async def persist_rules_to_bigquery(
        self,
        rules: list[DQRule],
        session_id: str,
        rule_set_version_id: str,
        bq_client: BigQueryClient,
    ) -> None:
        table_id = f"{self._dq_project}.{self._dq_dataset}.dq_rule_config"
        now = datetime.utcnow().isoformat()
        rows = [
            {
                "rule_id": r.rule_id,
                "rule_set_version_id": rule_set_version_id,
                "session_id": session_id,
                "rule_name": r.rule_name,
                "rule_category": r.rule_category.value,
                "description": r.description,
                "severity": r.severity.value,
                "threshold": r.threshold,
                "execution_frequency": r.execution_frequency or "daily",
                "project_id": r.project_id,
                "dataset_name": r.dataset_name,
                "table_name": r.table_name,
                "column_name": r.column_name,
                "generated_sql": r.generated_sql,
                "parameters_json": json.dumps(r.parameters or {}, default=str),
                "rationale": r.rationale,
                "is_active": r.is_active,
                "created_at": now,
                "updated_at": now,
            }
            for r in rules
        ]
        try:
            await bq_client.insert_rows(table_id, rows)
            self._log.info("rules_persisted_to_bq", count=len(rows), table=table_id)
        except Exception as exc:
            self._log.error("rules_persist_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Consolidated stored procedure — one DDL, all rules in one INSERT
    # ------------------------------------------------------------------

    async def create_consolidated_stored_procedure(
        self,
        rules: list[DQRule],
        bq_client: BigQueryClient,
        session_id: str,
    ) -> str:
        """Build and deploy a single CREATE OR REPLACE PROCEDURE for all rules.

        Returns the (unqualified) procedure name, or "" if no rules were eligible.
        Raises RuntimeError on deployment failure.
        """
        active = [r for r in rules if r.is_active]
        if not active:
            self._log.warning("no_active_rules_for_sp", session_id=session_id)
            return ""

        ddl, sp_name, rule_count = self._gen.build_procedure(session_id, active)

        # Rules unsupported by the generator (e.g. AI-only with raw SQL)
        # are silently dropped from the SP. They still execute via per-rule
        # fallback path. Log so this is visible.
        if rule_count < len(active):
            self._log.warning(
                "sp_excludes_unsupported_rules",
                included=rule_count,
                total=len(active),
            )

        if not ddl:
            self._log.warning("no_sp_statements_generated", session_id=session_id)
            return ""

        self._log.info(
            "creating_sp",
            sp=sp_name,
            rules=rule_count,
            lines=len(ddl.splitlines()),
        )
        try:
            await bq_client.execute_ddl(ddl)
            self._log.info("consolidated_sp_created", sp=sp_name, rules=rule_count)
            return sp_name
        except Exception as exc:
            self._log.error("consolidated_sp_failed", session_id=session_id, error=str(exc))
            raise RuntimeError(
                f"Failed to create consolidated stored procedure `{sp_name}`: {exc}"
            ) from exc
