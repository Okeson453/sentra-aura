"""Temporal workflows for SentraAura.

Matches Architecture §4.1, §5.1.
Implements the complete autonomous loop: Discover -> Create -> Produce -> Clip -> Publish -> Measure -> Learn -> Optimize
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.state_machine import WorkflowExecution, WorkflowState, TaskState, TaskNode
    from orchestrator.scheduler import DAGScheduler


def _require_activity_ok(name: str, result: dict[str, Any] | Any) -> dict[str, Any]:
    """Raise if an activity reported failure without throwing (P1-05).

    Temporal only fails the workflow when the activity raises. Activities that
    return ``{"status": "failed"}`` would otherwise leave LongFormVideoWorkflow
    reporting COMPLETED with a broken pipeline.
    """
    if not isinstance(result, dict):
        return {"value": result}
    status = str(result.get("status") or "").lower()
    if status in ("failed", "error", "cancelled"):
        raise RuntimeError(
            f"activity {name} returned status={status}: "
            f"{result.get('error') or result.get('error_message') or result}"
        )
    return result


@workflow.defn
class AgentWorkflow:
    """Generic workflow that executes a DAG of agent tasks."""

    @workflow.run
    async def run(self, execution: WorkflowExecution) -> dict[str, Any]:
        execution.state = WorkflowState.RUNNING
        scheduler = DAGScheduler()

        cycle = scheduler.detect_cycles(execution.tasks)
        if cycle:
            execution.state = WorkflowState.FAILED
            execution.error = f"Cycle detected: {' -> '.join(cycle)}"
            return execution.__dict__

        order = scheduler.topological_sort(execution.tasks)
        for task_id in order:
            task = execution.tasks[task_id]
            if task.state != TaskState.PENDING:
                continue

            deps_ready = all(
                execution.tasks.get(dep, TaskNode(task_id=dep, task_type="", agent_type="")).state == TaskState.COMPLETED
                for dep in task.dependencies
            )
            if not deps_ready:
                task.state = TaskState.SKIPPED
                continue

            try:
                task.state = TaskState.STARTED
                result = await workflow.execute_activity(
                    "execute_agent_task",
                    args=(
                        task.task_type,
                        task.agent_type,
                        task.inputs,
                        getattr(execution, "tenant_id", None),
                    ),
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(
                        maximum_attempts=max(1, task.max_retries + 1),
                        initial_interval=timedelta(seconds=5),
                        backoff_coefficient=2.0,
                    ),
                )
                task.outputs = result
                task.state = TaskState.COMPLETED
            except Exception as exc:
                task.state = TaskState.FAILED
                task.error = str(exc)
                task.retries += 1
                execution.state = WorkflowState.FAILED
                execution.error = f"Task {task_id} failed after {task.max_retries} retries: {exc}"
                execution.completed_at = workflow.now().isoformat()
                return execution.__dict__

        if execution.all_tasks_complete():
            execution.state = WorkflowState.COMPLETED
        elif execution.any_task_failed():
            execution.state = WorkflowState.FAILED
        execution.completed_at = workflow.now().isoformat()
        return execution.__dict__


@workflow.defn
class LongFormVideoWorkflow:
    """Workflow for complete long-form video production and autonomous loop.

    Implements: Discover -> Create -> Produce -> Clip -> Publish -> Measure -> Learn -> Optimize
    Matches Architecture §1 Core Operating Loop.
    """

    @workflow.run
    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        channel_id = params["channel_id"]
        topic = params["topic"]
        #: Owning tenant for this run. Threaded into every activity so the
        #: signed service token carries it as a claim: downstream services
        #: (publishing-service, policy-engine, analytics-ingestion) derive the
        #: acting tenant from that verified claim and fail closed (401) on a
        #: tenant-less token, so a run without it cannot publish or re-evaluate
        #: policy at all. Absent lineage falls back to the shared unattributed
        #: tenant rather than being silently dropped.
        tenant_id = params.get("tenant_id")
        workflow_id = params.get("workflow_id", workflow.uuid4() if hasattr(workflow, "uuid4") else str(workflow.info().workflow_id))

        results: dict[str, Any] = {
            "channel_id": channel_id,
            "topic": topic,
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
        }

        research = await workflow.execute_activity(
            "research_topic",
            args=(channel_id, topic, tenant_id),
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        results["research"] = _require_activity_ok("research_topic", research)

        script = await workflow.execute_activity(
            "draft_script",
            args=(channel_id, research, tenant_id),
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        results["script"] = _require_activity_ok("draft_script", script)

        voice = await workflow.execute_activity(
            "produce_voice",
            args=(channel_id, script, tenant_id),
            start_to_close_timeout=timedelta(minutes=20),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        results["voice"] = _require_activity_ok("produce_voice", voice)

        visuals = await workflow.execute_activity(
            "generate_visuals",
            args=(channel_id, script, tenant_id),
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        results["visuals"] = _require_activity_ok("generate_visuals", visuals)

        video = await workflow.execute_activity(
            "render_video",
            args=(channel_id, script, voice, visuals, tenant_id),
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        results["video"] = _require_activity_ok("render_video", video)

        clips = await workflow.execute_activity(
            "generate_clips",
            args=(channel_id, video.get("video_id"), script, tenant_id),
            start_to_close_timeout=timedelta(minutes=45),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        results["clips"] = _require_activity_ok("generate_clips", clips)

        publish_result = await workflow.execute_activity(
            "publish_content",
            args=(channel_id, video.get("video_id"), clips, script, tenant_id),
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        publish_result = _require_activity_ok("publish_content", publish_result)
        results["publish"] = publish_result

        analytics_result = await workflow.execute_activity(
            "record_analytics",
            args=(channel_id, video.get("video_id"), publish_result, clips, tenant_id),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        results["analytics"] = analytics_result

        learning_result = await workflow.execute_activity(
            "update_learning",
            args=(channel_id, video.get("video_id"), analytics_result, clips, tenant_id),
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        results["learning"] = learning_result

        optimize_result = await workflow.execute_activity(
            "optimize_policy",
            args=(channel_id, learning_result, analytics_result, tenant_id),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        results["optimize"] = optimize_result

        published = (
            publish_result.get("status") == "completed"
            and bool(publish_result.get("video_publication_id"))
        )
        return {
            **results,
            "channel_id": channel_id,
            "topic": topic,
            "video_id": (video or {}).get("video_id") if isinstance(video, dict) else None,
            "clip_count": len((clips or {}).get("candidates", [])) if isinstance(clips, dict) else 0,
            "published": published,
            "status": "COMPLETED" if published else "COMPLETED_WITH_WARNINGS",
            "loop_complete": True,
        }


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


try:
    AgentWorkflow  # noqa: F401
except NameError:
    AgentWorkflow = InProcessAgentWorkflow  # type: ignore
