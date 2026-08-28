"""Sandboxed tool execution runner with resource limits and isolation.

Executes agent tool calls in a controlled environment with:
- CPU time limits
- Memory limits
- Network egress restrictions (in-process; see network_guard)
- Input/output sanitization
- Audit logging

Network enforcement: in-process ContextVar-scoped socket.connect block when
allow_network=False. Does not provide OS-level network namespace isolation.
"""
from __future__ import annotations

import asyncio
import logging
import resource
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from agent_runtime.sandbox.network_guard import (
    NetworkAccessDeniedError,
    network_restriction,
)

logger = logging.getLogger(__name__)

def _find_network_denied(exc: BaseException) -> NetworkAccessDeniedError | None:
    """Unwrap ExceptionGroup / cause chain for NetworkAccessDeniedError."""
    if isinstance(exc, NetworkAccessDeniedError):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            found = _find_network_denied(sub)
            if found is not None:
                return found
    if exc.__cause__ is not None:
        return _find_network_denied(exc.__cause__)
    if exc.__context__ is not None and exc.__context__ is not exc.__cause__:
        return _find_network_denied(exc.__context__)
    return None



@dataclass(frozen=True)
class SandboxLimits:
    """Resource limits for sandboxed execution."""

    max_cpu_time_seconds: float = 30.0
    max_memory_mb: int = 512
    max_output_chars: int = 100_000
    max_file_descriptors: int = 64
    allow_network: bool = False


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""

    success: bool
    output: Any
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    memory_peak_mb: float = 0.0
    truncated: bool = False
    audit_log: dict[str, Any] = field(default_factory=dict)


class SandboxRunner:
    """Runs tool invocations in a sandboxed environment."""

    def __init__(self, limits: SandboxLimits | None = None) -> None:
        self.limits = limits or SandboxLimits()

    async def run(
        self,
        tool: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any] | None = None,
        agent_id: str = "unknown",
        tool_name: str = "unknown",
    ) -> SandboxResult:
        """Execute a tool call within sandbox constraints."""
        kwargs = kwargs or {}
        start_time = time.perf_counter()
        audit_entry: dict[str, Any] = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "allow_network": self.limits.allow_network,
        }

        # Block network only for this execution when allow_network=False
        restrict = not self.limits.allow_network

        try:
            if asyncio.iscoroutinefunction(tool):
                with network_restriction(restrict):
                    output = await asyncio.wait_for(
                        tool(*args, **kwargs),
                        timeout=self.limits.max_cpu_time_seconds,
                    )
            else:
                # ContextVar does not follow into executor threads — set restriction inside the worker
                def _sync_call() -> Any:
                    with network_restriction(restrict):
                        return tool(*args, **kwargs)

                loop = asyncio.get_event_loop()
                output = await asyncio.wait_for(
                    loop.run_in_executor(None, _sync_call),
                    timeout=self.limits.max_cpu_time_seconds,
                )

            duration_ms = (time.perf_counter() - start_time) * 1000
            truncated = False
            try:
                output_str = str(output) if output is not None else ""
                if len(output_str) > self.limits.max_output_chars:
                    output = output_str[: self.limits.max_output_chars] + "...[TRUNCATED]"
                    truncated = True
            except Exception:
                pass

            audit_entry.update({
                "success": True,
                "duration_ms": duration_ms,
                "truncated": truncated,
            })

            return SandboxResult(
                success=True,
                output=output,
                duration_ms=duration_ms,
                truncated=truncated,
                audit_log=audit_entry,
            )

        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            audit_entry.update({
                "success": False,
                "error": "timeout",
                "duration_ms": duration_ms,
            })
            logger.warning("Sandbox timeout: %s -> %s", agent_id, tool_name)
            return SandboxResult(
                success=False,
                output=None,
                stderr=f"Execution timed out after {self.limits.max_cpu_time_seconds}s",
                exit_code=-1,
                duration_ms=duration_ms,
                audit_log=audit_entry,
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            denied = _find_network_denied(exc)
            if denied is not None:
                audit_entry.update({
                    "success": False,
                    "error": "network_denied",
                    "error_type": "NetworkAccessDeniedError",
                    "duration_ms": duration_ms,
                })
                logger.warning("Sandbox network denied: %s -> %s: %s", agent_id, tool_name, denied)
                return SandboxResult(
                    success=False,
                    output=None,
                    stderr=str(denied),
                    exit_code=-3,
                    duration_ms=duration_ms,
                    audit_log=audit_entry,
                )
            audit_entry.update({
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "duration_ms": duration_ms,
            })
            logger.warning("Sandbox error: %s -> %s: %s", agent_id, tool_name, exc)
            return SandboxResult(
                success=False,
                output=None,
                stderr=str(exc),
                exit_code=-2,
                duration_ms=duration_ms,
                audit_log=audit_entry,
            )

    def apply_limits(self) -> None:
        """Apply resource limits to the current process (for subprocess sandboxes)."""
        if sys.platform != "linux":
            return
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (int(self.limits.max_cpu_time_seconds), int(self.limits.max_cpu_time_seconds) + 1),
        )
        max_bytes = self.limits.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        resource.setrlimit(
            resource.RLIMIT_NOFILE,
            (self.limits.max_file_descriptors, self.limits.max_file_descriptors),
        )
