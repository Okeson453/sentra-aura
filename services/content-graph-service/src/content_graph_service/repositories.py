"""Repositories for the Content Asset Graph."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from content_graph_service.models import ContentNode, ContentEdge, LineageRecord


class NodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, node_id: UUID) -> ContentNode | None:
        return self.db.query(ContentNode).filter(ContentNode.id == node_id).first()

    def list(self, node_types: list[str] | None = None, channel_id: str | None = None, tenant_id: str | None = None, status: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[ContentNode], int]:
        q = self.db.query(ContentNode)
        if node_types:
            q = q.filter(ContentNode.node_type.in_(node_types))
        if channel_id:
            q = q.filter(ContentNode.channel_id == channel_id)
        if tenant_id:
            q = q.filter(ContentNode.tenant_id == tenant_id)
        if status:
            q = q.filter(ContentNode.status == status)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> ContentNode:
        node = ContentNode(**data)
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def update(self, node_id: UUID, updates: dict[str, Any]) -> ContentNode | None:
        node = self.get(node_id)
        if not node:
            return None
        for k, v in updates.items():
            setattr(node, k, v)
        self.db.commit()
        self.db.refresh(node)
        return node

    def delete(self, node_id: UUID) -> bool:
        node = self.get(node_id)
        if not node:
            return False
        self.db.delete(node)
        self.db.commit()
        return True


class EdgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, edge_id: UUID) -> ContentEdge | None:
        return self.db.query(ContentEdge).filter(ContentEdge.id == edge_id).first()

    def list_by_node(self, node_id: UUID, direction: str = "both") -> list[ContentEdge]:
        q = self.db.query(ContentEdge)
        if direction == "out":
            q = q.filter(ContentEdge.source_id == node_id)
        elif direction == "in":
            q = q.filter(ContentEdge.target_id == node_id)
        else:
            q = q.filter((ContentEdge.source_id == node_id) | (ContentEdge.target_id == node_id))
        return q.all()

    def create(self, data: dict[str, Any]) -> ContentEdge:
        edge = ContentEdge(**data)
        self.db.add(edge)
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def delete(self, edge_id: UUID) -> bool:
        edge = self.get(edge_id)
        if not edge:
            return False
        self.db.delete(edge)
        self.db.commit()
        return True


class LineageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, record_id: UUID) -> LineageRecord | None:
        return self.db.query(LineageRecord).filter(LineageRecord.id == record_id).first()

    def list_by_node(self, node_id: UUID) -> list[LineageRecord]:
        return self.db.query(LineageRecord).filter(LineageRecord.node_id == node_id).order_by(LineageRecord.created_at.desc()).all()

    def create(self, data: dict[str, Any]) -> LineageRecord:
        rec = LineageRecord(**data)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec
