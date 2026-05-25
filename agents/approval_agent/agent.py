"""Human Approval Agent — checkpoint enforcement with audit logging."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog

from schemas.models import ApprovalRecord, ApprovalStatus, AuditLogEntry, DQRule, WorkflowState
from tools.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)


class HumanApprovalAgent:
    """Manages human-in-the-loop approval checkpoints with full audit trail."""

    def __init__(self, bq_client: BigQueryClient, dq_project: str, dq_dataset: str) -> None:
        self._bq_client = bq_client
        self._dq_project = dq_project
        self._dq_dataset = dq_dataset
        self._log = logger.bind(agent="HumanApprovalAgent")

    async def create_approval_request(
        self,
        session_id: str,
        stage: str,
        rule_set: Any,
        display_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an approval request and return the pending approval record."""
        approval_id = f"appr_{uuid.uuid4().hex[:8]}"

        self._log.info(
            "approval_request_created",
            session_id=session_id,
            stage=stage,
            approval_id=approval_id,
        )

        return {
            "approval_id": approval_id,
            "session_id": session_id,
            "stage": stage,
            "status": ApprovalStatus.PENDING.value,
            "summary": display_summary,
            "created_at": datetime.utcnow().isoformat(),
            "instructions": (
                f"Review the {stage} approval request and submit your decision via "
                f"POST /api/v1/approvals/submit with approval_id={approval_id}"
            ),
        }

    async def process_approval(
        self,
        session_id: str,
        stage: str,
        status: ApprovalStatus,
        approver_id: str,
        approver_email: str | None,
        comments: str | None,
        rule_modifications: list[dict[str, Any]] | None = None,
    ) -> ApprovalRecord:
        """Process and persist an approval decision."""
        if status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.MODIFIED):
            raise ValueError(f"Invalid approval status: {status}. Must be APPROVED, REJECTED, or MODIFIED.")

        record = ApprovalRecord(
            session_id=session_id,
            stage=stage,
            status=status,
            approver_id=approver_id,
            approver_email=approver_email,
            comments=comments,
            changes_made=rule_modifications or [],
        )

        await self._persist_approval(record)

        audit_entry = AuditLogEntry(
            session_id=session_id,
            action=f"approval_{status.value}",
            actor_id=approver_id,
            actor_email=approver_email,
            resource_type="approval",
            resource_id=record.approval_id,
            details={
                "stage": stage,
                "status": status.value,
                "comments": comments,
                "modifications_count": len(rule_modifications or []),
            },
        )
        await self._persist_audit_log(audit_entry)

        self._log.info(
            "approval_processed",
            session_id=session_id,
            stage=stage,
            status=status.value,
            approver=approver_id,
        )

        return record

    async def get_approval_status(self, session_id: str, stage: str) -> dict[str, Any]:
        """Query BigQuery for the current approval status for a session/stage."""
        sql = f"""
        SELECT *
        FROM `{self._dq_project}.{self._dq_dataset}.dq_audit_log`
        WHERE session_id = @session_id
          AND resource_type = 'approval'
          AND JSON_VALUE(details_json, '$.stage') = @stage
        ORDER BY timestamp DESC
        LIMIT 1
        """
        try:
            rows = await self._bq_client.execute_query(
                sql, params={"session_id": session_id, "stage": stage}
            )
            if rows:
                return dict(rows[0])
            return {"status": ApprovalStatus.PENDING.value, "stage": stage}
        except Exception as exc:
            self._log.error("approval_status_query_failed", error=str(exc))
            return {"status": "unknown", "error": str(exc)}

    async def apply_rule_modifications(
        self,
        rules: list[DQRule],
        modifications: list[dict[str, Any]],
    ) -> list[DQRule]:
        """Apply user modifications to rules before SQL generation."""
        mod_map = {m["rule_id"]: m for m in modifications if "rule_id" in m}

        updated: list[DQRule] = []
        for rule in rules:
            if rule.rule_id in mod_map:
                mod = mod_map[rule.rule_id]
                if "severity" in mod:
                    from schemas.models import Severity
                    rule.severity = Severity(mod["severity"].upper())
                if "threshold" in mod:
                    rule.threshold = float(mod["threshold"])
                if "is_active" in mod:
                    rule.is_active = bool(mod["is_active"])
                if "execution_frequency" in mod:
                    rule.execution_frequency = mod["execution_frequency"]
                rule.updated_at = datetime.utcnow()
            updated.append(rule)

        removed = set(mod_map.keys()) - {r.rule_id for r in rules}
        for rule_id in removed:
            self._log.warning("modification_target_not_found", rule_id=rule_id)

        return [r for r in updated if r.is_active]

    async def _persist_approval(self, record: ApprovalRecord) -> None:
        table_id = f"{self._dq_project}.{self._dq_dataset}.dq_audit_log"
        rows = [{
            "audit_id": record.approval_id,
            "session_id": record.session_id,
            "action": f"approval_{record.status.value}",
            "actor_id": record.approver_id,
            "actor_email": record.approver_email,
            "resource_type": "approval",
            "resource_id": record.approval_id,
            "details_json": json.dumps({
                "stage": record.stage,
                "status": record.status.value,
                "comments": record.comments,
                "changes_made": record.changes_made,
            }),
            "timestamp": record.created_at.isoformat(),
        }]
        try:
            await self._bq_client.insert_rows(table_id, rows)
        except Exception as exc:
            self._log.error("approval_persist_failed", error=str(exc))

    async def _persist_audit_log(self, entry: AuditLogEntry) -> None:
        table_id = f"{self._dq_project}.{self._dq_dataset}.dq_audit_log"
        rows = [{
            "audit_id": entry.audit_id,
            "session_id": entry.session_id,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_email": entry.actor_email,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details_json": json.dumps(entry.details, default=str),
            "timestamp": entry.timestamp.isoformat(),
        }]
        try:
            await self._bq_client.insert_rows(table_id, rows)
        except Exception as exc:
            self._log.error("audit_log_persist_failed", error=str(exc))
