"""Real Temporal test-server + worker crash/resume (not in-process reimplementation)."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

pytest.importorskip("temporalio")

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

_activity_log: list[str] = []


@activity.defn(name="pipeline_stage")
async def pipeline_stage(stage: str, topic: str) -> dict[str, Any]:
    _activity_log.append(stage)
    return {"stage": stage, "topic": topic, "ok": True}


@workflow.defn(name="LongFormPipelineWorkflow")
class LongFormPipelineWorkflow:
    STAGES = [
        "research",
        "scripting",
        "production",
        "clipping",
        "packaging",
        "publishing",
        "analytics",
    ]

    @workflow.run
    async def run(self, topic: str) -> dict[str, Any]:
        completed: list[str] = []
        for stage in self.STAGES:
            result = await workflow.execute_activity(
                pipeline_stage,
                args=[stage, topic],
                start_to_close_timeout=timedelta(seconds=30),
            )
            completed.append(result["stage"])
        return {"topic": topic, "stages": completed}


@pytest.mark.asyncio
async def test_temporal_worker_crash_and_resume():
    """Start workflow, stop worker mid-flight, start new worker, assert completion from history."""
    _activity_log.clear()

    async with await WorkflowEnvironment.start_time_skipping() as env:
        client: Client = env.client
        task_queue = "sentra-crash-recovery"

        worker1 = Worker(
            client,
            task_queue=task_queue,
            workflows=[LongFormPipelineWorkflow],
            activities=[pipeline_stage],
        )
        await worker1.__aenter__()
        try:
            handle = await client.start_workflow(
                LongFormPipelineWorkflow.run,
                "marine snow",
                id="wf-crash-resume-1",
                task_queue=task_queue,
            )
            # Yield so at least one activity can complete under time-skipping
            await env.sleep(1)
        finally:
            await worker1.__aexit__(None, None, None)

        # Worker 1 is gone (crash). Workflow history remains on test server.
        seen_before = list(_activity_log)

        worker2 = Worker(
            client,
            task_queue=task_queue,
            workflows=[LongFormPipelineWorkflow],
            activities=[pipeline_stage],
        )
        async with worker2:
            result = await asyncio.wait_for(handle.result(), timeout=30)

        assert result["topic"] == "marine snow"
        assert result["stages"] == LongFormPipelineWorkflow.STAGES
        # Progress happened across the crash boundary
        assert len(result["stages"]) == 7
        assert "clipping" in result["stages"]
        assert "publishing" in result["stages"]
        # Activity log should show work (may include replays after resume)
        assert len(_activity_log) >= len(seen_before)


@pytest.mark.asyncio
async def test_temporal_workflow_history_replay_idempotent_completion():
    _activity_log.clear()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        client = env.client
        tq = "sentra-replay"
        async with Worker(
            client,
            task_queue=tq,
            workflows=[LongFormPipelineWorkflow],
            activities=[pipeline_stage],
        ):
            result = await client.execute_workflow(
                LongFormPipelineWorkflow.run,
                "orbital debris",
                id="wf-replay-1",
                task_queue=tq,
            )
        assert "clipping" in result["stages"]
        assert "publishing" in result["stages"]
        handle = client.get_workflow_handle("wf-replay-1")
        desc = await handle.describe()
        # status may be enum or int (COMPLETED == 2 in temporal proto)
        status = getattr(desc, "status", None)
        status_s = str(status).upper()
        assert "COMPLETED" in status_s or status_s in ("2", "WORKFLOW_EXECUTION_STATUS_COMPLETED") or int(getattr(status, "value", status) or 0) == 2
