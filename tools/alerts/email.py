"""Email alerting via SendGrid with Gmail SMTP fallback."""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional
from dotenv import load_dotenv
load_dotenv()

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.settings import get_settings

logger = structlog.get_logger(__name__)

_SEVERITY_BADGE_COLORS = {
    "FAIL": "#dc3545",
    "WARN": "#ffc107",
    "INFO": "#28a745",
}


class EmailAlerter:
    """Send DQ alerts via email using SendGrid or Gmail SMTP fallback."""

    def __init__(
        self,
        sendgrid_api_key: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = sendgrid_api_key or settings.email.sendgrid_api_key
        self._from_email = from_email or settings.email.from_email
        self._log = logger

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=60),
        reraise=True,
    )
    async def send_alert(
        self,
        subject: str,
        title: str,
        message: str,
        severity: str,
        table_name: str,
        failures: Optional[list[dict[str, Any]]] = None,
        recipients: Optional[list[str]] = None,
        run_id: Optional[str] = None,
    ) -> bool:
        """Send an HTML DQ alert email. Returns True on success."""
        settings = get_settings()
        to_emails = recipients or settings.email.to_email_list

        if not to_emails:
            self._log.warning("email_no_recipients")
            return False

        html_body = self._build_html_body(
            title=title,
            message=message,
            severity=severity,
            table_name=table_name,
            failures=failures or [],
            run_id=run_id or "N/A",
        )

        # Use SendGrid if API key is set, otherwise fall back to Gmail SMTP
        if self._api_key and self._api_key.startswith("SG."):
            return await self._send_via_sendgrid(subject, html_body, to_emails)
        return await self._send_via_gmail_smtp(subject, html_body, to_emails)

    async def _send_via_sendgrid(
        self, subject: str, html_body: str, to_emails: list[str]
    ) -> bool:
        try:
            from sendgrid import SendGridAPIClient  # type: ignore[import]
            from sendgrid.helpers.mail import Mail, To  # type: ignore[import]

            message = Mail(
                from_email=self._from_email,
                subject=subject,
                html_content=html_body,
            )
            message.to = [To(email=e) for e in to_emails]

            client = SendGridAPIClient(api_key=self._api_key)
            response = await asyncio.to_thread(client.send, message)
            success = 200 <= response.status_code < 300
            self._log.info("email_sent_sendgrid", status=response.status_code, success=success)
            return success
        except Exception as exc:
            self._log.error("sendgrid_error", error=str(exc))
            return False

    async def _send_via_gmail_smtp(
        self, subject: str, html_body: str, to_emails: list[str]
    ) -> bool:
        """Send via Gmail SMTP using app password from .env."""
        import os

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USERNAME", self._from_email)
        smtp_pass = os.getenv("SMTP_PASSWORD", "")

        if not smtp_pass:
            self._log.warning("smtp_password_not_set")
            return False

        def _send() -> bool:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self._from_email
            msg["To"]      = ", ".join(to_emails)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(smtp_user, smtp_pass)
                smtp.sendmail(self._from_email, to_emails, msg.as_string())
            return True

        try:
            result = await asyncio.to_thread(_send)
            self._log.info("email_sent_gmail_smtp", recipients=to_emails)
            return result
        except Exception as exc:
            self._log.error("smtp_error", error=str(exc))
            return False

    def _build_html_body(
        self,
        title: str,
        message: str,
        severity: str,
        table_name: str,
        failures: list[dict[str, Any]],
        run_id: str,
    ) -> str:
        color = _SEVERITY_BADGE_COLORS.get(severity, "#6c757d")
        failures_html = ""
        if failures:
            rows = "".join(
                f"<tr>"
                f"<td style='padding:6px;border:1px solid #dee2e6'>{f.get('rule_id','')}</td>"
                f"<td style='padding:6px;border:1px solid #dee2e6'>{f.get('rule_type','')}</td>"
                f"<td style='padding:6px;border:1px solid #dee2e6;color:{color}'>{f.get('severity','')}</td>"
                f"<td style='padding:6px;border:1px solid #dee2e6'>{f.get('observed_value','')}</td>"
                f"</tr>"
                for f in failures[:20]
            )
            failures_html = f"""
            <h3 style='color:#343a40'>Failed Rules</h3>
            <table style='border-collapse:collapse;width:100%;font-size:13px'>
                <thead>
                    <tr style='background:{color};color:white'>
                        <th style='padding:8px;text-align:left'>Rule ID</th>
                        <th style='padding:8px;text-align:left'>Type</th>
                        <th style='padding:8px;text-align:left'>Severity</th>
                        <th style='padding:8px;text-align:left'>Observed Value</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            """

        return f"""<!DOCTYPE html>
<html>
<head><meta charset='utf-8'></head>
<body style='font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#343a40'>
    <div style='background:{color};color:white;padding:16px 20px;border-radius:6px 6px 0 0'>
        <h2 style='margin:0'>Data Quality Alert — {severity}</h2>
    </div>
    <div style='border:1px solid #dee2e6;border-top:none;padding:20px;border-radius:0 0 6px 6px'>
        <h3 style='color:#343a40;margin-top:0'>{title}</h3>
        <p style='color:#6c757d'>{message}</p>
        <table style='border-collapse:collapse;width:100%;font-size:13px;margin-bottom:16px'>
            <tr>
                <td style='padding:6px;font-weight:bold;width:30%'>Table</td>
                <td style='padding:6px'><code>{table_name}</code></td>
            </tr>
            <tr style='background:#f8f9fa'>
                <td style='padding:6px;font-weight:bold'>Run ID</td>
                <td style='padding:6px'><code>{run_id}</code></td>
            </tr>
            <tr>
                <td style='padding:6px;font-weight:bold'>Severity</td>
                <td style='padding:6px'>
                    <span style='background:{color};color:white;padding:2px 8px;border-radius:3px'>{severity}</span>
                </td>
            </tr>
        </table>
        {failures_html}
        <hr style='border:none;border-top:1px solid #dee2e6;margin:20px 0'>
        <p style='font-size:12px;color:#6c757d'>
            This alert was generated by the Agentic DQ Observability Platform powered by Claude AI.
        </p>
    </div>
</body>
</html>"""