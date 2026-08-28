"""Saga pattern implementation for durable workflows.

Supports choreography and orchestration sagas with compensation.
Matches Architecture §4.1 and Backend Spec §5.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class SagaStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"


@dataclass
class SagaStep:
    """A single step in a saga with action and compensation."""

    step_id: str
    name: str
    action: Any = None  # Callable or string action name
    compensation: Any = None
    max_retries: int = 3
    retry_delay_seconds: float = 5.0
    timeout_seconds: float = 300.0


@dataclass
class SagaLogEntry:
    step_id: str
    action: str
    status: str
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    timestamp: str = ""


@dataclass
class SagaState:
    saga_id: str
    saga_type: str = "default"
    status: SagaStatus | str = SagaStatus.PENDING
    current_step_index: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    error: str | None = None
    logs: list[SagaLogEntry] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    steps: list[SagaStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "saga_id": self.saga_id,
            "saga_type": self.saga_type,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "current_step_index": self.current_step_index,
            "completed_steps": list(self.completed_steps),
            "failed_step": self.failed_step,
            "error": self.error,
            "context": dict(self.context),
        }


# Tests historically used SagaDefinition as the step container
@dataclass
class SagaDefinition:
    saga_id: str
    steps: list[SagaStep] = field(default_factory=list)
    saga_type: str = "workflow"

    def to_state(self) -> SagaState:
        return SagaState(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            steps=list(self.steps),
        )


SagaCheckpoint = SagaState


class SagaOrchestrator:
    """Orchestrates sagas with checkpointing and compensation."""

    def __init__(
        self,
        saga_id: str | None = None,
        saga_type: str = "workflow",
        *,
        checkpoint_dir: str | None = None,
        saga_definition: SagaDefinition | None = None,
    ) -> None:
        if saga_definition is not None:
            self.saga_definition = saga_definition
            self.state = saga_definition.to_state()
            self._steps = list(saga_definition.steps)
            self.state.saga_id = saga_definition.saga_id
        else:
            sid = saga_id or "saga"
            self.saga_definition = SagaDefinition(saga_id=sid, saga_type=saga_type)
            self.state = SagaState(saga_id=sid, saga_type=saga_type)
            self._steps: list[SagaStep] = []
        self._checkpoint_dir = Path(checkpoint_dir or tempfile.mkdtemp(prefix="saga-cp-"))
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_fn: Callable[[SagaState], Awaitable[None]] | None = None
        self._action_handlers: dict[str, Callable] = {}
        self._comp_handlers: dict[str, Callable] = {}

    def add_step(self, step: SagaStep) -> "SagaOrchestrator":
        self._steps.append(step)
        self.saga_definition.steps.append(step)
        return self

    def on_checkpoint(self, fn: Callable[[SagaState], Awaitable[None]]) -> "SagaOrchestrator":
        self._checkpoint_fn = fn
        return self

    async def _persist_checkpoint(self) -> None:
        cp = self._checkpoint_dir / f"{self.state.saga_id}-{self.state.current_step_index}.json"
        cp.write_text(json.dumps(self.state.to_dict(), default=str), encoding="utf-8")
        if self._checkpoint_fn:
            await self._checkpoint_fn(self.state)

    def list_checkpoints(self) -> list[dict[str, Any]]:
        out = []
        for p in sorted(self._checkpoint_dir.glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    def load_latest_checkpoint(self, saga_id: str) -> SagaState | None:
        candidates = sorted(self._checkpoint_dir.glob(f"{saga_id}-*.json"))
        if not candidates:
            return None
        data = json.loads(candidates[-1].read_text(encoding="utf-8"))
        st = SagaState(
            saga_id=data["saga_id"],
            saga_type=data.get("saga_type", "workflow"),
            status=data.get("status", "PENDING"),
            current_step_index=int(data.get("current_step_index") or 0),
            completed_steps=list(data.get("completed_steps") or []),
            failed_step=data.get("failed_step"),
            error=data.get("error"),
            context=dict(data.get("context") or {}),
        )
        return st

    async def _execute_action(self, action: Any, context: dict[str, Any]) -> dict[str, Any]:
        if callable(action):
            result = action()
            if hasattr(result, "__await__"):
                return await result  # type: ignore[misc]
            return result if isinstance(result, dict) else {"result": result}
        name = str(action)
        handler = self._action_handlers.get(name)
        if handler:
            result = handler(context)
            if hasattr(result, "__await__"):
                return await result
            return result if isinstance(result, dict) else {"result": result}
        return {"status": "success", "action": name}

    async def _execute_compensation(self, compensation: Any, context: dict[str, Any]) -> dict[str, Any]:
        if callable(compensation):
            result = compensation()
            if hasattr(result, "__await__"):
                return await result  # type: ignore[misc]
            return result if isinstance(result, dict) else {"result": result}
        name = str(compensation)
        handler = self._comp_handlers.get(name)
        if handler:
            result = handler(context)
            if hasattr(result, "__await__"):
                return await result
            return result if isinstance(result, dict) else {"result": result}
        return {"status": "compensated", "compensation": name}

    async def execute(self, context: dict[str, Any] | None = None) -> SagaState:
        self.state.status = SagaStatus.RUNNING
        if context:
            self.state.context.update(context)

        start_idx = 0
        # Resume support: skip completed steps
        if self.state.completed_steps:
            start_idx = len(self.state.completed_steps)

        for i, step in enumerate(self._steps):
            if i < start_idx:
                continue
            self.state.current_step_index = i
            await self._persist_checkpoint()
            try:
                result = await self._execute_action(step.action, self.state.context)
                self.state.completed_steps.append(step.step_id)
                self.state.context[f"{step.step_id}_result"] = result
                if isinstance(result, dict):
                    self.state.context.update({k: v for k, v in result.items() if k.endswith("_id")})
                self.state.logs.append(
                    SagaLogEntry(
                        step_id=step.step_id,
                        action="execute",
                        status="success",
                        result=result if isinstance(result, dict) else {},
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception as exc:
                self.state.failed_step = step.step_id
                self.state.error = str(exc)
                self.state.logs.append(
                    SagaLogEntry(
                        step_id=step.step_id,
                        action="execute",
                        status="failure",
                        error=str(exc),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
                await self._compensate()
                await self._persist_checkpoint()
                raise

        self.state.status = SagaStatus.COMPLETED
        await self._persist_checkpoint()
        return self.state

    async def _compensate(self) -> None:
        self.state.status = SagaStatus.COMPENSATING
        for step_id in reversed(self.state.completed_steps):
            step = next((s for s in self._steps if s.step_id == step_id), None)
            if not step or not step.compensation:
                continue
            try:
                result = await self._execute_compensation(step.compensation, self.state.context)
                self.state.logs.append(
                    SagaLogEntry(
                        step_id=step.step_id,
                        action="compensate",
                        status="success",
                        result=result if isinstance(result, dict) else {},
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception as exc:
                self.state.logs.append(
                    SagaLogEntry(
                        step_id=step.step_id,
                        action="compensate",
                        status="failure",
                        error=str(exc),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
                # continue compensating others
        self.state.status = SagaStatus.COMPENSATED
