"""Alerting Agent — severity-aware alert routing to Slack and email."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from schemas.models import AlertConfig, DQResult, Severity
from tools.alerts.email import EmailAlerter
from tools.alerts.slack import SlackAlerter

logger = structlog.get_logger(__name__)

_SEVERITY_ORDER = {"INFO": 0, "WARN": 1, "FAIL": 2}


class AlertingAgent:
    """Routes DQ failures to Slack and email with severity-aware escalation."""

    def __init__(self) -> None:
        self._slack = SlackAlerter()
        self._email = EmailAlerter()
        self._log = logger.bind(agent="AlertingAgent")

    async def run(
        self,
        failures: list[DQResult],
        alert_config: AlertConfig,
        table_name: str,
        run_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Evaluate failures and send alerts if severity threshold is met."""
        if not failures:
            return {"alerts_sent": 0, "failures": 0}

        min_severity = alert_config.min_severity_to_alert
        min_level = _SEVERITY_ORDER.get(min_severity.value, 1)

        alertable = [
            f for f in failures
            if _SEVERITY_ORDER.get(f.severity.value, 0) >= min_level
        ]

        if not alertable:
            self._log.info("no_alertable_failures", total_failures=len(failures))
            return {"alerts_sent": 0, "failures": len(failures)}

        # Determine highest severity
        max_severity = max(alertable, key=lambda f: _SEVERITY_ORDER.get(f.severity.value, 0)).severity
        title = f"DQ Alert [{max_severity.value}] — {table_name}"
        message = (
            f"{len(alertable)} rule(s) failed for table `{table_name}`. "
            f"Run ID: {run_id}. "
            f"Highest severity: {max_severity.value}."
        )

        failure_dicts = [
            {
                "rule_id": f.rule_id,
                "rule_type": f.rule_type,
                "severity": f.severity.value,
                "status": f.status.value,
                "observed_value": f.observed_value,
                "column_name": f.column_name,
            }
            for f in alertable[:20]
        ]

        alerts_sent = 0

        if alert_config.slack_enabled:
            try:
                await self._slack.send_alert(
                    title=title,
                    message=message,
                    severity=max_severity.value,
                    table_name=table_name,
                    rule_ids=[f.rule_id for f in alertable[:10]],
                    run_id=run_id,
                    failure_count=len(alertable),
                )
                alerts_sent += 1
            except Exception as exc:
                self._log.error("slack_alert_failed", error=str(exc))

        if alert_config.email_enabled:
            try:
                await self._email.send_alert(
                    subject=title,
                    title=title,
                    message=message,
                    severity=max_severity.value,
                    table_name=table_name,
                    failures=failure_dicts,
                    recipients=alert_config.email_recipients,
                    run_id=run_id,
                )
                alerts_sent += 1
            except Exception as exc:
                self._log.error("email_alert_failed", error=str(exc))

        return {
            "alerts_sent": alerts_sent,
            "alertable_failures": len(alertable),
            "total_failures": len(failures),
            "max_severity": max_severity.value,
            "timestamp": datetime.utcnow().isoformat(),
        }
