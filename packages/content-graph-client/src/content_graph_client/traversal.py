"""Graph traversal helpers for the Content Asset Graph client.

Provides high-level lineage query builders and path reconstruction.
"""
from __future__ import annotations

from typing import Any

from content_graph_client.node import ContentNode
from content_graph_client.edge import ContentEdge
from content_graph_client.lineage import LineageRecord


class LineageBuilder:
    """Builder for constructing lineage queries and interpreting results."""

    def __init__(self, start_node_id: str) -> None:
        self.start_node_id = start_node_id
        self._direction = "both"
        self._max_depth = 10
        self._node_types: list[str] | None = None

    def direction(self, direction: str) -> "LineageBuilder":
        self._direction = direction
        return self

    def max_depth(self, depth: int) -> "LineageBuilder":
        self._max_depth = depth
        return self

    def filter_types(self, node_types: list[str]) -> "LineageBuilder":
        self._node_types = node_types
        return self

    def build(self) -> dict[str, Any]:
        return {
            "start_node_id": self.start_node_id,
            "direction": self._direction,
            "max_depth": self._max_depth,
            "node_types": self._node_types,
        }


def reconstruct_lineage_path(
    nodes: list[ContentNode],
    edges: list[ContentEdge],
    start_node_id: str,
) -> list[ContentNode]:
    """Reconstruct a lineage path from nodes and edges."""
    node_map = {str(n.node_id): n for n in nodes}
    edge_map: dict[str, list[str]] = {}
    for e in edges:
        sid = str(e.source_id)
        tid = str(e.target_id)
        if sid not in edge_map:
            edge_map[sid] = []
        edge_map[sid].append(tid)

    path: list[ContentNode] = []
    current = start_node_id
    visited: set[str] = set()
    while current in node_map and current not in visited:
        visited.add(current)
        path.append(node_map[current])
        # Follow outgoing edges
        next_nodes = edge_map.get(current, [])
        current = next_nodes[0] if next_nodes else ""
    return path


def find_common_ancestors(
    node_ids: list[str],
    nodes: list[ContentNode],
    edges: list[ContentEdge],
) -> list[ContentNode]:
    """Find common ancestors among a set of nodes."""
    if not node_ids:
        return []

    # Build reverse adjacency (child -> parents)
    parents: dict[str, set[str]] = {}
    for e in edges:
        tid = str(e.target_id)
        sid = str(e.source_id)
        if tid not in parents:
            parents[tid] = set()
        parents[tid].add(sid)

    def get_ancestors(node_id: str) -> set[str]:
        result: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            for p in parents.get(current, []):
                if p not in result:
                    result.add(p)
                    stack.append(p)
        return result

    all_ancestors = [get_ancestors(nid) for nid in node_ids]
    if not all_ancestors:
        return []
    common = set.intersection(*all_ancestors)
    node_map = {str(n.node_id): n for n in nodes}
    return [node_map[nid] for nid in common if nid in node_map]
