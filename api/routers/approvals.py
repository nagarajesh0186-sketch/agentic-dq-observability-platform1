"""Approvals API endpoints — human-in-the-loop checkpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from api.middleware.auth import verify_api_key
from api.routers.discovery import _sessions, _get_orchestrator
from schemas.models import APIResponse, ApprovalRequest, ApprovalStatus
from tools.airflow.dag_orchestrator import DAGOrchestrator

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/submit",
    response_model=APIResponse,
    summary="Submit approval decision",
    description="Submit APPROVED, REJECTED, or MODIFIED decision for a workflow checkpoint.",
)
async def submit_approval(
    request: ApprovalRequest,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {request.session_id} not found",
        )

    if request.stage not in ("approval_1", "approval_2"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown stage: {request.stage}. Must be approval_1 or approval_2.",
        )

    try:
        orchestrator = _get_orchestrator()

        if request.stage == "approval_1":
            state = await orchestrator.process_approval_1(
                state=state,
                status=request.status,
                approver_id=request.approver_id,
                approver_email=request.approver_email,
                comments=request.comments,
                rule_modifications=request.rule_modifications,
            )

            # --- Trigger Cloud Composer automatically after approval ---
            composer_result: dict = {}
            if request.status == ApprovalStatus.APPROVED:
                try:
                    dag_orch = DAGOrchestrator()
                    all_rules = []
                    if state.rule_set is not None:
                        all_rules = state.rule_set.all_rules

                    approved_rules = [
                        {
                            "rule_id": r.rule_id,
                            "rule_name": r.rule_name,
                            "generated_sql": r.generated_sql or "",
                            "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                            "project_id": r.project_id,
                            "table_name": r.table_name,
                        }
                        for r in all_rules
                    ]

                    sp_name = (
                        state.consolidated_sp_name
                        or f"sp_dq_{request.session_id}"
                    )

                    composer_result = await dag_orch.deploy_and_trigger(
                        session_id=request.session_id,
                        rules=approved_rules,
                        sp_name=sp_name,
                        schedule="0 6 * * *",
                        use_consolidated=True,
                    )

                    logger.info(
                        "composer_dag_deployed",
                        session_id=request.session_id,
                        dag_id=composer_result.get("dag_id"),
                        run_id=composer_result.get("run_id"),
                        status=composer_result.get("status"),
                    )

                except Exception as exc:
                    logger.warning(
                        "composer_deploy_failed_approval_still_recorded",
                        session_id=request.session_id,
                        error=str(exc)[:300],
                    )
                    composer_result = {"status": "failed", "error": str(exc)[:200]}

            next_action = (
                "SQL generated and stored as BigQuery stored procedures. "
                "DAG uploaded to Composer and triggered automatically. "
                "Once DQ results are available, proceed to Checkpoint 2 for production sign-off."
                if request.status == ApprovalStatus.APPROVED
                else "Workflow halted. Review rejection comments."
            )

        else:
            # ── Checkpoint 2: DQ Results Review → Production Sign-off ──
            state = await orchestrator.process_approval_2(
                state=state,
                status=request.status,
                approver_id=request.approver_id,
                approver_email=request.approver_email,
                comments=request.comments,
            )

            composer_result = {}
            next_action = (
                "Checkpoint 2 approved. Reporting views refreshed. Workflow complete. "
                "Data is certified for production use."
                if request.status == ApprovalStatus.APPROVED
                else "Checkpoint 2 rejected. Data NOT certified for production. Review DQ failures."
            )

        _sessions[request.session_id] = state

        return APIResponse(
            success=True,
            data={
                "session_id": request.session_id,
                "stage": request.stage,
                "decision": request.status.value,
                "next_action": next_action,
                **({"composer": composer_result} if composer_result else {}),
            },
            message=f"Approval {request.status.value} recorded for stage {request.stage}",
        )

    except Exception as exc:
        logger.error("approval_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/dq-results/{session_id}",
    response_model=APIResponse,
    summary="Get DQ results summary for CP2 review",
    description="Fetch latest DQ run results for a session — used in Checkpoint 2 review.",
)
async def get_dq_results_for_review(
    session_id: str,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    """Fetch DQ results from BigQuery for CP2 review."""
    from tools.bigquery.client import get_bq_client
    from configs.settings import get_settings

    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    settings = get_settings()
    bq = get_bq_client()

    try:
        # Get summary stats for latest run
        summary_sql = f"""
            WITH latest AS (
                SELECT MAX(execution_time) AS max_time
                FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_results`
                WHERE DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
            )
            SELECT
                COUNT(*) AS total_rules,
                COUNTIF(status = 'PASS') AS passed,
                COUNTIF(status = 'FAIL') AS failed,
                COUNTIF(status = 'FAIL' AND severity = 'FAIL') AS critical_failures,
                ROUND(SAFE_DIVIDE(COUNTIF(status = 'PASS'), COUNT(*)) * 100, 2) AS pass_rate_pct,
                ROUND(
                    (SAFE_DIVIDE(COUNTIF(status = 'PASS'), COUNT(*)) * 0.7 +
                    (1 - SAFE_DIVIDE(COUNTIF(status = 'FAIL' AND severity = 'FAIL'), COUNT(*))) * 0.3) * 100,
                2) AS health_score,
                MAX(execution_time) AS last_run_time
            FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_results` r
            CROSS JOIN latest lr
            WHERE r.execution_time >= lr.max_time - INTERVAL 1 HOUR
        """

        # Get failure details
        failures_sql = f"""
            WITH latest AS (
                SELECT MAX(execution_time) AS max_time
                FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_results`
                WHERE DATE(execution_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
            )
            SELECT
                r.rule_id,
                r.rule_type,
                r.severity,
                r.status,
                r.table_name,
                r.column_name,
                r.observed_value,
                r.expected_value,
                r.failure_count,
                rc.rule_name,
                rc.description,
                CASE WHEN r.rule_id LIKE 'BRUL_%' THEN 'business' ELSE 'technical' END AS rule_layer
            FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_results` r
            CROSS JOIN latest lr
            LEFT JOIN (
                SELECT DISTINCT rule_id, rule_name, description
                FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_rule_config`
            ) rc ON r.rule_id = rc.rule_id
            WHERE r.execution_time >= lr.max_time - INTERVAL 1 HOUR
              AND r.status = 'FAIL'
            ORDER BY
                CASE r.severity WHEN 'FAIL' THEN 1 WHEN 'WARN' THEN 2 ELSE 3 END,
                r.rule_type
            LIMIT 50
        """

        summary_rows = await bq.execute_query(summary_sql)
        failure_rows = await bq.execute_query(failures_sql)

        summary = summary_rows[0] if summary_rows else {}

        # Determine if data is safe for production
        critical = summary.get("critical_failures", 0) or 0
        health = summary.get("health_score", 0) or 0
        prod_safe = critical == 0 and health >= 70

        return APIResponse(
            success=True,
            data={
                "session_id": session_id,
                "summary": summary,
                "failures": failure_rows,
                "production_ready": prod_safe,
                "recommendation": (
                    "✅ Data quality is acceptable — safe to approve for production."
                    if prod_safe
                    else f"⚠️ {critical} critical failure(s) detected — review before approving for production."
                ),
            },
        )

    except Exception as exc:
        logger.error("dq_results_fetch_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/{session_id}",
    response_model=APIResponse,
    summary="Get approval status",
    description="Retrieve the current approval status for a session.",
)
async def get_approval_status(
    session_id: str,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return APIResponse(
        success=True,
        data={
            "session_id": session_id,
            "approval_1_status": state.approval_1_status.value,
            "approval_2_status": state.approval_2_status.value,
            "current_stage": state.current_stage.value,
        },
    )