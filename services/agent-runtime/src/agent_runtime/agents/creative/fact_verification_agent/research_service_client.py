"""Client for research-service fact-check and claims endpoints."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FactCheckServiceClient:
    def __init__(self, base_url: str, token: str = "dev-token", timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fact_check(
        self,
        *,
        claim_text: str,
        context: str = "",
        channel_id: str = "",
    ) -> dict[str, Any]:
        """POST /fact-check on research-service."""
        client = await self._get_client()
        payload = {
            "claim_text": claim_text,
            "context": context,
            "channel_id": channel_id,
        }
        logger.info("research-service POST /fact-check claim=%s", claim_text[:80])
        r = await client.post(
            f"{self.base_url}/fact-check", json=payload, headers=self._headers()
        )
        r.raise_for_status()
        return r.json()
