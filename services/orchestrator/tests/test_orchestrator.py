"""Tests for the orchestrator."""
from __future__ import annotations

from orchestrator.state_machine import WorkflowExecution, WorkflowState, TaskState, TaskNode
from orchestrator.scheduler import DAGScheduler


def test_workflow_execution():
    wf = WorkflowExecution(workflow_id="W1", workflow_type="test", channel_id="C1")
    assert wf.state == WorkflowState.PENDING


def test_task_node():
    task = TaskNode(task_id="T1", task_type="research", agent_type="IntelligenceAgent")
    assert task.state == TaskState.PENDING
    assert task.retries == 0


def test_dag_scheduler_build():
    tasks = [
        {"task_id": "T1", "task_type": "research", "agent_type": "A1", "dependencies": []},
        {"task_id": "T2", "task_type": "draft", "agent_type": "A2", "dependencies": ["T1"]},
    ]
    dag = DAGScheduler.build_dag(tasks)
    assert len(dag) == 2
    assert dag["T2"].dependencies == ["T1"]


def test_topological_sort():
    tasks = [
        {"task_id": "T1", "task_type": "research", "agent_type": "A1", "dependencies": []},
        {"task_id": "T2", "task_type": "draft", "agent_type": "A2", "dependencies": ["T1"]},
        {"task_id": "T3", "task_type": "render", "agent_type": "A3", "dependencies": ["T2"]},
    ]
    dag = DAGScheduler.build_dag(tasks)
    order = DAGScheduler.topological_sort(dag)
    assert order.index("T1") < order.index("T2")
    assert order.index("T2") < order.index("T3")


def test_detect_cycle():
    tasks = [
        {"task_id": "T1", "task_type": "a", "agent_type": "A1", "dependencies": ["T2"]},
        {"task_id": "T2", "task_type": "b", "agent_type": "A2", "dependencies": ["T1"]},
    ]
    dag = DAGScheduler.build_dag(tasks)
    cycle = DAGScheduler.detect_cycles(dag)
    assert cycle is not None
    assert "T1" in cycle and "T2" in cycle


def test_no_cycle():
    tasks = [
        {"task_id": "T1", "task_type": "a", "agent_type": "A1", "dependencies": []},
        {"task_id": "T2", "task_type": "b", "agent_type": "A2", "dependencies": ["T1"]},
    ]
    dag = DAGScheduler.build_dag(tasks)
    cycle = DAGScheduler.detect_cycles(dag)
    assert cycle is None
