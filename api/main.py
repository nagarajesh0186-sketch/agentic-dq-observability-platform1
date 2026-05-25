"""FastAPI application entrypoint for the Agentic DQ Observability Platform."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from google.auth.exceptions import DefaultCredentialsError, TransportError

from api.routers import approvals, discovery, monitoring, reporting, rules, sql
from configs.logging_config import configure_logging
from configs.settings import get_settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    logger.info("application_startup", environment=settings.environment, version="1.0.0")

    if settings.gcp.project_id and settings.gcp.dq_dataset:
        try:
            from tools.bigquery.client import get_bq_client
            from tools.bigquery.setup import ensure_dq_tables, ensure_dq_views

            bq = get_bq_client()
            table_results = await ensure_dq_tables(bq, settings.gcp.project_id, settings.gcp.dq_dataset)
            view_results = await ensure_dq_views(bq, settings.gcp.project_id, settings.gcp.dq_dataset)
            logger.info(
                "bq_infrastructure_ready",
                tables_ok=sum(table_results.values()),
                views_ok=sum(view_results.values()),
            )
        except Exception as exc:
            logger.warning("bq_setup_skipped", error=str(exc))
    else:
        logger.warning("bq_setup_skipped", reason="GCP_PROJECT_ID or GCP_DQ_DATASET not configured")

    yield
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Agentic DQ Observability Platform",
        description=(
            "Production-grade AI-powered Data Quality & Observability Platform "
            "using Gemini API, BigQuery, and multi-agent orchestration."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(discovery.router, prefix="/api/v1/discovery", tags=["Discovery"])
    app.include_router(rules.router, prefix="/api/v1/rules", tags=["Rules"])
    app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["Approvals"])
    app.include_router(sql.router, prefix="/api/v1/sql", tags=["SQL"])
    app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])
    app.include_router(reporting.router, prefix="/api/v1/reporting", tags=["Reporting"])

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": "1.0.0"}

    @app.exception_handler(DefaultCredentialsError)
    async def gcp_credentials_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.warning("gcp_credentials_missing", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error": "GCP credentials not configured",
                "detail": (
                    "Google Cloud credentials are required for this endpoint. "
                    "Run: gcloud auth application-default login"
                ),
            },
        )

    @app.exception_handler(TransportError)
    async def gcp_transport_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.warning("gcp_transport_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error": "GCP credentials not configured",
                "detail": (
                    "Google Cloud credentials are required for this endpoint. "
                    "Run: gcloud auth application-default login"
                ),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "Internal server error", "detail": str(exc)},
        )

    return app


app = create_app()
