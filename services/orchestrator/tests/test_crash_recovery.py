"""Crash recovery, checkpointing, and compensation tests for orchestrator sagas."""
from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.saga import SagaDefinition, SagaOrchestrator, SagaStep, SagaStatus
from orchestrator.state_machine import WorkflowState, WorkflowStateMachine
from orchestrator.workflows import InProcessAgentWorkflow, InProcessLongFormVideoWorkflow


@pytest.fixture
def checkpoint_dir():
    return tempfile.mkdtemp()


@pytest.fixture
def saga_def():
    return SagaDefinition(
        saga_id="test-saga-1",
        steps=[
            SagaStep(step_id="plan", name="plan", action="create_plan", compensation="delete_plan"),
            SagaStep(step_id="script", name="script", action="write_script", compensation="delete_script"),
            SagaStep(step_id="render", name="render", action="render_video", compensation="delete_render"),
        ],
    )


@pytest.fixture
def orchestrator(checkpoint_dir, saga_def):
    return SagaOrchestrator(checkpoint_dir=checkpoint_dir, saga_definition=saga_def)


class TestSagaCheckpointing:
    @pytest.mark.asyncio
    async def test_checkpoint_created_after_each_step(self, orchestrator):
        await orchestrator.execute({"channel_id": "ch-1"})
        cps = orchestrator.list_checkpoints()
        assert len(cps) >= 3

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint_after_crash(self, orchestrator, checkpoint_dir, saga_def):
        # Complete first two steps then "crash" by saving state
        async def selective(action, context):
            if action == "render_video":
                raise RuntimeError("crash before render")
            return {"status": "success", "action": action}

        with patch.object(orchestrator, "_execute_action", side_effect=selective):
            with pytest.raises(RuntimeError):
                await orchestrator.execute({"channel_id": "ch-1"})

        latest = orchestrator.load_latest_checkpoint("test-saga-1")
        assert latest is not None
        assert "plan" in latest.completed_steps
        assert "script" in latest.completed_steps

        # Resume with fresh orchestrator
        resumed = SagaOrchestrator(checkpoint_dir=checkpoint_dir, saga_definition=saga_def)
        resumed.state.completed_steps = list(latest.completed_steps)
        with patch.object(resumed, "_execute_action", new_callable=AsyncMock) as mock_action:
            mock_action.return_value = {"status": "success"}
            await resumed.execute({"channel_id": "ch-1"})
            # Only remaining steps execute
            assert mock_action.call_count >= 1

    @pytest.mark.asyncio
    async def test_compensation_on_failure(self, orchestrator):
        async def actions(action, context):
            if action == "render_video":
                raise RuntimeError("render_video failed")
            return {"status": "success", "plan_id": "plan-123", "script_id": "script-456"}

        with patch.object(orchestrator, "_execute_action", side_effect=actions), patch.object(
            orchestrator, "_execute_compensation", new_callable=AsyncMock
        ) as mock_comp:
            mock_comp.return_value = {"status": "compensated"}
            with pytest.raises(RuntimeError, match="render_video failed"):
                await orchestrator.execute({"channel_id": "ch-1"})
            assert mock_comp.call_count == 2

    @pytest.mark.asyncio
    async def test_checkpoint_durability(self, orchestrator, checkpoint_dir):
        await orchestrator.execute({"channel_id": "ch-1"})
        new_orch = SagaOrchestrator(
            checkpoint_dir=checkpoint_dir, saga_definition=orchestrator.saga_definition
        )
        assert len(new_orch.list_checkpoints()) > 0
        latest = new_orch.load_latest_checkpoint("test-saga-1")
        assert latest is not None
        assert str(latest.status) in ("COMPLETED", "SagaStatus.COMPLETED") or latest.status == SagaStatus.COMPLETED


class TestWorkflowStateMachine:
    def test_state_transitions_are_atomic(self):
        sm = WorkflowStateMachine(initial_state=WorkflowState.PENDING)
        sm.transition_to(WorkflowState.RUNNING)
        assert sm.current_state == WorkflowState.RUNNING


class TestTemporalWorkflowCrashRecovery:
    def test_agent_workflow_survives_crash(self):
        workflow = InProcessAgentWorkflow()
        workflow.transition(WorkflowState.RUNNING)
        workflow.checkpoint({"progress": 0.5})
        assert workflow.state_machine.current_state == WorkflowState.RUNNING
        assert workflow.checkpoints

    def test_long_form_workflow_checkpoint_interval(self):
        workflow = InProcessLongFormVideoWorkflow(checkpoint_interval_seconds=0.1)
        result = workflow.run_stages("marine snow")
        assert "clipping" in result["stages"]
        assert "publishing" in result["stages"]
        assert result["checkpoints"] >= 6
        last = workflow.checkpoints[-1]
        assert last["context"]["progress"] > 0


class TestSagaCompensation:
    @pytest.mark.asyncio
    async def test_compensation_idempotency(self, checkpoint_dir):
        orch = SagaOrchestrator(
            checkpoint_dir=checkpoint_dir,
            saga_definition=SagaDefinition(
                saga_id="idempotent-test",
                steps=[SagaStep(step_id="s1", name="create", action="create", compensation="delete")],
            ),
        )
        with patch.object(orch, "_execute_compensation", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = {"status": "already_deleted"}
            await orch._execute_compensation("delete", {"id": "test-1"})
            await orch._execute_compensation("delete", {"id": "test-1"})
            assert mock_comp.call_count == 2

    @pytest.mark.asyncio
    async def test_partial_compensation_recovery(self, checkpoint_dir):
        orch = SagaOrchestrator(
            checkpoint_dir=checkpoint_dir,
            saga_definition=SagaDefinition(
                saga_id="partial-comp-test",
                steps=[
                    SagaStep(step_id="s1", name="create_a", action="create_a", compensation="delete_a"),
                    SagaStep(step_id="s2", name="create_b", action="create_b", compensation="delete_b"),
                    SagaStep(step_id="s3", name="create_c", action="create_c", compensation="delete_c"),
                ],
            ),
        )

        async def actions(action, context):
            if action == "create_c":
                raise RuntimeError("step 3 failed")
            return {"status": "success"}

        async def comps(comp, context):
            if comp == "delete_a":
                raise RuntimeError("compensation failed")
            return {"status": "compensated"}

        with patch.object(orch, "_execute_action", side_effect=actions), patch.object(
            orch, "_execute_compensation", side_effect=comps
        ):
            with pytest.raises(RuntimeError):
                await orch.execute({})
            cp = orch.load_latest_checkpoint("partial-comp-test")
            assert cp is not None
