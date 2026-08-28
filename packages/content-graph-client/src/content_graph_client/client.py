"""Content Graph Service client for SentraAura."""
from __future__ import annotations

import httpx
from typing import Any

from content_graph_client.node import ContentNode, ContentNodeType
from content_graph_client.edge import ContentEdge, ContentEdgeType
from content_graph_client.lineage import LineageRecord, LineageRecordType
from content_graph_client.query import GraphQuery, GraphQueryResult, LineageQuery
from content_graph_client.traversal import LineageBuilder, reconstruct_lineage_path, find_common_ancestors


class ContentGraphClient:
    """HTTP client for the Content Asset Graph service."""

    def __init__(self, base_url: str = "http://localhost:8002", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def create_node(self, node: ContentNode) -> dict[str, Any]:
        response = await self._client.post("/nodes", json=node.to_dict())
        response.raise_for_status()
        return response.json()

    async def get_node(self, node_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/nodes/{node_id}")
        response.raise_for_status()
        return response.json()

    async def list_nodes(self, query: GraphQuery | None = None) -> dict[str, Any]:
        params = {}
        if query:
            if query.node_types:
                params["node_types"] = [t.value for t in query.node_types]
            if query.channel_id:
                params["channel_id"] = query.channel_id
            if query.tenant_id:
                params["tenant_id"] = query.tenant_id
            if query.status:
                params["status"] = query.status
            params["limit"] = query.limit
            params["offset"] = query.offset
        response = await self._client.get("/nodes", params=params)
        response.raise_for_status()
        return response.json()

    async def create_edge(self, edge: ContentEdge) -> dict[str, Any]:
        response = await self._client.post("/edges", json=edge.to_dict())
        response.raise_for_status()
        return response.json()

    async def get_lineage(self, node_id: str) -> list[dict[str, Any]]:
        response = await self._client.get(f"/nodes/{node_id}/lineage")
        response.raise_for_status()
        return response.json()

    async def traverse(self, query: LineageQuery) -> dict[str, Any]:
        response = await self._client.post("/traverse", json=query.__dict__)
        response.raise_for_status()
        return response.json()

    async def get_ancestors(self, node_id: str, max_depth: int = 10) -> dict[str, Any]:
        response = await self._client.get(f"/nodes/{node_id}/ancestors", params={"max_depth": max_depth})
        response.raise_for_status()
        return response.json()

    async def get_descendants(self, node_id: str, max_depth: int = 10) -> dict[str, Any]:
        response = await self._client.get(f"/nodes/{node_id}/descendants", params={"max_depth": max_depth})
        response.raise_for_status()
        return response.json()

    async def get_lineage_path(self, node_id: str, max_depth: int = 20) -> list[dict[str, Any]]:
        response = await self._client.get(f"/nodes/{node_id}/lineage-path", params={"max_depth": max_depth})
        response.raise_for_status()
        return response.json()

    async def get_provenance(self, node_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/nodes/{node_id}/provenance")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
