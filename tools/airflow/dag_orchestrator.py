"""DAG orchestration — uploads generated DAG to GCS and triggers Cloud Composer."""

from __future__ import annotations

import os
import re
from typing import Any

import structlog

from configs.settings import get_settings
from tools.airflow.composer_client import AirflowClient
from tools.airflow.dag_builder import generate_consolidated_sp_dag, generate_standalone_dag

logger = structlog.get_logger(__name__)


class DAGOrchestrator:
    """Handles end-to-end DAG lifecycle: build → upload → trigger."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AirflowClient()
        self._settings = settings
        self._log = logger.bind(component="DAGOrchestrator")

    async def deploy_and_trigger(
        self,
        session_id: str,
        rules: list[dict[str, Any]],
        sp_name: str | None = None,
        schedule: str = "0 6 * * *",
        use_consolidated: bool = True,
    ) -> dict[str, Any]:
        """Build DAG, upload to GCS bucket, trigger Composer, return run info."""
        settings = get_settings()
        gcp = settings.gcp

        # Use table name for stable DAG ID — one DAG per table, not per session
        table_name = rules[0].get("table_name", "") if rules else ""
        stable_id = re.sub(r"[^a-zA-Z0-9_]", "_", table_name).lower() if table_name else session_id[:12]
        dag_id = f"dq_pipeline_{stable_id}"
        dag_filename = f"{dag_id}.py"

        # Read email credentials from environment for embedding in DAG
        alert_email = os.getenv("ALERT_EMAIL_TO", "")
        smtp_host   = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port   = int(os.getenv("SMTP_PORT", "587"))
        smtp_user   = os.getenv("SMTP_USERNAME", "")
        smtp_pass   = os.getenv("SMTP_PASSWORD", "")

        # --- 1. Build DAG content ---
        if use_consolidated and sp_name:
            self._log.info("building_consolidated_dag", session_id=session_id, sp=sp_name, table=table_name)
            dag_content = generate_consolidated_sp_dag(
                session_id=session_id,
                sp_name=sp_name,
                dq_project=gcp.project_id,
                dq_dataset=gcp.dq_dataset,
                table_name=table_name,
                schedule=schedule,
                alert_email=alert_email,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_pass=smtp_pass,
            )
        else:
            self._log.info("building_standalone_dag", session_id=session_id, rules=len(rules))
            dag_content = generate_standalone_dag(
                session_id=session_id,
                rules=rules,
                schedule=schedule,
                gcp_project=gcp.project_id,
                gcp_dataset=gcp.dataset_id,
                dq_dataset=gcp.dq_dataset,
            )

        # --- 2. Upload DAG file to Composer GCS bucket ---
        bucket = settings.airflow.dag_bucket
        if not bucket:
            self._log.warning("dag_bucket_not_set_skipping_upload")
        else:
            self._log.info("uploading_dag", filename=dag_filename, bucket=bucket, dag_id=dag_id)
            await self._client.upload_dag_file(
                dag_content=dag_content,
                dag_filename=dag_filename,
                gcs_bucket=bucket,
            )
            self._log.info("dag_uploaded_successfully", filename=dag_filename)

        # --- 3. Trigger Composer DAG run ---
        run_id = ""
        try:
            self._log.info("triggering_dag", dag_id=dag_id)
            run_id = await self._client.trigger_dag(
                dag_id=dag_id,
                conf={
                    "session_id": session_id,
                    "triggered_by": "dq_platform_approval",
                },
            )
            self._log.info("dag_triggered_successfully", dag_id=dag_id, run_id=run_id)
        except Exception as exc:
            self._log.warning(
                "dag_trigger_failed_will_run_on_schedule",
                dag_id=dag_id,
                error=str(exc)[:200],
            )

        return {
            "dag_id": dag_id,
            "dag_filename": dag_filename,
            "run_id": run_id,
            "bucket": bucket,
            "status": "triggered" if run_id else "uploaded_pending_schedule",
        }
