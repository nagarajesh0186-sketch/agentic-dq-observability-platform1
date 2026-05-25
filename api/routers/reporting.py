"""Reporting API endpoints — health scores, KPIs, and trends."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from api.middleware.auth import verify_api_key
from configs.settings import get_settings
from schemas.models import APIResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


def _get_reporting_agent():
    from agents.reporting_agent.agent import ReportingAgent
    from tools.bigquery.client import get_bq_client
    settings = get_settings()
    return ReportingAgent(
        bq_client=get_bq_client(),
        dq_project=settings.gcp.project_id,
        dq_dataset=settings.gcp.dq_dataset,
    )


@router.get(
    "/health",
    response_model=APIResponse,
    summary="Table health scores",
    description="Return per-table health scores from the v_dq_table_health view.",
)
async def get_table_health(
    _: str = Depends(verify_api_key),
) -> APIResponse:
    try:
        agent = _get_reporting_agent()
        data = await agent.get_table_health()
        return APIResponse(success=True, data={"tables": data, "count": len(data)})
    except Exception as exc:
        logger.error("health_query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/kpi",
    response_model=APIResponse,
    summary="Executive KPI snapshot",
    description="Return the executive KPI summary from v_dq_executive_kpi.",
)
async def get_kpi(
    _: str = Depends(verify_api_key),
) -> APIResponse:
    try:
        agent = _get_reporting_agent()
        data = await agent.get_executive_kpi()
        return APIResponse(success=True, data=data)
    except Exception as exc:
        logger.error("kpi_query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/trends",
    response_model=APIResponse,
    summary="Trend data",
    description="Return daily DQ pass/fail trends from v_dq_trend_analysis.",
)
async def get_trends(
    days: int = 30,
    _: str = Depends(verify_api_key),
) -> APIResponse:
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    try:
        agent = _get_reporting_agent()
        data = await agent.get_trend_data(days=days)
        return APIResponse(success=True, data={"trends": data, "days": days, "count": len(data)})
    except Exception as exc:
        logger.error("trend_query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/failed-rules",
    response_model=APIResponse,
    summary="Active failures",
    description="Return latest active DQ failures from v_dq_failed_rules (last 7 days).",
)
async def get_failed_rules(_: str = Depends(verify_api_key)) -> APIResponse:
    try:
        agent = _get_reporting_agent()
        data = await agent.get_failed_rules()
        return APIResponse(success=True, data={"rules": data, "count": len(data)})
    except Exception as exc:
        logger.error("failed_rules_query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/freshness",
    response_model=APIResponse,
    summary="Freshness report",
    description="Return per-table freshness lag vs. SLA from v_dq_freshness_report.",
)
async def get_freshness(_: str = Depends(verify_api_key)) -> APIResponse:
    try:
        agent = _get_reporting_agent()
        data = await agent.get_freshness_report()
        return APIResponse(success=True, data={"tables": data, "count": len(data)})
    except Exception as exc:
        logger.error("freshness_query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    
@router.get(
    "/technical-health",
    response_model=APIResponse,
    summary="Technical DQ health",
    description="Health scores for technical rules only.",
)
async def get_technical_health(_: str = Depends(verify_api_key)) -> APIResponse:
    try:
        from tools.bigquery.client import get_bq_client
        settings = get_settings()
        bq = get_bq_client()
        sql = f"SELECT * FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.v_dq_technical_health`"
        data = await bq.execute_query(sql)
        return APIResponse(success=True, data={"tables": data, "count": len(data)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/business-health",
    response_model=APIResponse,
    summary="Business DQ health",
    description="Health scores for AI-generated business rules only.",
)
async def get_business_health(_: str = Depends(verify_api_key)) -> APIResponse:
    try:
        from tools.bigquery.client import get_bq_client
        settings = get_settings()
        bq = get_bq_client()
        sql = f"SELECT * FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.v_dq_business_health`"
        data = await bq.execute_query(sql)
        return APIResponse(success=True, data={"tables": data, "count": len(data)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/setup-views",
    response_model=APIResponse,
    summary="Create / refresh reporting views",
    description="Idempotently create or replace all v_dq_* reporting views in BigQuery.",
)
async def setup_views(_: str = Depends(verify_api_key)) -> APIResponse:
    try:
        agent = _get_reporting_agent()
        results = await agent.setup_views()
        ok = sum(results.values())
        return APIResponse(
            success=True,
            data={"views": results, "created": ok, "total": len(results)},
            message=f"{ok}/{len(results)} views created successfully",
        )
    except Exception as exc:
        logger.error("setup_views_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
