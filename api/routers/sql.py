"""SQL API endpoints — generate and execute DQ SQL."""

from __future__ import annotations

import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from api.middleware.auth import verify_api_key
from api.routers.discovery import _sessions, _get_orchestrator
from schemas.models import APIResponse, SQLGenerationRequest

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/generate",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate DQ SQL",
    description="Generate parameterized BigQuery SQL for all approved rules.",
)
async def generate_sql(
    request: SQLGenerationRequest,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")

    from schemas.models import ApprovalStatus
    if state.approval_1_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Checkpoint 1 approval is required before SQL generation. Submit approval first.",
        )

    orchestrator = _get_orchestrator()
    try:
        state = await orchestrator.run_stage_sql_generation(state)
        _sessions[request.session_id] = state

        rules = state.rule_set.all_rules if state.rule_set else []
        with_sql = sum(1 for r in rules if r.generated_sql)

        return APIResponse(
            success=True,
            data={
                "session_id": request.session_id,
                "total_rules": len(rules),
                "sql_generated": with_sql,
                "stage": state.current_stage.value,
                "message": "SQL generated. Execute via POST /sql/execute",
            },
        )
    except Exception as exc:
        logger.error("sql_generation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/rebuild-sp",
    response_model=APIResponse,
    summary="Rebuild consolidated stored procedure",
    description=(
        "Regenerates SQL for all approved rules using the current generator and "
        "redeploys the consolidated stored procedure in BigQuery."
    ),
)
async def rebuild_sp(
    body: dict,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    from schemas.models import ApprovalStatus
    if state.approval_1_status != ApprovalStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Checkpoint 1 must be approved before rebuilding the SP.")

    orchestrator = _get_orchestrator()
    try:
        state = await orchestrator.run_stage_sql_generation(state)
        _sessions[session_id] = state

        rules = state.rule_set.all_rules if state.rule_set else []
        with_sql = sum(1 for r in rules if r.generated_sql)

        return APIResponse(
            success=True,
            data={
                "session_id": session_id,
                "sp_name": state.consolidated_sp_name,
                "rules_with_sql": with_sql,
                "total_rules": len(rules),
            },
            message=f"Stored procedure `{state.consolidated_sp_name}` rebuilt with updated SQL.",
        )
    except Exception as exc:
        logger.error("rebuild_sp_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/execute",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute DQ SQL",
    description="Execute all generated DQ SQL and write results to BigQuery.",
)
async def execute_sql(
    body: dict,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not state.rule_set:
        raise HTTPException(status_code=400, detail="No rules available for execution")

    from agents.validation_agent.agent import ValidationAgent
    from tools.bigquery.client import get_bq_client
    from configs.settings import get_settings

    settings = get_settings()
    bq_client = get_bq_client()
    validation_agent = ValidationAgent(bq_client, settings.gcp.project_id, settings.gcp.dq_dataset)

    try:
        run_result = await validation_agent.run(
            session_id=session_id,
            rules=state.rule_set.all_rules,
            rule_set_version_id=state.rule_set.rule_set_version_id,
            consolidated_sp_name=state.consolidated_sp_name,
        )
        state.run_results = run_result
        _sessions[session_id] = state

        # --- Auto-send email alert if there are failures or warnings ---
        await _send_dq_alert(run_result, session_id)

        return APIResponse(
            success=True,
            data={
                "run_id": run_result.run_id,
                "session_id": session_id,
                "total_rules": run_result.total_rules,
                "passed": run_result.passed,
                "failed": run_result.failed,
                "errors": run_result.errors,
                "pass_rate": run_result.pass_rate,
                "health_score": run_result.health_score,
                "duration_seconds": run_result.duration_seconds,
            },
        )
    except Exception as exc:
        logger.error("sql_execution_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _send_dq_alert(run_result, session_id: str) -> None:
    """Send email alert if DQ run has failures or warnings."""
    try:
        # Only alert if there are failures
        if run_result.failed == 0 and run_result.errors == 0:
            logger.info("no_failures_no_alert_needed", session_id=session_id)
            return

        from tools.alerts.email import EmailAlerter

        # Determine severity based on results
        severity = "FAIL" if run_result.failed > 0 else "WARN"

        # Build failures list from results
        failures = []
        for r in (run_result.results or []):
            from schemas.models import DQStatus
            if r.status in (DQStatus.FAIL, DQStatus.ERROR):
                failures.append({
                    "rule_id":        r.rule_id,
                    "rule_type":      r.rule_type,
                    "severity":       r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                    "observed_value": r.observed_value or "N/A",
                })

        # Health score colour indicator
        hs = run_result.health_score
        hs_label = "🟢 Healthy" if hs >= 80 else ("🟡 At Risk" if hs >= 60 else "🔴 Critical")

        alerter = EmailAlerter()
        await alerter.send_alert(
            subject=f"🚨 DQ Alert — {run_result.failed} failure(s) detected [{severity}]",
            title=f"Data Quality Run Complete — {hs_label}",
            message=(
                f"DQ run completed with {run_result.failed} failure(s) and "
                f"{run_result.passed} passing checks. "
                f"Health Score: {hs:.0f}/100 | Pass Rate: {run_result.pass_rate * 100:.1f}%"
            ),
            severity=severity,
            table_name=", ".join(
                {r.table_name for r in (run_result.results or [])}
            ) or "enterprise_customer_transactions",
            failures=failures[:20],
            run_id=run_result.run_id,
        )

        logger.info(
            "dq_alert_sent",
            session_id=session_id,
            run_id=run_result.run_id,
            failed=run_result.failed,
            severity=severity,
        )

    except Exception as exc:
        # Never let alert failure block the main response
        logger.warning("dq_alert_failed", error=str(exc)[:200])