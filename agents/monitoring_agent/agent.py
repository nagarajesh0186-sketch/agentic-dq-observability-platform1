"""Monitoring Agent — SLA tracking, freshness, anomaly detection, health scoring."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import structlog

from agents.base import BaseAgent
from configs.settings import get_settings
from prompts.monitoring_agent import (
    MONITORING_SYSTEM_PROMPT_V1,
    SLA_RECOMMENDATION_PROMPT_V1,
)
from schemas.models import AlertConfig, DQRunResult, MonitoringConfig
from tools.alerts.email import EmailAlerter
from tools.alerts.slack import SlackAlerter
from tools.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)


class MonitoringAgent(BaseAgent):
    """Monitors DQ health, detects anomalies, and routes alerts."""

    def __init__(self, bq_client: BigQueryClient) -> None:
        super().__init__(
            agent_name="MonitoringAgent",
            system_prompt=MONITORING_SYSTEM_PROMPT_V1,
        )
        self._bq_client = bq_client
        settings = get_settings()
        self._slack = SlackAlerter()
        self._email = EmailAlerter()
        self._dq_project = settings.gcp.project_id
        self._dq_dataset = settings.gcp.dq_dataset

    async def run(
        self,
        session_id: str,
        run_result: DQRunResult,
        monitoring_config: MonitoringConfig,
    ) -> dict[str, Any]:
        """Evaluate a DQ run result against monitoring config and fire alerts if needed."""
        self._log.info(
            "monitoring_evaluation_start",
            session_id=session_id,
            run_id=run_result.run_id,
            health_score=run_result.health_score,
        )

        breaches: list[dict[str, Any]] = []

        # SLA breach checks
        if run_result.health_score < monitoring_config.health_score_min * 100:
            breaches.append({
                "type": "health_score",
                "observed": run_result.health_score,
                "threshold": monitoring_config.health_score_min * 100,
                "severity": "FAIL",
            })

        if run_result.failed > 0:
            breaches.append({
                "type": "rule_failures",
                "observed": run_result.failed,
                "threshold": 0,
                "severity": "FAIL" if run_result.failed > 5 else "WARN",
            })

        # Fire alerts if breaches found and alerting configured
        if breaches and monitoring_config.alert_config:
            await self._fire_alerts(
                session_id, run_result, monitoring_config, breaches
            )

        return {
            "session_id": session_id,
            "run_id": run_result.run_id,
            "health_score": run_result.health_score,
            "pass_rate": run_result.pass_rate,
            "breaches": breaches,
            "alerts_fired": len(breaches) > 0 and bool(monitoring_config.alert_config),
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    async def recommend_monitoring_config(
        self,
        session_id: str,
        table_name: str,
        row_count: int,
        partition_column: str | None,
    ) -> MonitoringConfig:
        """Use Claude to recommend monitoring configuration for a table."""
        prompt = SLA_RECOMMENDATION_PROMPT_V1.format(
            table_name=table_name,
            row_count=row_count,
            partition_column=partition_column or "none",
            update_frequency="daily",
            business_criticality="medium",
            dq_history_json="[]",
        )

        try:
            result = await self._call_claude_json(prompt)
            settings = get_settings()
            alert_config = AlertConfig(
                slack_enabled=bool(settings.slack.webhook_url),
                slack_webhook_url=settings.slack.webhook_url,
                email_enabled=bool(settings.email.sendgrid_api_key),
                email_recipients=settings.email.to_email_list,
                min_severity_to_alert="WARN",  # type: ignore[arg-type]
            )

            return MonitoringConfig(
                session_id=session_id,
                table_name=table_name,
                sla_check_frequency=result.get("monitoring_schedule_cron", "0 * * * *"),
                freshness_lag_max_hours=float(result.get("freshness_sla_hours", 24.0)),
                volume_drop_threshold_pct=0.3,
                volume_spike_threshold_pct=2.0,
                health_score_min=float(result.get("min_pass_rate_pct", 80)) / 100,
                monitoring_schedule=result.get("monitoring_schedule_cron", "0 * * * *"),
                alert_config=alert_config,
            )
        except Exception as exc:
            self._log.error("monitoring_config_recommendation_failed", error=str(exc))
            settings = get_settings()
            return MonitoringConfig(
                session_id=session_id,
                table_name=table_name,
                alert_config=AlertConfig(
                    slack_enabled=bool(settings.slack.webhook_url),
                    email_enabled=bool(settings.email.sendgrid_api_key),
                ),
            )

    async def _fire_alerts(
        self,
        session_id: str,
        run_result: DQRunResult,
        config: MonitoringConfig,
        breaches: list[dict[str, Any]],
    ) -> None:
        """Route alerts to Slack and/or email based on configuration."""
        severity = max((b["severity"] for b in breaches), key=lambda s: {"INFO": 0, "WARN": 1, "FAIL": 2}.get(s, 0))
        title = f"DQ Alert — {config.table_name} — {severity}"
        message = (
            f"Health score: {run_result.health_score:.1f}/100. "
            f"Failed rules: {run_result.failed}. "
            f"Pass rate: {run_result.pass_rate:.1%}."
        )

        alert_cfg = config.alert_config

        if alert_cfg.slack_enabled:
            try:
                await self._slack.send_alert(
                    title=title,
                    message=message,
                    severity=severity,
                    table_name=config.table_name,
                    run_id=run_result.run_id,
                    failure_count=run_result.failed,
                )
            except Exception as exc:
                self._log.error("slack_alert_failed", error=str(exc))

        if alert_cfg.email_enabled:
            try:
                await self._email.send_alert(
                    subject=title,
                    title=title,
                    message=message,
                    severity=severity,
                    table_name=config.table_name,
                    recipients=alert_cfg.email_recipients,
                    run_id=run_result.run_id,
                )
            except Exception as exc:
                self._log.error("email_alert_failed", error=str(exc))
