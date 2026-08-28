"""Base agent class with standardized lifecycle, tool invocation, and observability.

All SentraAura domain agents inherit from BaseAgent to ensure:
- Consistent initialization and configuration
- Standardized tool permission enforcement
- Injection defense at the boundary
- Structured output validation
- Audit logging and telemetry
- Graceful error handling and fallback
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.execution_policy import ExecutionPolicy
from agent_runtime.registry_client import RegistryClient
from agent_runtime.approval_gate import ApprovalGate, ApprovalScope, get_default_approval_gate
from agent_runtime.tool_permissions import (
    ApprovalRequiredError,
    PermissionDeniedError,
    PermissionMatrix,
    ToolPermissionEnforcer,
)
from agent_runtime.sandbox.runner import SandboxRunner, SandboxLimits
from agent_runtime.injection_defense.untrusted_boundary import UntrustedBoundary

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class AgentState:
    """Mutable agent execution state."""

    status: AgentStatus = AgentStatus.IDLE
    current_task_id: str | None = None
    step_count: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


T = TypeVar("T")


class BaseAgent(ABC, Generic[T]):
    """Abstract base class for all SentraAura domain agents."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        domain: str,
        version: str = "1.0.0",
        autonomy_level: str = "L2",
        registry_client: RegistryClient | None = None,
        permission_matrix: PermissionMatrix | None = None,
        sandbox_limits: SandboxLimits | None = None,
        approval_gate: ApprovalGate | None = None,
        **kwargs: Any,
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.domain = domain
        self.version = version
        self.autonomy_level = autonomy_level
        self.registry = registry_client
        self.permissions = ToolPermissionEnforcer(permission_matrix or PermissionMatrix())
        self.approval_gate: ApprovalGate = approval_gate or get_default_approval_gate()
        self.sandbox = SandboxRunner(sandbox_limits)
        self.boundary = UntrustedBoundary()
        self.state = AgentState()
        self._tools: dict[str, Any] = {}

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """Return the list of capabilities this agent provides."""
        ...

    @abstractmethod
    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        """Execute a task envelope and return structured results."""
        ...

    async def run(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        """Standardized agent lifecycle wrapper around execute()."""
        task_id = envelope.message.trace_id or f"task-{uuid.uuid4().hex[:12]}"
        self.state = AgentState(
            status=AgentStatus.RUNNING,
            current_task_id=task_id,
            started_at=time.time(),
        )
        logger.info("Agent %s starting task %s", self.agent_id, task_id)

        try:
            # Register with registry if available
            if self.registry:
                await self._register_with_registry()

            # Pre-execution: validate envelope
            self._validate_envelope(envelope)

            # Execute
            result = await self.execute(envelope)

            # Post-execution: validate output
            self._validate_output(result)

            self.state.status = AgentStatus.COMPLETED
            self.state.completed_at = time.time()
            logger.info("Agent %s completed task %s", self.agent_id, task_id)
            return result

        except PermissionDeniedError as exc:
            self.state.status = AgentStatus.ERROR
            self.state.errors.append({"type": "permission_denied", "message": str(exc)})
            logger.error("Agent %s permission denied: %s", self.agent_id, exc)
            raise

        except Exception as exc:
            self.state.status = AgentStatus.ERROR
            self.state.errors.append({"type": type(exc).__name__, "message": str(exc)})
            logger.exception("Agent %s failed task %s", self.agent_id, task_id)
            raise

    def _validate_envelope(self, envelope: AgentMessageEnvelope) -> None:
        """Validate incoming task envelope."""
        if not envelope.message.agent_type:
            raise ValueError("Task envelope missing agent_type")
        if not envelope.message.task_type:
            raise ValueError("Task envelope missing task_type")

    def _validate_output(self, result: dict[str, Any]) -> None:
        """Validate agent output structure."""
        if not isinstance(result, dict):
            raise ValueError("Agent output must be a dict")

    async def invoke_tool(
        self,
        tool_name: str,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        scope_key: str = "",
    ) -> Any:
        """Invoke a tool with permission checking, approval gate, and sandboxing."""
        kwargs = kwargs or {}
        scope = ApprovalScope(
            agent_id=self.agent_id,
            tool_name=tool_name,
            action="execute",
            scope_key=scope_key,
        )

        # Permission check — ESCALATE+requires_approval may be satisfied by a grant
        try:
            await self.permissions.enforce(
                self.agent_id, tool_name, "execute", context={"args": str(args), "scope_key": scope_key}
            )
        except ApprovalRequiredError:
            consumed = self.approval_gate.consume_grant(scope)
            if consumed is None:
                pending = self.approval_gate.request(scope, context={"args": str(args)[:500]})
                raise ApprovalRequiredError(
                    self.agent_id,
                    tool_name,
                    "execute",
                    "No permission rule allows without approval — grant required",
                    approval_id=pending.approval_id,
                    scope_key=scope_key,
                ) from None
            logger.info(
                "Proceeding on approved grant id=%s for %s/%s",
                consumed.approval_id,
                self.agent_id,
                tool_name,
            )

        # Find tool
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not registered for agent {self.agent_id}")

        # Sandbox execution
        result = await self.sandbox.run(
            tool=tool,
            args=args,
            kwargs=kwargs,
            agent_id=self.agent_id,
            tool_name=tool_name,
        )

        self.state.tool_calls.append({
            "tool": tool_name,
            "success": result.success,
            "duration_ms": result.duration_ms,
        })
        self.state.step_count += 1

        if not result.success:
            raise RuntimeError(f"Tool {tool_name} failed: {result.stderr}")

        return result.output

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a tool for this agent."""
        self._tools[name] = tool
        logger.debug("Registered tool %s for agent %s", name, self.agent_id)

    def sanitize_input(self, text: str, source: str = "unknown") -> str:
        """Sanitize external input through the untrusted boundary."""
        result = self.boundary.validate(text, source=source, agent_id=self.agent_id)
        if not result.allowed:
            raise ValueError(f"Input blocked by untrusted boundary: {result.threat_level}")
        return result.sanitized_text

    async def _register_with_registry(self) -> None:
        """Register this agent with the registry service."""
        if not self.registry:
            return
        try:
            await self.registry.register(
                agent_id=self.agent_id,
                name=self.name,
                domain=self.domain,
                capabilities=self.capabilities,
                version=self.version,
                endpoint=f"agents/{self.agent_id}",
                autonomy_level=self.autonomy_level,
            )
        except Exception as exc:
            logger.warning("Failed to register agent %s: %s", self.agent_id, exc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize agent state for observability."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "version": self.version,
            "autonomy_level": self.autonomy_level,
            "capabilities": self.capabilities,
            "status": self.state.status.value,
            "current_task_id": self.state.current_task_id,
            "step_count": self.state.step_count,
            "tool_call_count": len(self.state.tool_calls),
            "error_count": len(self.state.errors),
            "started_at": self.state.started_at,
            "completed_at": self.state.completed_at,
        }
