"""Tests for content-graph-client."""
from __future__ import annotations

import pytest
from uuid import uuid4

from content_graph_client.node import ContentNode, ContentNodeType
from content_graph_client.edge import ContentEdge, ContentEdgeType
from content_graph_client.lineage import LineageRecord, LineageRecordType
from content_graph_client.query import GraphQuery, LineageQuery
from content_graph_client.traversal import LineageBuilder, reconstruct_lineage_path, find_common_ancestors


class TestContentNode:
    def test_node_creation(self):
        node = ContentNode(
            node_type=ContentNodeType.VIDEO,
            channel_id="ch-1",
            tenant_id="t-1",
            title="Test Video",
            payload={"duration": 300},
        )
        assert node.node_type == ContentNodeType.VIDEO
        assert node.to_dict()["node_type"] == "VIDEO"

    def test_node_from_dict(self):
        node = ContentNode(
            node_type=ContentNodeType.SCRIPT,
            channel_id="ch-1",
            tenant_id="t-1",
            title="Script",
        )
        restored = ContentNode.from_dict(node.to_dict())
        assert restored.title == "Script"
        assert restored.node_type == ContentNodeType.SCRIPT


class TestContentEdge:
    def test_edge_creation(self):
        edge = ContentEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=ContentEdgeType.CLIPPED_FROM,
            channel_id="ch-1",
            weight=0.95,
        )
        assert edge.edge_type == ContentEdgeType.CLIPPED_FROM
        assert edge.to_dict()["edge_type"] == "CLIPPED_FROM"

    def test_edge_from_dict(self):
        edge = ContentEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=ContentEdgeType.RENDERED_FROM,
        )
        restored = ContentEdge.from_dict(edge.to_dict())
        assert restored.edge_type == ContentEdgeType.RENDERED_FROM


class TestLineageRecord:
    def test_record_creation(self):
        record = LineageRecord(
            node_id=uuid4(),
            record_type=LineageRecordType.AGENT,
            agent_id="agent-1",
            action="generate",
            inputs={"topic": "AI"},
            outputs={"content": "Hello"},
        )
        assert record.record_type == LineageRecordType.AGENT
        assert record.to_dict()["record_type"] == "AGENT"


class TestLineageBuilder:
    def test_builder_chain(self):
        builder = LineageBuilder("node-1")
        query = builder.direction("in").max_depth(5).filter_types(["VIDEO", "CLIP"]).build()
        assert query["start_node_id"] == "node-1"
        assert query["direction"] == "in"
        assert query["max_depth"] == 5
        assert query["node_types"] == ["VIDEO", "CLIP"]


class TestTraversalHelpers:
    def test_reconstruct_lineage_path(self):
        n1 = ContentNode(node_type=ContentNodeType.TOPIC, channel_id="ch-1", tenant_id="t-1", title="Topic")
        n2 = ContentNode(node_type=ContentNodeType.SCRIPT, channel_id="ch-1", tenant_id="t-1", title="Script")
        n3 = ContentNode(node_type=ContentNodeType.VIDEO, channel_id="ch-1", tenant_id="t-1", title="Video")

        e1 = ContentEdge(source_id=n1.node_id, target_id=n2.node_id, edge_type=ContentEdgeType.DRAFTED_FROM, channel_id="ch-1")
        e2 = ContentEdge(source_id=n2.node_id, target_id=n3.node_id, edge_type=ContentEdgeType.RENDERED_FROM, channel_id="ch-1")

        path = reconstruct_lineage_path([n1, n2, n3], [e1, e2], str(n1.node_id))
        assert len(path) == 3
        assert path[0].title == "Topic"
        assert path[2].title == "Video"

    def test_find_common_ancestors(self):
        n1 = ContentNode(node_type=ContentNodeType.TOPIC, channel_id="ch-1", tenant_id="t-1", title="Common Topic")
        n2 = ContentNode(node_type=ContentNodeType.SCRIPT, channel_id="ch-1", tenant_id="t-1", title="Script 1")
        n3 = ContentNode(node_type=ContentNodeType.SCRIPT, channel_id="ch-1", tenant_id="t-1", title="Script 2")

        e1 = ContentEdge(source_id=n1.node_id, target_id=n2.node_id, edge_type=ContentEdgeType.DRAFTED_FROM, channel_id="ch-1")
        e2 = ContentEdge(source_id=n1.node_id, target_id=n3.node_id, edge_type=ContentEdgeType.DRAFTED_FROM, channel_id="ch-1")

        common = find_common_ancestors([str(n2.node_id), str(n3.node_id)], [n1, n2, n3], [e1, e2])
        assert len(common) == 1
        assert common[0].title == "Common Topic"

    def test_find_common_ancestors_no_common(self):
        n1 = ContentNode(node_type=ContentNodeType.TOPIC, channel_id="ch-1", tenant_id="t-1", title="Topic 1")
        n2 = ContentNode(node_type=ContentNodeType.TOPIC, channel_id="ch-1", tenant_id="t-1", title="Topic 2")
        n3 = ContentNode(node_type=ContentNodeType.SCRIPT, channel_id="ch-1", tenant_id="t-1", title="Script")

        e1 = ContentEdge(source_id=n1.node_id, target_id=n3.node_id, edge_type=ContentEdgeType.DRAFTED_FROM, channel_id="ch-1")

        common = find_common_ancestors([str(n2.node_id), str(n3.node_id)], [n1, n2, n3], [e1])
        assert len(common) == 0
