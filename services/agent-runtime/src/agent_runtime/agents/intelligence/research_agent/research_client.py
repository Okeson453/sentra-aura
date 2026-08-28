"""HTTP client for research-service (retrieval is not reimplemented inline)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ResearchServiceClient:
    """Calls research-service POST /research and polls job results."""

    def __init__(
        self,
        base_url: str,
        token: str = "dev-token",
        timeout: float = 60.0,
        poll_interval: float = 0.15,
        poll_max_attempts: int = 40,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.poll_max_attempts = poll_max_attempts
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

    async def health(self) -> dict[str, Any]:
        client = await self._get_client()
        r = await client.get(f"{self.base_url}/health")
        r.raise_for_status()
        return r.json()

    async def start_research(
        self,
        *,
        query: str,
        depth: str = "standard",
        max_sources: int = 10,
        topic_domains: list[str] | None = None,
        channel_id: str = "",
    ) -> dict[str, Any]:
        """POST /research — starts async research job."""
        client = await self._get_client()
        payload = {
            "query": query,
            "depth": depth,
            "max_sources": max_sources,
            "topic_domains": topic_domains or [],
            "channel_id": channel_id,
        }
        logger.info("research-service POST /research query=%s", query[:80])
        r = await client.post(
            f"{self.base_url}/research", json=payload, headers=self._headers()
        )
        r.raise_for_status()
        return r.json()

    async def get_job(self, job_id: str) -> dict[str, Any]:
        client = await self._get_client()
        r = await client.get(
            f"{self.base_url}/research/jobs/{job_id}", headers=self._headers()
        )
        r.raise_for_status()
        return r.json()

    async def get_results(self, job_id: str) -> dict[str, Any]:
        client = await self._get_client()
        r = await client.get(
            f"{self.base_url}/research/jobs/{job_id}/results", headers=self._headers()
        )
        r.raise_for_status()
        return r.json()

    async def search_and_wait(
        self,
        *,
        query: str,
        depth: str = "standard",
        max_sources: int = 10,
        topic_domains: list[str] | None = None,
        channel_id: str = "",
    ) -> dict[str, Any]:
        """Start research and poll until completed or failed; return results dict."""
        job = await self.start_research(
            query=query,
            depth=depth,
            max_sources=max_sources,
            topic_domains=topic_domains,
            channel_id=channel_id,
        )
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            raise RuntimeError(f"research-service did not return job_id: {job!r}")

        # Synchronous mock services may complete immediately and embed results
        if job.get("status") == "completed" and job.get("results"):
            return {"job_id": job_id, "job": job, "results": job["results"]}

        for _ in range(self.poll_max_attempts):
            status = await self.get_job(job_id)
            st = (status.get("status") or "").lower()
            if st in ("completed", "complete", "succeeded", "success"):
                results = await self.get_results(job_id)
                return {"job_id": job_id, "job": status, "results": results}
            if st in ("failed", "error"):
                raise RuntimeError(f"research job failed: {status}")
            await asyncio.sleep(self.poll_interval)

        raise TimeoutError(f"research job {job_id} did not complete in time")
