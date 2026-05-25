"""Discovery API endpoints — metadata discovery and session management."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from api.middleware.auth import verify_api_key
from agents.orchestrator.agent import OrchestratorAgent
from schemas.models import APIResponse, DiscoveryRequest, WorkflowState

logger = structlog.get_logger(__name__)
router = APIRouter()

_sessions: dict[str, WorkflowState] = {}


def _check_gcp_credentials() -> None:
    """Raise HTTPException 503 immediately if GCP credentials are not configured."""
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError
    try:
        google.auth.default()
    except DefaultCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google Cloud credentials are not configured. "
                "Run: gcloud auth application-default login"
            ),
        )


def _get_orchestrator() -> OrchestratorAgent:
    return OrchestratorAgent()


@router.post(
    "/start",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start metadata discovery",
    description="Initiate a new DQ workflow session with metadata discovery.",
)
async def start_discovery(
    request: DiscoveryRequest,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    _check_gcp_credentials()
    try:
        orchestrator = _get_orchestrator()
        state = await orchestrator.start_workflow(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_names=request.table_names,
        )
        state = await orchestrator.run_stage_metadata_discovery(state)
        _sessions[state.session_id] = state

        logger.info("discovery_started", session_id=state.session_id)
        return APIResponse(
            success=True,
            data={
                "session_id": state.session_id,
                "stage": state.current_stage.value,
                "tables_discovered": list(state.metadata.keys()),
                "message": "Metadata discovery complete. Call /rules/generate to proceed.",
            },
            message="Discovery initiated successfully",
        )
    except Exception as exc:
        logger.error("discovery_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/{session_id}",
    response_model=APIResponse,
    summary="Get discovery results",
    description="Retrieve metadata discovery results for a session.",
)
async def get_discovery_results(
    session_id: str,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    return APIResponse(
        success=True,
        data={
            "session_id": session_id,
            "stage": state.current_stage.value,
            "tables": list(state.metadata.keys()),
            "errors": state.errors,
        },
    )
