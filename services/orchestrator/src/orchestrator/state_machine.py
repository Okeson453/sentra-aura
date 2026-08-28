"""State machine for workflow execution.

Matches Architecture §4.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class WorkflowState(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    PERMANENT_FAIL = "PERMANENT_FAIL"
    CANCELLED = "CANCELLED"


class TaskState(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TaskNode:
    """A node in the workflow DAG."""
    task_id: str
    task_type: str
    agent_type: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    retries: int = 0
    max_retries: int = 3
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class WorkflowExecution:
    """Execution state of a workflow."""
    workflow_id: str
    workflow_type: str
    channel_id: str
    tenant_id: str = ""
    state: WorkflowState = WorkflowState.PENDING
    tasks: dict[str, TaskNode] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    error: str | None = None

    def get_ready_tasks(self) -> list[TaskNode]:
        """Return tasks whose dependencies are all completed."""
        ready = []
        for task in self.tasks.values():
            if task.state != TaskState.PENDING:
                continue
            deps_complete = all(
                self.tasks.get(dep, TaskNode(task_id=dep, task_type="", agent_type="")).state == TaskState.COMPLETED
                for dep in task.dependencies
            )
            if deps_complete:
                ready.append(task)
        return ready

    def all_tasks_complete(self) -> bool:
        return all(t.state in (TaskState.COMPLETED, TaskState.SKIPPED) for t in self.tasks.values())

    def any_task_failed(self) -> bool:
        return any(t.state == TaskState.FAILED for t in self.tasks.values())


class WorkflowStateMachine:
    """State machine for a single workflow with checkpoint support."""

    def __init__(self, initial_state: WorkflowState = WorkflowState.PENDING) -> None:
        self.current_state = initial_state
        self.previous_state: WorkflowState | None = None
        self.context: dict[str, Any] = {}

    def transition_to(self, new_state: WorkflowState) -> None:
        """Transition to a new state with validation."""
        valid_transitions = {
            WorkflowState.PENDING: [WorkflowState.QUEUED, WorkflowState.RUNNING, WorkflowState.CANCELLED],
            WorkflowState.QUEUED: [WorkflowState.STARTED, WorkflowState.CANCELLED],
            WorkflowState.STARTED: [WorkflowState.RUNNING, WorkflowState.FAILED, WorkflowState.CANCELLED],
            WorkflowState.RUNNING: [WorkflowState.COMPLETED, WorkflowState.PAUSED, WorkflowState.FAILED, WorkflowState.RETRYING, WorkflowState.CANCELLED],
            WorkflowState.PAUSED: [WorkflowState.RUNNING, WorkflowState.CANCELLED],
            WorkflowState.RETRYING: [WorkflowState.RUNNING, WorkflowState.FAILED, WorkflowState.PERMANENT_FAIL],
            WorkflowState.FAILED: [WorkflowState.RETRYING, WorkflowState.PERMANENT_FAIL, WorkflowState.CANCELLED],
            WorkflowState.COMPLETED: [],
            WorkflowState.PERMANENT_FAIL: [],
            WorkflowState.CANCELLED: [],
        }
        allowed = valid_transitions.get(self.current_state, [])
        if new_state not in allowed:
            raise ValueError(f"Invalid transition: {self.current_state.value} -> {new_state.value}")
        self.previous_state = self.current_state
        self.current_state = new_state

    def to_checkpoint(self) -> dict[str, Any]:
        """Serialize state to checkpoint dict."""
        return {
            "current_state": self.current_state.value,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "context": self.context,
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "WorkflowStateMachine":
        """Restore state machine from checkpoint."""
        sm = cls(initial_state=WorkflowState(data["current_state"]))
        if data.get("previous_state"):
            sm.previous_state = WorkflowState(data["previous_state"])
        sm.context = data.get("context", {})
        return sm
