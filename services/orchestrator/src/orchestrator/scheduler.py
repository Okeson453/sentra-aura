"""DAG scheduler for workflow execution.

Matches Architecture §5.2.
"""
from __future__ import annotations

from typing import Any

from orchestrator.state_machine import WorkflowExecution, TaskNode, TaskState


class DAGScheduler:
    """Schedules tasks in a workflow DAG based on dependencies."""

    @staticmethod
    def build_dag(tasks: list[dict[str, Any]]) -> dict[str, TaskNode]:
        """Build a task map from a list of task definitions."""
        task_map: dict[str, TaskNode] = {}
        for t in tasks:
            node = TaskNode(
                task_id=t["task_id"],
                task_type=t["task_type"],
                agent_type=t["agent_type"],
                inputs=t.get("inputs", {}),
                dependencies=t.get("dependencies", []),
                max_retries=t.get("max_retries", 3),
            )
            task_map[node.task_id] = node
        return task_map

    @staticmethod
    def topological_sort(tasks: dict[str, TaskNode]) -> list[str]:
        """Return task IDs in topological order."""
        visited: set[str] = set()
        result: list[str] = []

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            visited.add(task_id)
            for dep in tasks.get(task_id, TaskNode(task_id=task_id, task_type="", agent_type="")).dependencies:
                visit(dep)
            result.append(task_id)

        for task_id in tasks:
            visit(task_id)
        return result

    @staticmethod
    def detect_cycles(tasks: dict[str, TaskNode]) -> list[str] | None:
        """Detect cycles in the DAG. Returns cycle path if found, None otherwise."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {tid: WHITE for tid in tasks}
        path: list[str] = []

        def dfs(task_id: str) -> list[str] | None:
            color[task_id] = GRAY
            path.append(task_id)
            for dep in tasks[task_id].dependencies:
                if dep not in tasks:
                    continue
                if color[dep] == GRAY:
                    cycle_start = path.index(dep)
                    return path[cycle_start:] + [dep]
                if color[dep] == WHITE:
                    result = dfs(dep)
                    if result:
                        return result
            path.pop()
            color[task_id] = BLACK
            return None

        for tid in tasks:
            if color[tid] == WHITE:
                cycle = dfs(tid)
                if cycle:
                    return cycle
        return None
