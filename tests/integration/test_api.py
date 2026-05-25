"""Integration tests for the FastAPI application."""

from __future__ import annotations

import os
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

# Skip integration tests if no real GCP credentials are available
pytestmark = pytest.mark.integration


@pytest.fixture
def api_key():
    return os.environ.get("API_KEY", "test-api-key")


@pytest.fixture
def mock_settings():
    with patch("configs.settings.get_settings") as mock:
        settings = MagicMock()
        settings.api_key = "test-api-key"
        settings.log_level = "DEBUG"
        settings.environment = "testing"
        settings.gcp.project_id = "test-project"
        settings.gcp.dq_dataset = "test_dq"
        settings.gcp.dataplex_enabled = False
        settings.gemini.api_key = "test-key"
        settings.gemini.model = "gemini-1.5-flash"
        settings.slack.webhook_url = None
        settings.email.sendgrid_api_key = None
        mock.return_value = settings
        yield settings


@pytest.fixture
async def async_client(mock_settings):
    from api.main import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


class TestHealthEndpoint:
    async def test_health_check(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestDiscoveryEndpoints:
    async def test_missing_api_key_returns_403(self, async_client):
        response = await async_client.post(
            "/api/v1/discovery/start",
            json={"project_id": "p", "dataset_id": "d", "table_names": ["t"]},
        )
        assert response.status_code == 403

    async def test_get_nonexistent_session_returns_404(self, async_client, api_key):
        response = await async_client.get(
            "/api/v1/discovery/nonexistent-session",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404


class TestRulesEndpoints:
    async def test_get_rules_missing_session(self, async_client, api_key):
        response = await async_client.get(
            "/api/v1/rules/nonexistent",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404


class TestApprovalEndpoints:
    async def test_get_approval_missing_session(self, async_client, api_key):
        response = await async_client.get(
            "/api/v1/approvals/nonexistent",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404
