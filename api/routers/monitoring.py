"""Monitoring API endpoints — configure and query monitoring status."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from api.middleware.auth import verify_api_key
from api.routers.discovery import _sessions, _get_orchestrator
from schemas.models import APIResponse, MonitoringConfigRequest

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/configure",
    response_model=APIResponse,
    summary="Configure monitoring",
    description="Configure monitoring schedules and alert thresholds.",
)
async def configure_monitoring(
    request: MonitoringConfigRequest,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")

    if state.monitoring_config is None:
        state.monitoring_config = {}
    state.monitoring_config[request.monitoring_config.table_name] = (
        request.monitoring_config.model_dump(mode="json")
    )
    _sessions[request.session_id] = state

    return APIResponse(
        success=True,
        data={
            "session_id": request.session_id,
            "table": request.monitoring_config.table_name,
            "schedule": request.monitoring_config.monitoring_schedule,
            "message": "Monitoring configured. Submit approval via POST /approvals/submit (stage: approval_2)",
        },
    )


@router.post(
    "/generate-dag",
    response_model=APIResponse,
    summary="Generate Airflow DAG",
    description="Generate an Airflow DAG Python file that calls the consolidated DQ stored procedure.",
)
async def generate_dag(
    body: dict,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    session_id = body.get("session_id")
    schedule = body.get("schedule", "0 6 * * *")

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    sp_name = state.consolidated_sp_name
    if not sp_name:
        raise HTTPException(
            status_code=400,
            detail=(
                "No consolidated stored procedure found for this session. "
                "Complete Checkpoint 1 approval first to auto-generate it."
            ),
        )

    from tools.airflow.dag_builder import generate_consolidated_sp_dag
    from configs.settings import get_settings
    settings = get_settings()

    dag_content = generate_consolidated_sp_dag(
        session_id=session_id,
        sp_name=sp_name,
        dq_project=settings.gcp.project_id,
        dq_dataset=settings.gcp.dq_dataset,
        schedule=schedule,
        owner=body.get("owner", "data-quality"),
    )

    dag_id = f"dq_pipeline_{session_id[:12]}"
    return APIResponse(
        success=True,
        data={
            "session_id": session_id,
            "dag_id": dag_id,
            "sp_name": sp_name,
            "schedule": schedule,
            "filename": f"{dag_id}.py",
            "dag_content": dag_content,
        },
    )


@router.get(
    "/status",
    response_model=APIResponse,
    summary="Get monitoring status",
    description="Return current monitoring configuration and status.",
)
async def get_monitoring_status(
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
            "monitoring_config": state.monitoring_config or {},
            "approval_2_status": state.approval_2_status.value,
        },
    )
