"""Temporal workflows for SentraAura.

Matches Architecture §4.1, §5.1.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.state_machine import WorkflowExecution, WorkflowState, TaskState
    from orchestrator.scheduler import DAGScheduler


@workflow.defn
class AgentWorkflow:
    """Generic workflow that executes a DAG of agent tasks."""

    @workflow.run
    async def run(self, execution: WorkflowExecution) -> dict[str, Any]:
        execution.state = WorkflowState.RUNNING
        scheduler = DAGScheduler()

        # Validate DAG
        cycle = scheduler.detect_cycles(execution.tasks)
        if cycle:
            execution.state = WorkflowState.FAILED
            execution.error = f"Cycle detected: {' -> '.join(cycle)}"
            return execution.__dict__

        # Execute tasks in topological order
        order = scheduler.topological_sort(execution.tasks)
        for task_id in order:
            task = execution.tasks[task_id]
            if task.state != TaskState.PENDING:
                continue

            # Check if dependencies completed
            deps_ready = all(
                execution.tasks.get(dep, TaskNode(task_id=dep, task_type="", agent_type="")).state == TaskState.COMPLETED
                for dep in task.dependencies
            )
            if not deps_ready:
                task.state = TaskState.SKIPPED
                continue

            # Execute task activity
            try:
                task.state = TaskState.STARTED
                result = await workflow.execute_activity(
                    "execute_agent_task",
                    args=(task.task_type, task.agent_type, task.inputs),
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(
                        maximum_attempts=task.max_retries,
                        initial_interval=timedelta(seconds=5),
                    ),
                )
                task.outputs = result
                task.state = TaskState.COMPLETED
            except Exception as exc:
                task.state = TaskState.FAILED
                task.error = str(exc)
                task.retries += 1
                if task.retries >= task.max_retries:
                    execution.state = WorkflowState.FAILED
                    execution.error = f"Task {task_id} failed permanently: {exc}"
                    return execution.__dict__

        if execution.all_tasks_complete():
            execution.state = WorkflowState.COMPLETED
        elif execution.any_task_failed():
            execution.state = WorkflowState.FAILED
        execution.completed_at = workflow.now().isoformat()
        return execution.__dict__


@workflow.defn
class LongFormVideoWorkflow:
    """Workflow for long-form video production."""

    @workflow.run
    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        channel_id = params["channel_id"]
        topic = params["topic"]

        # Step 1: Research
        research = await workflow.execute_activity(
            "research_topic",
            args=(channel_id, topic),
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 2: Draft script
        script = await workflow.execute_activity(
            "draft_script",
            args=(channel_id, research),
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 3: Produce voice
        voice = await workflow.execute_activity(
            "produce_voice",
            args=(channel_id, script),
            start_to_close_timeout=timedelta(minutes=20),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 4: Generate visuals
        visuals = await workflow.execute_activity(
            "generate_visuals",
            args=(channel_id, script),
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 5: Render video
        video = await workflow.execute_activity(
            "render_video",
            args=(channel_id, script, voice, visuals),
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        return {
            "channel_id": channel_id,
            "topic": topic,
            "video_id": video.get("video_id"),
            "status": "COMPLETED",
        }


# ---------------------------------------------------------------------------
# In-process workflow helpers for unit/crash-recovery tests (no Temporal worker)
# ---------------------------------------------------------------------------

class InProcessAgentWorkflow:
    """Lightweight agent workflow with explicit state machine for tests."""

    def __init__(self) -> None:
        from orchestrator.state_machine import WorkflowStateMachine, WorkflowState
        self.state_machine = WorkflowStateMachine(initial_state=WorkflowState.PENDING)
        self.checkpoints: list[dict[str, Any]] = []

    def transition(self, state) -> None:
        self.state_machine.transition_to(state)

    def checkpoint(self, context: dict[str, Any]) -> None:
        self.checkpoints.append({"state": self.state_machine.current_state.value, "context": context})


class InProcessLongFormVideoWorkflow:
    """Long-form pipeline stages including clipping/distribution/ops."""

    STAGES = [
        "research",
        "scripting",
        "production",
        "clipping",
        "packaging",
        "publishing",
        "analytics",
    ]

    def __init__(self, checkpoint_interval_seconds: float = 1.0) -> None:
        self.checkpoint_interval_seconds = checkpoint_interval_seconds
        self.checkpoints: list[dict[str, Any]] = []
        self.completed_stages: list[str] = []

    def run_stages(self, topic: str) -> dict[str, Any]:
        for i, stage in enumerate(self.STAGES):
            self.completed_stages.append(stage)
            self.checkpoints.append({
                "stage": stage,
                "context": {"progress": (i + 1) / len(self.STAGES), "topic": topic},
            })
        return {"stages": list(self.completed_stages), "checkpoints": len(self.checkpoints)}


# Back-compat aliases some tests import
try:
    AgentWorkflow  # noqa: F401
except NameError:
    AgentWorkflow = InProcessAgentWorkflow  # type: ignore
