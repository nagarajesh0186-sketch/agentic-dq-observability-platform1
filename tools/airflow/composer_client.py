"""Cloud Composer / Airflow REST API client — Google IAP (OAuth) authentication."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.settings import get_settings

logger = structlog.get_logger(__name__)


def _get_identity_token() -> str:
    """Fetch a fresh Google identity token using google-auth library.

    Works on all platforms (Windows/Mac/Linux) using application default
    credentials set via: gcloud auth application-default login
    No gcloud CLI needed at runtime.
    """
    try:
        import google.auth
        import google.auth.transport.requests
        from google.oauth2 import id_token

        # Get application default credentials
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # Refresh credentials to get a valid token
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)

        # Return the access token (works for Composer REST API)
        token = credentials.token
        if not token:
            raise RuntimeError("google-auth returned empty token")
        return token

    except Exception as exc:
        raise RuntimeError(
            f"Failed to get identity token via google-auth: {exc}"
        ) from exc


class AirflowClient:
    """Async Airflow REST API client for Cloud Composer with IAP/OAuth authentication."""

    def __init__(
        self,
        webserver_url: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (webserver_url or settings.airflow.webserver_url).rstrip("/")
        self._api_url = f"{self._base_url}/api/v1"
        self._log = logger.bind(base_url=self._base_url)

    def _headers(self) -> dict[str, str]:
        """Return auth headers using a fresh IAP identity token."""
        token = _get_identity_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def trigger_dag(self, dag_id: str, conf: Optional[dict[str, Any]] = None) -> str:
        """Trigger a DAG run and return the run_id."""
        url = f"{self._api_url}/dags/{dag_id}/dagRuns"
        payload: dict[str, Any] = {"conf": conf or {}}

        headers = await asyncio.to_thread(self._headers)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                run_id = data.get("dag_run_id", "")
                self._log.info("dag_triggered", dag_id=dag_id, run_id=run_id)
                return run_id

    async def get_dag_run_status(self, dag_id: str, run_id: str) -> str:
        """Return the state of a specific DAG run."""
        url = f"{self._api_url}/dags/{dag_id}/dagRuns/{run_id}"
        headers = await asyncio.to_thread(self._headers)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    return "not_found"
                resp.raise_for_status()
                data = await resp.json()
                return data.get("state", "unknown")

    async def upload_dag_file(
        self, dag_content: str, dag_filename: str, gcs_bucket: Optional[str] = None
    ) -> None:
        """Upload a DAG file to the GCS bucket backing Cloud Composer."""
        settings = get_settings()
        bucket = (gcs_bucket or settings.airflow.dag_bucket or "").strip()

        if not bucket:
            self._log.warning("dag_bucket_not_configured", filename=dag_filename)
            return

        from google.cloud import storage  # type: ignore[import]

        def _upload() -> None:
            client = storage.Client()
            bucket_name = bucket.replace("gs://", "").split("/")[0]
            prefix = "/".join(bucket.replace("gs://", "").split("/")[1:])
            blob_path = f"{prefix}/dags/{dag_filename}" if prefix else f"dags/{dag_filename}"
            bucket_obj = client.bucket(bucket_name)
            blob = bucket_obj.blob(blob_path)
            blob.upload_from_string(dag_content, content_type="text/x-python")
            logger.info("dag_uploaded", filename=dag_filename, bucket=bucket_name, path=blob_path)

        await asyncio.to_thread(_upload)
        self._log.info("dag_upload_complete", filename=dag_filename, bucket=bucket)

    async def list_dags(self) -> list[dict[str, Any]]:
        """Return a list of all DAGs registered in Airflow."""
        url = f"{self._api_url}/dags?limit=100"
        headers = await asyncio.to_thread(self._headers)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("dags", [])

    async def pause_dag(self, dag_id: str, is_paused: bool = True) -> bool:
        """Pause or unpause a DAG."""
        url = f"{self._api_url}/dags/{dag_id}"
        payload = {"is_paused": is_paused}
        headers = await asyncio.to_thread(self._headers)
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=payload, headers=headers) as resp:
                return resp.status == 200
