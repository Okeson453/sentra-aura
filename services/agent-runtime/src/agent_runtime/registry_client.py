"""Agent Registry Client — discovers agent capabilities and routes tasks to registered agents.

This client communicates with the Agent Registry Service to:
- Register/unregister agents
- Query agent capabilities and health
- Resolve agent endpoints for task dispatch
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentDescriptor:
    """Canonical descriptor for a registered agent."""

    agent_id: str
    name: str
    domain: str
    capabilities: list[str]
    version: str
    endpoint: str
    health: str
    autonomy_level: str
    risk_tier: str


class RegistryClient:
    """Client for the Agent Registry Service."""

    def __init__(
        self,
        registry_url: str = "http://agent-registry-service:8000",
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.registry_url = registry_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.registry_url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=timeout,
        )
        self._cache: dict[str, AgentDescriptor] = {}

    async def register(
        self,
        agent_id: str,
        name: str,
        domain: str,
        capabilities: list[str],
        version: str,
        endpoint: str,
        autonomy_level: str = "L2",
        risk_tier: str = "medium",
    ) -> dict[str, Any]:
        """Register an agent with the registry."""
        payload = {
            "agent_id": agent_id,
            "name": name,
            "domain": domain,
            "capabilities": capabilities,
            "version": version,
            "endpoint": endpoint,
            "autonomy_level": autonomy_level,
            "risk_tier": risk_tier,
        }
        resp = await self._client.post("/agents", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Registered agent %s v%s", agent_id, version)
        return data

    async def unregister(self, agent_id: str) -> None:
        """Unregister an agent."""
        resp = await self._client.delete(f"/agents/{agent_id}")
        resp.raise_for_status()
        self._cache.pop(agent_id, None)
        logger.info("Unregistered agent %s", agent_id)

    async def get_agent(self, agent_id: str) -> AgentDescriptor | None:
        """Fetch descriptor for a specific agent."""
        if agent_id in self._cache:
            return self._cache[agent_id]
        try:
            resp = await self._client.get(f"/agents/{agent_id}")
            resp.raise_for_status()
            data = resp.json()
            desc = AgentDescriptor(
                agent_id=data["agent_id"],
                name=data["name"],
                domain=data["domain"],
                capabilities=data.get("capabilities", []),
                version=data["version"],
                endpoint=data["endpoint"],
                health=data.get("health", "unknown"),
                autonomy_level=data.get("autonomy_level", "L2"),
                risk_tier=data.get("risk_tier", "medium"),
            )
            self._cache[agent_id] = desc
            return desc
        except Exception as exc:
            logger.warning("Failed to fetch agent %s: %s", agent_id, exc)
            return None

    async def list_agents(
        self,
        domain: str | None = None,
        capability: str | None = None,
        health: str | None = None,
    ) -> list[AgentDescriptor]:
        """List agents with optional filtering."""
        params: dict[str, str] = {}
        if domain:
            params["domain"] = domain
        if capability:
            params["capability"] = capability
        if health:
            params["health"] = health

        resp = await self._client.get("/agents", params=params)
        resp.raise_for_status()
        data = resp.json()
        return [
            AgentDescriptor(
                agent_id=a["agent_id"],
                name=a["name"],
                domain=a["domain"],
                capabilities=a.get("capabilities", []),
                version=a["version"],
                endpoint=a["endpoint"],
                health=a.get("health", "unknown"),
                autonomy_level=a.get("autonomy_level", "L2"),
                risk_tier=a.get("risk_tier", "medium"),
            )
            for a in data.get("agents", [])
        ]

    async def update_health(self, agent_id: str, health: str) -> None:
        """Update agent health status."""
        resp = await self._client.patch(
            f"/agents/{agent_id}/health",
            json={"health": health},
        )
        resp.raise_for_status()
        if agent_id in self._cache:
            # Invalidate cache entry
            del self._cache[agent_id]

    async def submit_evaluation(
        self,
        agent_id: str,
        status: str,  # canary, staging, production, deprecated
        score: float,
        evaluator: str,
        notes: str = "",
    ) -> dict[str, Any]:
        """Submit an evaluation record for an agent."""
        payload = {
            "agent_id": agent_id,
            "status": status,
            "score": score,
            "evaluator": evaluator,
            "notes": notes,
        }
        resp = await self._client.post(f"/agents/{agent_id}/evaluations", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_evaluations(self, agent_id: str) -> list[dict[str, Any]]:
        """Get evaluation history for an agent."""
        resp = await self._client.get(f"/agents/{agent_id}/evaluations")
        resp.raise_for_status()
        return resp.json().get("evaluations", [])

    async def get_canary_status(self, agent_id: str) -> dict[str, Any] | None:
        """Get the latest CANARY evaluation for an agent."""
        evaluations = await self.get_evaluations(agent_id)
        canary_evals = [e for e in evaluations if e.get("status") == "canary"]
        if not canary_evals:
            return None
        return max(canary_evals, key=lambda e: e.get("evaluated_at", ""))

    async def close(self) -> None:
        await self._client.aclose()
