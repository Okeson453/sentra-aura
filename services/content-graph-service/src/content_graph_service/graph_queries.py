"""Graph traversal and lineage query engine for Content Asset Graph.

Supports BFS/DFS traversal, shortest path, ancestry/descendant queries,
and temporal lineage reconstruction using Postgres recursive CTEs.
Matches Architecture §4.2 and Backend Spec §13.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from content_graph_service.models import ContentNode, ContentEdge, LineageRecord


@dataclass
class TraversalResult:
    """Result of a graph traversal."""
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    depth: int = 0


class GraphTraversal:
    """Graph traversal engine for the Content Asset Graph using Postgres recursive CTEs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _node_to_dict(self, row: Any) -> dict[str, Any]:
        return {
            "node_id": str(row.id) if hasattr(row, "id") else str(row.node_id),
            "node_type": row.node_type,
            "channel_id": row.channel_id,
            "tenant_id": row.tenant_id,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "version": row.version,
            "payload": row.payload,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "depth": getattr(row, "depth", 0),
        }

    def _edge_to_dict(self, edge: ContentEdge) -> dict[str, Any]:
        return {
            "edge_id": str(edge.id),
            "source_id": str(edge.source_id),
            "target_id": str(edge.target_id),
            "edge_type": edge.edge_type,
            "channel_id": edge.channel_id,
            "weight": edge.weight,
            "metadata": edge.metadata_json,
            "created_at": edge.created_at.isoformat() if edge.created_at else None,
        }

    def get_descendants(
        self,
        start_node_id: str,
        max_depth: int = 10,
        node_types: list[str] | None = None,
    ) -> TraversalResult:
        """Get all descendant nodes using a Postgres recursive CTE."""
        cte_sql = """
        WITH RECURSIVE descendants AS (
            SELECT id, node_type, channel_id, tenant_id, title, description, status, version, payload, created_at, updated_at, 0 AS depth
            FROM content_nodes
            WHERE id = :start_id
            UNION ALL
            SELECT n.id, n.node_type, n.channel_id, n.tenant_id, n.title, n.description, n.status, n.version, n.payload, n.created_at, n.updated_at, d.depth + 1
            FROM content_nodes n
            INNER JOIN content_edges e ON n.id = e.target_id
            INNER JOIN descendants d ON e.source_id = d.id
            WHERE d.depth < :max_depth
        )
        SELECT * FROM descendants
        ORDER BY depth, created_at
        """
        result = self.db.execute(text(cte_sql), {"start_id": start_node_id, "max_depth": max_depth})
        rows = result.mappings().all()

        nodes = []
        for row in rows:
            d = dict(row)
            if node_types and d.get("node_type") not in node_types:
                continue
            nodes.append(self._node_to_dict(type("Row", (), d)()))

        # Fetch edges between these nodes
        node_ids = [n["node_id"] for n in nodes]
        edges = []
        if len(node_ids) > 1:
            edge_rows = self.db.query(ContentEdge).filter(
                ContentEdge.source_id.in_(node_ids),
                ContentEdge.target_id.in_(node_ids),
            ).all()
            edges = [self._edge_to_dict(e) for e in edge_rows]

        return TraversalResult(
            nodes=nodes,
            edges=edges,
            path=[n["node_id"] for n in nodes],
            depth=max((n.get("depth", 0) for n in nodes), default=0),
        )

    def get_ancestors(
        self,
        start_node_id: str,
        max_depth: int = 10,
        node_types: list[str] | None = None,
    ) -> TraversalResult:
        """Get all ancestor nodes using a Postgres recursive CTE."""
        cte_sql = """
        WITH RECURSIVE ancestors AS (
            SELECT id, node_type, channel_id, tenant_id, title, description, status, version, payload, created_at, updated_at, 0 AS depth
            FROM content_nodes
            WHERE id = :start_id
            UNION ALL
            SELECT n.id, n.node_type, n.channel_id, n.tenant_id, n.title, n.description, n.status, n.version, n.payload, n.created_at, n.updated_at, a.depth + 1
            FROM content_nodes n
            INNER JOIN content_edges e ON n.id = e.source_id
            INNER JOIN ancestors a ON e.target_id = a.id
            WHERE a.depth < :max_depth
        )
        SELECT * FROM ancestors
        ORDER BY depth, created_at
        """
        result = self.db.execute(text(cte_sql), {"start_id": start_node_id, "max_depth": max_depth})
        rows = result.mappings().all()

        nodes = []
        for row in rows:
            d = dict(row)
            if node_types and d.get("node_type") not in node_types:
                continue
            nodes.append(self._node_to_dict(type("Row", (), d)()))

        node_ids = [n["node_id"] for n in nodes]
        edges = []
        if len(node_ids) > 1:
            edge_rows = self.db.query(ContentEdge).filter(
                ContentEdge.source_id.in_(node_ids),
                ContentEdge.target_id.in_(node_ids),
            ).all()
            edges = [self._edge_to_dict(e) for e in edge_rows]

        return TraversalResult(
            nodes=nodes,
            edges=edges,
            path=[n["node_id"] for n in nodes],
            depth=max((n.get("depth", 0) for n in nodes), default=0),
        )

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 10,
    ) -> list[str]:
        """Find shortest path between two nodes using a Postgres recursive CTE."""
        cte_sql = """
        WITH RECURSIVE path_cte AS (
            SELECT target_id AS node_id, ARRAY[source_id, target_id] AS path, 1 AS depth
            FROM content_edges
            WHERE source_id = :source_id
            UNION ALL
            SELECT e.target_id, p.path || e.target_id, p.depth + 1
            FROM content_edges e
            INNER JOIN path_cte p ON e.source_id = p.node_id
            WHERE NOT e.target_id = ANY(p.path) AND p.depth < :max_depth
        )
        SELECT path FROM path_cte WHERE node_id = :target_id LIMIT 1
        """
        result = self.db.execute(text(cte_sql), {"source_id": source_id, "target_id": target_id, "max_depth": max_depth})
        row = result.fetchone()
        if row and row.path:
            return [str(n) for n in row.path]
        return []

    def get_lineage_path(self, node_id: str, max_depth: int = 20) -> list[dict[str, Any]]:
        """Reconstruct full lineage path from root to this node using recursive CTE."""
        cte_sql = """
        WITH RECURSIVE lineage_cte AS (
            SELECT id, node_type, channel_id, tenant_id, title, description, status, version, payload, created_at, updated_at, 0 AS depth
            FROM content_nodes
            WHERE id = :node_id
            UNION ALL
            SELECT n.id, n.node_type, n.channel_id, n.tenant_id, n.title, n.description, n.status, n.version, n.payload, n.created_at, n.updated_at, l.depth + 1
            FROM content_nodes n
            INNER JOIN content_edges e ON n.id = e.source_id
            INNER JOIN lineage_cte l ON e.target_id = l.id
            WHERE l.depth < :max_depth
        )
        SELECT * FROM lineage_cte ORDER BY depth DESC
        """
        result = self.db.execute(text(cte_sql), {"node_id": node_id, "max_depth": max_depth})
        rows = result.mappings().all()
        return [self._node_to_dict(type("Row", (), dict(r))()) for r in rows]

    def get_provenance_chain(self, node_id: str) -> list[dict[str, Any]]:
        """Get all lineage records for a node and its ancestors using recursive CTE."""
        cte_sql = """
        WITH RECURSIVE ancestor_ids AS (
            SELECT id FROM content_nodes WHERE id = :node_id
            UNION ALL
            SELECT n.id
            FROM content_nodes n
            INNER JOIN content_edges e ON n.id = e.source_id
            INNER JOIN ancestor_ids a ON e.target_id = a.id
        )
        SELECT lr.* FROM lineage_records lr
        INNER JOIN ancestor_ids a ON lr.node_id = a.id
        ORDER BY lr.created_at ASC
        """
        result = self.db.execute(text(cte_sql), {"node_id": node_id})
        rows = result.mappings().all()
        return [
            {
                "record_id": str(r["id"]),
                "node_id": str(r["node_id"]),
                "record_type": r["record_type"],
                "agent_id": r["agent_id"],
                "action": r["action"],
                "inputs": r["inputs"],
                "outputs": r["outputs"],
                "metadata": r["metadata_json"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    def bfs(
        self,
        start_node_id: str,
        direction: str = "out",
        max_depth: int = 10,
        node_types: list[str] | None = None,
    ) -> TraversalResult:
        """Breadth-first search using recursive CTE."""
        if direction == "in":
            return self.get_ancestors(start_node_id, max_depth=max_depth, node_types=node_types)
        return self.get_descendants(start_node_id, max_depth=max_depth, node_types=node_types)

    def dfs(
        self,
        start_node_id: str,
        direction: str = "out",
        max_depth: int = 10,
        node_types: list[str] | None = None,
    ) -> TraversalResult:
        """Depth-first search using recursive CTE (same as BFS for CTE, ordering differs)."""
        result = self.bfs(start_node_id, direction=direction, max_depth=max_depth, node_types=node_types)
        # Reverse path for DFS feel when going inward
        if direction == "in":
            result.path = list(reversed(result.path))
        return result
