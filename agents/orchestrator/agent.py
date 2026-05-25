"""Orchestrator Agent — coordinates the full multi-agent DQ workflow."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog

from agents.approval_agent.agent import HumanApprovalAgent
from agents.base import BaseAgent
from agents.business_dq_agent.agent import BusinessRuleRecommendationAgent
from agents.metadata_agent.agent import MetadataDiscoveryAgent
from agents.monitoring_agent.agent import MonitoringAgent
from agents.reporting_agent.agent import ReportingAgent
from agents.sql_generation_agent.agent import SQLGenerationAgent
from agents.technical_dq_agent.agent import TechnicalRuleEngineAgent
from agents.validation_agent.agent import ValidationAgent
from configs.settings import get_settings
from prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT_V1, STAGE_TRANSITION_PROMPT_V1
from schemas.models import (
    ApprovalStatus,
    DQRuleSet,
    WorkflowStage,
    WorkflowState,
)
from tools.bigquery.client import BigQueryClient, get_bq_client

logger = structlog.get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Coordinates the full 10-stage DQ workflow:
    Metadata → Tech Rules → Business Rules → Approval 1 → SQL Gen →
    DAG Integration → Monitoring Config → Approval 2 → Reporting → Complete
    """

    def __init__(self) -> None:
        super().__init__(
            agent_name="OrchestratorAgent",
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT_V1,
        )
        settings = get_settings()
        self._settings = settings
        self._bq_client: BigQueryClient = get_bq_client(settings.gcp.project_id)
        self._dq_project = settings.gcp.project_id
        self._dq_dataset = settings.gcp.dq_dataset

        self._metadata_agent = MetadataDiscoveryAgent(self._bq_client)
        self._technical_agent = TechnicalRuleEngineAgent()
        self._business_agent = BusinessRuleRecommendationAgent()
        self._sql_agent = SQLGenerationAgent(self._dq_project, self._dq_dataset)
        self._validation_agent = ValidationAgent(self._bq_client, self._dq_project, self._dq_dataset)
        self._monitoring_agent = MonitoringAgent(self._bq_client)
        self._reporting_agent = ReportingAgent(self._bq_client, self._dq_project, self._dq_dataset)
        self._approval_agent = HumanApprovalAgent(self._bq_client, self._dq_project, self._dq_dataset)

    async def start_workflow(
        self,
        project_id: str,
        dataset_id: str,
        table_names: list[str],
    ) -> WorkflowState:
        """Initialize and start a new DQ workflow session."""
        state = WorkflowState(
            project_id=project_id,
            dataset_id=dataset_id,
            table_names=table_names,
        )
        await self._persist_state(state)
        self._log.info("workflow_started", session_id=state.session_id)
        return state

    async def run_stage_metadata_discovery(self, state: WorkflowState) -> WorkflowState:
        """Stage 1: Discover metadata, profile columns, infer semantics."""
        state.advance_stage(WorkflowStage.METADATA_DISCOVERY)
        await self._persist_state(state)

        try:
            result = await self._metadata_agent.run(
                project_id=state.project_id,
                dataset_id=state.dataset_id,
                table_names=state.table_names,
            )
            state.metadata = result.get("tables", {})
            self._log.info("metadata_discovery_done", tables=len(state.metadata))
        except Exception as exc:
            state.record_error("metadata_discovery", str(exc))
            self._log.error("metadata_discovery_failed", error=str(exc))

        await self._persist_state(state)
        return state

    async def run_stage_technical_rules(self, state: WorkflowState) -> WorkflowState:
        """Stage 2: Generate technical DQ rules."""
        state.advance_stage(WorkflowStage.TECHNICAL_RULES)

        rule_set_version_id = f"rs_{uuid.uuid4().hex[:8]}"
        try:
            tech_rules = await self._technical_agent.run(
                project_id=state.project_id,
                dataset_id=state.dataset_id,
                table_metadata={"tables": state.metadata},
                column_profiles={},
                column_semantics={},
                rule_set_version_id=rule_set_version_id,
            )

            state.rule_set = DQRuleSet(
                session_id=state.session_id,
                project_id=state.project_id,
                dataset_id=state.dataset_id,
                table_names=state.table_names,
                technical_rules=tech_rules,
                rule_set_version_id=rule_set_version_id,
            )
            self._log.info("technical_rules_generated", count=len(tech_rules))
        except Exception as exc:
            state.record_error("technical_rules", str(exc))

        await self._persist_state(state)
        return state

    async def run_stage_business_rules(
        self,
        state: WorkflowState,
        custom_context: str | None = None,
    ) -> WorkflowState:
        """Stage 3: Generate LLM-inferred business rules."""
        state.advance_stage(WorkflowStage.BUSINESS_RULES)

        if not state.rule_set:
            state.record_error("business_rules", "No rule_set found — skipping business rules")
            return state

        version_id = state.rule_set.rule_set_version_id
        technical_rules = state.rule_set.technical_rules
        try:
            for table_name, table_data in state.metadata.items():
                business_rules = await self._business_agent.run(
                    project_id=state.project_id,
                    dataset_id=state.dataset_id,
                    table_name=table_name,
                    metadata=table_data.get("metadata", {}),
                    profiles=table_data.get("profiling", {}),
                    semantics=table_data.get("semantics", {}),
                    rule_set_version_id=version_id,
                    custom_context=custom_context,
                    existing_rules=technical_rules,
                    dataplex_tags=table_data.get("dataplex_tags") or [],
                    bq_client=self._bq_client,
                )
                state.rule_set.business_rules.extend(business_rules)

            self._log.info("business_rules_generated", count=len(state.rule_set.business_rules))
        except Exception as exc:
            state.record_error("business_rules", str(exc))

        await self._persist_state(state)
        return state

    async def create_approval_checkpoint_1(self, state: WorkflowState) -> dict[str, Any]:
        """Checkpoint 1: Return approval request for rule set review."""
        state.advance_stage(WorkflowStage.APPROVAL_1)

        if not state.rule_set:
            return {"error": "No rule set available for approval"}

        all_rules = state.rule_set.all_rules
        summary = {
            "session_id": state.session_id,
            "total_rules": len(all_rules),
            "technical_rules": len(state.rule_set.technical_rules),
            "business_rules": len(state.rule_set.business_rules),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "category": r.rule_category.value,
                    "severity": r.severity.value,
                    "threshold": r.threshold,
                    "table": r.table_name,
                    "column": r.column_name,
                    "description": r.description,
                }
                for r in all_rules
            ],
        }

        return await self._approval_agent.create_approval_request(
            session_id=state.session_id,
            stage="approval_1",
            rule_set=state.rule_set,
            display_summary=summary,
        )

    async def process_approval_1(
        self,
        state: WorkflowState,
        status: ApprovalStatus,
        approver_id: str,
        approver_email: str | None = None,
        comments: str | None = None,
        rule_modifications: list[dict[str, Any]] | None = None,
    ) -> WorkflowState:
        """Process checkpoint 1 approval decision."""
        record = await self._approval_agent.process_approval(
            session_id=state.session_id,
            stage="approval_1",
            status=status,
            approver_id=approver_id,
            approver_email=approver_email,
            comments=comments,
            rule_modifications=rule_modifications,
        )

        state.approval_1_status = status

        if status == ApprovalStatus.MODIFIED and rule_modifications and state.rule_set:
            all_rules = state.rule_set.all_rules
            updated = await self._approval_agent.apply_rule_modifications(all_rules, rule_modifications)
            state.rule_set.rules = updated
            state.rule_set.technical_rules = []
            state.rule_set.business_rules = []

        if status == ApprovalStatus.APPROVED and state.rule_set:
            self._log.info("auto_sql_generation_triggered", session_id=state.session_id)
            try:
                state = await self.run_stage_sql_generation(state)
            except Exception as exc:
                state.record_error("auto_sql_generation", str(exc))
                self._log.error("auto_sql_generation_failed", error=str(exc))

        await self._persist_state(state)
        return state

    async def process_approval_2(
        self,
        state: WorkflowState,
        status: ApprovalStatus,
        approver_id: str,
        approver_email: str | None = None,
        comments: str | None = None,
    ) -> WorkflowState:
        """Process checkpoint 2 — DQ results review before production sign-off.

        CP2 APPROVED → refresh reporting views → mark workflow COMPLETE
        CP2 REJECTED → halt, flag for remediation
        """
        self._log.info(
            "checkpoint_2_processing",
            session_id=state.session_id,
            status=status.value,
            approver=approver_id,
        )

        # Record approval in audit log
        await self._approval_agent.process_approval(
            session_id=state.session_id,
            stage="approval_2",
            status=status,
            approver_id=approver_id,
            approver_email=approver_email,
            comments=comments,
        )

        state.approval_2_status = status
        state.updated_at = datetime.utcnow()

        if status == ApprovalStatus.APPROVED:
            self._log.info("checkpoint_2_approved_running_reporting", session_id=state.session_id)
            try:
                # Refresh all reporting views in BigQuery
                state = await self.run_stage_reporting(state)
                self._log.info("checkpoint_2_complete", session_id=state.session_id)
            except Exception as exc:
                state.record_error("checkpoint_2_reporting", str(exc))
                self._log.error("checkpoint_2_reporting_failed", error=str(exc))
        else:
            # REJECTED — log and halt
            self._log.warning(
                "checkpoint_2_rejected",
                session_id=state.session_id,
                comments=comments,
            )
            state.record_error(
                "checkpoint_2_rejected",
                f"CP2 rejected by {approver_id}: {comments or 'No comments provided'}",
            )

        await self._persist_state(state)
        return state

    async def run_stage_sql_generation(self, state: WorkflowState) -> WorkflowState:
        """Stage 6: Generate BigQuery SQL for all approved rules."""
        if state.approval_1_status != ApprovalStatus.APPROVED:
            state.record_error("sql_generation", "Cannot proceed — Checkpoint 1 not approved")
            return state

        state.advance_stage(WorkflowStage.SQL_GENERATION)
        if not state.rule_set:
            state.record_error("sql_generation", "No rule set available")
            return state

        try:
            run_id = f"run_{uuid.uuid4().hex[:12]}"
            active_rules = [r for r in state.rule_set.all_rules if r.is_active]
            updated_rules = await self._sql_agent.run(
                rules=active_rules,
                table_metadata=state.metadata,
                run_id=run_id,
            )
            state.rule_set.rules = updated_rules
            state.rule_set.technical_rules = []
            state.rule_set.business_rules = []
            rules_with_sql = sum(1 for r in updated_rules if r.generated_sql)
            self._log.info("sql_generation_done", active_rules=len(active_rules), rules_with_sql=rules_with_sql)

            await self._sql_agent.persist_rules_to_bigquery(
                updated_rules,
                session_id=state.session_id,
                rule_set_version_id=state.rule_set.rule_set_version_id,
                bq_client=self._bq_client,
            )

            try:
                sp_name = await self._sql_agent.create_consolidated_stored_procedure(
                    updated_rules,
                    bq_client=self._bq_client,
                    session_id=state.session_id,
                )
                if sp_name:
                    state.consolidated_sp_name = sp_name
                    self._log.info("consolidated_sp_stored", sp=sp_name)
            except Exception as sp_exc:
                state.record_error("consolidated_sp_creation", str(sp_exc))
                self._log.error("consolidated_sp_creation_failed", error=str(sp_exc))
        except Exception as exc:
            state.record_error("sql_generation", str(exc))

        await self._persist_state(state)
        return state

    async def run_stage_monitoring_config(self, state: WorkflowState) -> WorkflowState:
        """Stage 8: Generate monitoring configuration."""
        state.advance_stage(WorkflowStage.MONITORING_CONFIG)

        try:
            for table_name in state.table_names:
                table_data = state.metadata.get(table_name, {})
                row_count = table_data.get("metadata", {}).get("row_count", 0)
                partition_col = table_data.get("metadata", {}).get("partition_column")

                config = await self._monitoring_agent.recommend_monitoring_config(
                    session_id=state.session_id,
                    table_name=table_name,
                    row_count=row_count,
                    partition_column=partition_col,
                )
                if state.monitoring_config is None:
                    state.monitoring_config = {}
                state.monitoring_config[table_name] = config.model_dump(mode="json")
        except Exception as exc:
            state.record_error("monitoring_config", str(exc))

        await self._persist_state(state)
        return state

    async def run_stage_reporting(self, state: WorkflowState) -> WorkflowState:
        """Stage 10: Create BigQuery reporting views — triggered by CP2 approval."""
        if state.approval_2_status != ApprovalStatus.APPROVED:
            state.record_error("reporting", "Cannot proceed — Checkpoint 2 not approved")
            return state

        state.advance_stage(WorkflowStage.REPORTING)

        try:
            views = await self._reporting_agent.run()
            self._log.info("reporting_done", views_created=len(views))
        except Exception as exc:
            state.record_error("reporting", str(exc))

        state.advance_stage(WorkflowStage.COMPLETE)
        state.completed_at = datetime.utcnow()
        await self._persist_state(state)
        return state

    async def _persist_state(self, state: WorkflowState) -> None:
        """Persist workflow state to BigQuery."""
        table_id = f"{self._dq_project}.{self._dq_dataset}.dq_workflow_state"
        rows = [{
            "session_id": state.session_id,
            "current_stage": state.current_stage.value,
            "project_id": state.project_id,
            "dataset_id": state.dataset_id,
            "table_names": json.dumps(state.table_names),
            "approval_1_status": state.approval_1_status.value,
            "approval_2_status": state.approval_2_status.value,
            "rule_set_version_id": state.rule_set.rule_set_version_id if state.rule_set else None,
            "state_json": json.dumps({"errors": state.errors, "retry_count": state.retry_count}, default=str),
            "retry_count": state.retry_count,
            "errors_json": json.dumps(state.errors, default=str),
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
        }]
        try:
            await self._bq_client.insert_rows(table_id, rows)
        except Exception as exc:
            self._log.error("state_persist_failed", error=str(exc))