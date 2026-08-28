"""Slack webhook integration for alert notifications."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SlackClient:
    """Client for posting alert messages to Slack via incoming webhooks."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_alert(
        self,
        alert_id: str,
        severity: str,
        title: str,
        message: str,
        source_service: str = "",
        channel_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a formatted alert message to Slack."""
        color = self._severity_color(severity)
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"[{severity.upper()}] {title}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
                    {"type": "mrkdwn", "text": f"*Source:*\n{source_service}"},
                    {"type": "mrkdwn", "text": f"*Channel:*\n{channel_id or 'N/A'}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
        ]

        if metadata:
            meta_text = "\n".join(f"• *{k}:* {v}" for k, v in metadata.items())
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Metadata:*\n{meta_text}"},
            })

        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ]
        }

        client = await self._get_client()
        try:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Slack alert sent: %s", alert_id)
            return {"sent": True, "channel": "slack", "alert_id": alert_id}
        except httpx.HTTPStatusError as exc:
            logger.error("Slack send failed: %s - %s", exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("Slack unexpected error: %s", exc)
            raise

    def _severity_color(self, severity: str) -> str:
        colors = {
            "info": "#36a64f",
            "warning": "#ff9900",
            "error": "#ff0000",
            "critical": "#990000",
        }
        return colors.get(severity.lower(), "#808080")
