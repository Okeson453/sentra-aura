"""Graph query models for the Content Asset Graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_graph_client.node import ContentNodeType


@dataclass
class GraphQuery:
    """Query parameters for the Content Asset Graph."""
    node_types: list[ContentNodeType] | None = None
    channel_id: str | None = None
    tenant_id: str | None = None
    status: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = 100
    offset: int = 0
    sort_by: str = "created_at"
    sort_order: str = "desc"
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphQueryResult:
    """Result of a graph query."""
    nodes: list[Any] = field(default_factory=list)
    edges: list[Any] = field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0


@dataclass
class LineageQuery:
    """Query parameters for lineage traversal."""
    start_node_id: str = ""
    direction: str = "both"  # out, in, both
    max_depth: int = 10
    node_types: list[str] | None = None
    include_edges: bool = True
    include_records: bool = True
