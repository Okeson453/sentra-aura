"""In-memory store for agent registry with persistence hooks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from agent_registry_service.models import (
    AgentHealth,
    AgentRegistration,
    AgentStatus,
    AgentVersion,
    EvaluationRecord,
    EvaluationStatus,
    HealthStatus,
    RegisteredAgent,
)

logger = logging.getLogger(__name__)


class AgentStore:
    """Thread-safe(ish) in-memory store for agent registry data.

    In production this would be backed by PostgreSQL or Redis.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentRegistration] = {}
        self._health: dict[str, AgentHealth] = {}
        self._versions: dict[str, list[AgentVersion]] = {}
        self._evaluations: dict[str, list[EvaluationRecord]] = {}

    # --- Agent CRUD ---

    def register(self, registration: AgentRegistration) -> RegisteredAgent:
        if registration.agent_id in self._agents:
            raise ValueError(f"Agent {registration.agent_id} already registered")
        self._agents[registration.agent_id] = registration
        self._health[registration.agent_id] = AgentHealth(
            agent_id=registration.agent_id,
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.utcnow(),
        )
        self._versions.setdefault(registration.agent_id, []).append(
            AgentVersion(
                version=registration.version,
                status=AgentStatus.ACTIVE,
                release_notes=f"Initial registration of {registration.name}",
            )
        )
        logger.info("Registered agent %s v%s", registration.agent_id, registration.version)
        return self._to_registered(registration)

    def update(self, agent_id: str, registration: AgentRegistration) -> RegisteredAgent:
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")
        old = self._agents[agent_id]
        # Preserve registration timestamp
        registration.registered_at = old.registered_at
        registration.updated_at = datetime.utcnow()
        self._agents[agent_id] = registration
        # Add version record if version changed
        if registration.version != old.version:
            self._versions.setdefault(agent_id, []).append(
                AgentVersion(
                    version=registration.version,
                    status=AgentStatus.ACTIVE,
                    release_notes=f"Updated to {registration.version}",
                )
            )
        return self._to_registered(registration)

    def get(self, agent_id: str) -> RegisteredAgent | None:
        reg = self._agents.get(agent_id)
        if not reg:
            return None
        return self._to_registered(reg)

    def delete(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._health.pop(agent_id, None)
        logger.info("Unregistered agent %s", agent_id)

    def list_all(
        self,
        domain: str | None = None,
        status: AgentStatus | None = None,
        capability: str | None = None,
    ) -> list[RegisteredAgent]:
        results = []
        for reg in self._agents.values():
            if domain and reg.domain != domain:
                continue
            if status and reg.status != status:
                continue
            if capability and capability not in reg.capabilities:
                continue
            results.append(self._to_registered(reg))
        return results

    # --- Health ---

    def update_health(self, agent_id: str, health_status: HealthStatus) -> None:
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")
        self._health[agent_id] = AgentHealth(
            agent_id=agent_id,
            status=health_status,
            last_heartbeat=datetime.utcnow(),
        )

    def get_health(self, agent_id: str) -> AgentHealth | None:
        return self._health.get(agent_id)

    # --- Versions ---

    def list_versions(self, agent_id: str) -> list[AgentVersion]:
        return self._versions.get(agent_id, [])

    # --- Evaluations / CANARY ---

    def add_evaluation(self, record: EvaluationRecord) -> EvaluationRecord:
        self._evaluations.setdefault(record.agent_id, []).append(record)
        logger.info(
            "Added %s evaluation for %s: score=%.2f",
            record.status.value,
            record.agent_id,
            record.score,
        )
        return record

    def get_evaluations(self, agent_id: str) -> list[EvaluationRecord]:
        return self._evaluations.get(agent_id, [])

    def get_canary_status(self, agent_id: str) -> EvaluationRecord | None:
        evals = [e for e in self._evaluations.get(agent_id, []) if e.status == EvaluationStatus.CANARY]
        if not evals:
            return None
        return max(evals, key=lambda e: e.evaluated_at)

    def get_latest_evaluation(self, agent_id: str) -> EvaluationRecord | None:
        evals = self._evaluations.get(agent_id, [])
        if not evals:
            return None
        return max(evals, key=lambda e: e.evaluated_at)

    def _to_registered(self, reg: AgentRegistration) -> RegisteredAgent:
        health = self._health.get(reg.agent_id)
        return RegisteredAgent(
            agent_id=reg.agent_id,
            name=reg.name,
            domain=reg.domain,
            version=reg.version,
            status=reg.status,
            description=reg.description,
            capabilities=reg.capabilities,
            input_schema=reg.input_schema,
            output_schema=reg.output_schema,
            cost_estimate_usd=reg.cost_estimate_usd,
            avg_latency_ms=reg.avg_latency_ms,
            registered_at=reg.registered_at,
            health=health.status if health else HealthStatus.UNKNOWN,
        )
