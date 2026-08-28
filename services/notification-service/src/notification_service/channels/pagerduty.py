"""PagerDuty integration for critical alerts."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PagerDutyClient:
    """Client for PagerDuty Events API v2."""

    EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"

    def __init__(self, routing_key: str) -> None:
        self.routing_key = routing_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def trigger_incident(
        self,
        alert_id: str,
        title: str,
        message: str,
        severity: str = "critical",
        source_service: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger a PagerDuty incident."""
        payload = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": alert_id,
            "payload": {
                "summary": title,
                "severity": severity,
                "source": source_service,
                "custom_details": metadata or {},
            },
        }
        client = await self._get_client()
        try:
            response = await client.post(self.EVENTS_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("PagerDuty incident triggered: %s", data.get("dedup_key"))
            return data
        except httpx.HTTPStatusError as exc:
            logger.error("PagerDuty trigger failed: %s - %s", exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("PagerDuty unexpected error: %s", exc)
            raise

    async def resolve_incident(self, alert_id: str) -> dict[str, Any]:
        """Resolve a previously triggered incident."""
        payload = {
            "routing_key": self.routing_key,
            "event_action": "resolve",
            "dedup_key": alert_id,
        }
        client = await self._get_client()
        response = await client.post(self.EVENTS_API_URL, json=payload)
        response.raise_for_status()
        return response.json()
