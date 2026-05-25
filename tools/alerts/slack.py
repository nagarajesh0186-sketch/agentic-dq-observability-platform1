"""Slack alerting with Block Kit formatting and severity-aware color coding."""

from __future__ import annotations

from typing import Any, Optional

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.settings import get_settings

logger = structlog.get_logger(__name__)

_SEVERITY_COLORS = {
    "FAIL": "danger",
    "WARN": "warning",
    "INFO": "good",
}

_SEVERITY_EMOJI = {
    "FAIL": ":red_circle:",
    "WARN": ":large_yellow_circle:",
    "INFO": ":large_green_circle:",
}


class SlackAlerter:
    """Send DQ alerts to Slack using webhooks or the Web API."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._webhook_url = webhook_url or settings.slack.webhook_url
        self._bot_token = bot_token or settings.slack.bot_token
        self._channel = channel or settings.slack.channel
        self._log = logger

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=30),
        reraise=True,
    )
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        table_name: str,
        rule_ids: Optional[list[str]] = None,
        run_id: Optional[str] = None,
        failure_count: int = 0,
    ) -> bool:
        """Send a formatted DQ alert to Slack. Returns True on success."""
        if not self._webhook_url and not self._bot_token:
            self._log.warning("slack_not_configured")
            return False

        blocks = self._build_blocks(
            title=title,
            message=message,
            severity=severity,
            table_name=table_name,
            rule_ids=rule_ids or [],
            run_id=run_id or "N/A",
            failure_count=failure_count,
        )

        payload = {
            "text": f"{_SEVERITY_EMOJI.get(severity, '')} {title}",
            "attachments": [
                {
                    "color": _SEVERITY_COLORS.get(severity, "good"),
                    "blocks": blocks,
                }
            ],
        }

        if self._webhook_url:
            return await self._send_via_webhook(payload)
        return await self._send_via_api(payload)

    async def _send_via_webhook(self, payload: dict[str, Any]) -> bool:
        try:
            from slack_sdk.webhook.async_client import AsyncWebhookClient  # type: ignore[import]
            client = AsyncWebhookClient(url=self._webhook_url)
            response = await client.send_dict(payload)
            success = response.status_code == 200
            if success:
                self._log.info("slack_alert_sent_webhook")
            else:
                self._log.error("slack_webhook_failed", status=response.status_code, body=response.body)
            return success
        except Exception as exc:
            self._log.error("slack_webhook_error", error=str(exc))
            return False

    async def _send_via_api(self, payload: dict[str, Any]) -> bool:
        try:
            from slack_sdk.web.async_client import AsyncWebClient  # type: ignore[import]
            client = AsyncWebClient(token=self._bot_token)
            response = await client.chat_postMessage(channel=self._channel, **payload)
            success = response.get("ok", False)
            if success:
                self._log.info("slack_alert_sent_api")
            else:
                self._log.error("slack_api_failed", error=response.get("error"))
            return bool(success)
        except Exception as exc:
            self._log.error("slack_api_error", error=str(exc))
            return False

    def _build_blocks(
        self,
        title: str,
        message: str,
        severity: str,
        table_name: str,
        rule_ids: list[str],
        run_id: str,
        failure_count: int,
    ) -> list[dict[str, Any]]:
        emoji = _SEVERITY_EMOJI.get(severity, "")
        rules_text = ", ".join(f"`{r}`" for r in rule_ids[:5]) if rule_ids else "_None_"
        if len(rule_ids) > 5:
            rules_text += f" +{len(rule_ids) - 5} more"

        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {title}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*Table:*\n`{table_name}`"},
                    {"type": "mrkdwn", "text": f"*Failed Rules:*\n{failure_count}"},
                    {"type": "mrkdwn", "text": f"*Run ID:*\n`{run_id}`"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Affected Rules:*\n{rules_text}"},
            },
            {"type": "divider"},
        ]
