"""Temporal worker harness for SentraAura tests."""
from __future__ import annotations

from typing import Any, Callable


class TemporalWorkerHarness:
    """In-memory harness for testing Temporal workflows."""

    def __init__(self) -> None:
        self._workflows: dict[str, Callable] = {}
        self._activities: dict[str, Callable] = {}
        self._executions: list[dict[str, Any]] = []

    def register_workflow(self, name: str, fn: Callable) -> None:
        """Register a workflow function."""
        self._workflows[name] = fn

    def register_activity(self, name: str, fn: Callable) -> None:
        """Register an activity function."""
        self._activities[name] = fn

    async def execute_workflow(
        self,
        name: str,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a workflow in the harness."""
        wf = self._workflows.get(name)
        if wf is None:
            raise ValueError(f"Workflow {name} not registered")
        result = await wf(*args, **(kwargs or {}))
        self._executions.append({"workflow": name, "result": result})
        return result

    def get_executions(self) -> list[dict[str, Any]]:
        """Get all executed workflows."""
        return self._executions.copy()
