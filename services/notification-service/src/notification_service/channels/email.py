"""SMTP email integration for alert notifications."""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib

logger = logging.getLogger(__name__)


class EmailClient:
    """Async SMTP client for sending alert emails."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str = "alerts@sentraaura.com",
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.use_tls = use_tls

    async def send_alert(
        self,
        alert_id: str,
        severity: str,
        title: str,
        message: str,
        recipients: list[str],
        source_service: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an alert email to the specified recipients."""
        if not recipients:
            logger.warning("No recipients for email alert %s", alert_id)
            return {"sent": False, "reason": "no_recipients"}

        subject = f"[SentraAura {severity.upper()}] {title}"
        body = self._build_html_body(alert_id, severity, title, message, source_service, metadata)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
            logger.info("Email alert sent to %d recipients: %s", len(recipients), alert_id)
            return {"sent": True, "channel": "email", "recipients": len(recipients), "alert_id": alert_id}
        except Exception as exc:
            logger.error("Email send failed for alert %s: %s", alert_id, exc)
            raise

    def _build_html_body(
        self,
        alert_id: str,
        severity: str,
        title: str,
        message: str,
        source_service: str,
        metadata: dict[str, Any] | None,
    ) -> str:
        meta_rows = ""
        if metadata:
            for k, v in metadata.items():
                meta_rows += f"<tr><td><b>{k}</b></td><td>{v}</td></tr>\n"

        return f"""<!DOCTYPE html>
<html>
<head><style>
body {{ font-family: Arial, sans-serif; }}
.header {{ background: #1a1a2e; color: #fff; padding: 20px; }}
.content {{ padding: 20px; }}
.meta {{ background: #f4f4f4; padding: 15px; margin-top: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
</style></head>
<body>
<div class="header">
<h2>[{severity.upper()}] {title}</h2>
<p>Alert ID: {alert_id} | Source: {source_service}</p>
</div>
<div class="content">
<p>{message}</p>
</div>
<div class="meta">
<h3>Metadata</h3>
<table>
{meta_rows}
</table>
</div>
</body>
</html>"""
