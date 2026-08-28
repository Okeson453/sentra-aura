"""Tests for content graph service."""
from __future__ import annotations

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock

from content_graph_service.models import ContentNode, ContentEdge, LineageRecord
from content_graph_service.graph_queries import GraphTraversal, TraversalResult


class TestGraphTraversal:
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        from unittest.mock import MagicMock, create_autospec
        from sqlalchemy.orm import Session
        return create_autospec(Session)

    def test_shortest_path_empty(self, mock_db):
        gt = GraphTraversal(mock_db)
        mock_db.execute.return_value.fetchone.return_value = None
        path = gt.shortest_path("a", "b")
        assert path == []

    def test_shortest_path_found(self, mock_db):
        gt = GraphTraversal(mock_db)
        mock_row = MagicMock()
        mock_row.path = ["a", "c", "b"]
        mock_db.execute.return_value.fetchone.return_value = mock_row
        path = gt.shortest_path("a", "b")
        assert path == ["a", "c", "b"]

    def test_get_lineage_path(self, mock_db):
        gt = GraphTraversal(mock_db)
        mock_db.execute.return_value.mappings.return_value.all.return_value = [
            {"id": uuid4(), "node_type": "VIDEO", "channel_id": "ch-1", "tenant_id": "t-1",
             "title": "Video", "description": "", "status": "ACTIVE", "version": 1,
             "payload": {}, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(), "depth": 0},
        ]
        lineage = gt.get_lineage_path("node-1")
        assert len(lineage) == 1
        assert lineage[0]["node_type"] == "VIDEO"

    def test_get_provenance_chain(self, mock_db):
        gt = GraphTraversal(mock_db)
        mock_db.execute.return_value.mappings.return_value.all.return_value = [
            {"id": uuid4(), "node_id": uuid4(), "record_type": "SOURCE", "agent_id": "agent-1",
             "action": "create", "inputs": {}, "outputs": {}, "metadata_json": {},
             "created_at": datetime.utcnow()},
        ]
        records = gt.get_provenance_chain("node-1")
        assert len(records) == 1
        assert records[0]["record_type"] == "SOURCE"

    def test_bfs_direction_in(self, mock_db):
        gt = GraphTraversal(mock_db)
        mock_db.execute.return_value.mappings.return_value.all.return_value = [
            {"id": uuid4(), "node_type": "SCRIPT", "channel_id": "ch-1", "tenant_id": "t-1",
             "title": "Script", "description": "", "status": "ACTIVE", "version": 1,
             "payload": {}, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(), "depth": 1},
        ]
        result = gt.bfs("node-1", direction="in", max_depth=5)
        assert len(result.nodes) == 1

    def test_dfs_direction_out(self, mock_db):
        gt = GraphTraversal(mock_db)
        mock_db.execute.return_value.mappings.return_value.all.return_value = [
            {"id": uuid4(), "node_type": "CLIP", "channel_id": "ch-1", "tenant_id": "t-1",
             "title": "Clip", "description": "", "status": "ACTIVE", "version": 1,
             "payload": {}, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(), "depth": 1},
        ]
        result = gt.dfs("node-1", direction="out", max_depth=5)
        assert len(result.nodes) == 1


class TestContentGraphModels:
    def test_node_creation(self):
        node = ContentNode(
            node_type="VIDEO",
            channel_id="ch-1",
            tenant_id="t-1",
            title="Test Video",
            payload={"duration": 300},
        )
        assert node.node_type == "VIDEO"
        assert node.payload["duration"] == 300

    def test_edge_creation(self):
        edge = ContentEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type="CLIPPED_FROM",
            channel_id="ch-1",
            weight=0.95,
        )
        assert edge.edge_type == "CLIPPED_FROM"
        assert edge.weight == 0.95

    def test_lineage_record_creation(self):
        record = LineageRecord(
            node_id=uuid4(),
            record_type="AGENT",
            agent_id="agent-1",
            action="generate_script",
            inputs={"topic": "AI"},
            outputs={"script": "Hello world"},
        )
        assert record.record_type == "AGENT"
        assert record.outputs["script"] == "Hello world"
