"""DAG orchestration — uploads generated DAG to GCS and triggers Cloud Composer."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
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

    def generate_dag_spec(
        self,
        session_id: str,
        sp_name: str,
        table_name: str,
        rules: list[dict[str, Any]],
        schedule: str,
        dq_project: str,
        dq_dataset: str,
    ) -> dict[str, Any]:
        """Generate a structured JSON DAG specification.

        This JSON spec describes the DAG structure — tasks, dependencies,
        SQL locations — before the Python DAG file is generated.
        This makes the DAG generation transparent and auditable.
        """
        stable_id = re.sub(r"[^a-zA-Z0-9_]", "_", table_name).lower() if table_name else session_id[:12]
        dag_id = f"dq_pipeline_{stable_id}"

        # Separate technical and business rules
        tech_rules = [r for r in rules if not r.get("rule_id", "").startswith("BRUL_")]
        biz_rules  = [r for r in rules if r.get("rule_id", "").startswith("BRUL_")]

        # Build task list
        tasks = [
            {
                "task_id": "execute_dq_stored_procedure",
                "type": "bigquery_stored_procedure",
                "description": f"Execute consolidated DQ stored procedure for all {len(rules)} rules",
                "sql": f"CALL `{dq_project}.{dq_dataset}.{sp_name}`('{{{{ run_id }}}}')",
                "sql_location": f"{dq_project}.{dq_dataset}.{sp_name}",
                "dependencies": [],
                "rules_included": len(rules),
            },
            {
                "task_id": "send_email_alert",
                "type": "python_callable",
                "description": "Query dq_results and send email alert if failures detected",
                "sql": f"SELECT * FROM `{dq_project}.{dq_dataset}.dq_results` WHERE run_id = '{{run_id}}' AND status = 'FAIL'",
                "sql_location": f"{dq_project}.{dq_dataset}.dq_results",
                "dependencies": ["execute_dq_stored_procedure"],
                "rules_included": 0,
            },
        ]

        # Build rule inventory with SQL locations
        rule_inventory = []
        for r in rules:
            rule_inventory.append({
                "rule_id": r.get("rule_id"),
                "rule_name": r.get("rule_name"),
                "severity": r.get("severity"),
                "rule_type": "business" if r.get("rule_id", "").startswith("BRUL_") else "technical",
                "sql_location": f"{dq_project}.{dq_dataset}.dq_rule_config",
                "sql_filter": f"rule_id = '{r.get('rule_id')}'",
            })

        spec = {
            "spec_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "dag_id": dag_id,
            "dag_filename": f"{dag_id}.py",
            "table_name": table_name,
            "stored_procedure": f"{dq_project}.{dq_dataset}.{sp_name}",
            "schedule": {
                "cron": schedule,
                "description": _cron_description(schedule),
                "timezone": "UTC",
            },
            "tasks": tasks,
            "task_dependencies": [
                {"from": "execute_dq_stored_procedure", "to": "send_email_alert"}
            ],
            "rules_summary": {
                "total": len(rules),
                "technical": len(tech_rules),
                "business": len(biz_rules),
                "results_table": f"{dq_project}.{dq_dataset}.dq_results",
                "rule_config_table": f"{dq_project}.{dq_dataset}.dq_rule_config",
            },
            "rule_inventory": rule_inventory,
            "infrastructure": {
                "project": dq_project,
                "dq_dataset": dq_dataset,
                "composer_bucket": self._settings.airflow.dag_bucket,
                "webserver_url": self._settings.airflow.webserver_url,
            },
        }

        self._log.info(
            "dag_spec_generated",
            dag_id=dag_id,
            tasks=len(tasks),
            rules=len(rules),
            session_id=session_id,
        )
        return spec

    async def store_dag_spec(
        self,
        spec: dict[str, Any],
        session_id: str,
    ) -> None:
        """Store the DAG spec JSON in BigQuery for audit and visibility."""
        from tools.bigquery.client import get_bq_client
        settings = get_settings()
        bq = get_bq_client()
        table_id = f"{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_dag_specs"

        try:
            rows = [{
                "session_id": session_id,
                "dag_id": spec["dag_id"],
                "table_name": spec.get("table_name", ""),
                "spec_json": json.dumps(spec),
                "generated_at": spec["generated_at"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }]
            await bq.insert_rows(table_id, rows)
            self._log.info("dag_spec_stored", session_id=session_id, dag_id=spec["dag_id"])
        except Exception as exc:
            self._log.warning("dag_spec_store_failed", error=str(exc)[:200])

    async def get_dag_spec(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve the DAG spec for a session from BigQuery."""
        from tools.bigquery.client import get_bq_client
        settings = get_settings()
        bq = get_bq_client()

        try:
            sql = f"""
                SELECT spec_json
                FROM `{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_dag_specs`
                WHERE session_id = '{session_id}'
                ORDER BY created_at DESC
                LIMIT 1
            """
            rows = await bq.execute_query(sql)
            if rows:
                val = rows[0]["spec_json"]
                # BQ may return already-parsed dict or a string
                if isinstance(val, dict):
                    return val
                return json.loads(val)
        except Exception as exc:
            self._log.warning("dag_spec_fetch_failed", error=str(exc)[:200])
        return None

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

        # Use table name for stable DAG ID
        table_name = rules[0].get("table_name", "") if rules else ""
        stable_id = re.sub(r"[^a-zA-Z0-9_]", "_", table_name).lower() if table_name else session_id[:12]
        dag_id = f"dq_pipeline_{stable_id}"
        dag_filename = f"{dag_id}.py"

        # Read email credentials from environment
        alert_email = os.getenv("ALERT_EMAIL_TO", "")
        smtp_host   = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port   = int(os.getenv("SMTP_PORT", "587"))
        smtp_user   = os.getenv("SMTP_USERNAME", "")
        smtp_pass   = os.getenv("SMTP_PASSWORD", "")

        # --- 0. Generate JSON DAG spec first ---
        if use_consolidated and sp_name:
            spec = self.generate_dag_spec(
                session_id=session_id,
                sp_name=sp_name,
                table_name=table_name,
                rules=rules,
                schedule=schedule,
                dq_project=gcp.project_id,
                dq_dataset=gcp.dq_dataset,
            )
            # Store spec in BigQuery for audit
            await self.store_dag_spec(spec, session_id)

        # --- 1. Build DAG content from spec ---
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
            "dag_spec": spec if use_consolidated and sp_name else None,
        }


def _cron_description(cron: str) -> str:
    """Convert cron expression to human-readable description."""
    descriptions = {
        "0 6 * * *":   "Daily at 6:00 AM UTC",
        "0 * * * *":   "Every hour",
        "0 */6 * * *": "Every 6 hours",
        "0 7 * * 1":   "Every Monday at 7:00 AM UTC",
        "0 8 1 * *":   "1st of every month at 8:00 AM UTC",
    }
    return descriptions.get(cron, f"Custom schedule: {cron}")