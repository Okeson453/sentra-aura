"""Pydantic schemas for Content Graph Service."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class NodeCreate(BaseModel):
    node_type: str = Field(..., min_length=1, max_length=50)
    channel_id: str = Field(..., min_length=1, max_length=32)
    tenant_id: str = Field(..., min_length=1, max_length=32)
    title: str = Field(default="", max_length=500)
    description: str | None = None
    status: str = Field(default="ACTIVE", max_length=20)
    version: int = Field(default=1, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class NodeUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    status: str | None = Field(default=None, max_length=20)
    version: int | None = Field(default=None, ge=1)
    payload: dict[str, Any] | None = None


class NodeResponse(BaseModel):
    node_id: str
    node_type: str
    channel_id: str
    tenant_id: str
    title: str
    description: str | None
    status: str
    version: int
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EdgeCreate(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=36)
    target_id: str = Field(..., min_length=1, max_length=36)
    edge_type: str = Field(..., min_length=1, max_length=50)
    channel_id: str = Field(..., min_length=1, max_length=32)
    tenant_id: str = Field(..., min_length=1, max_length=32)
    weight: float = Field(default=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeResponse(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    channel_id: str
    tenant_id: str
    weight: float
    metadata: dict[str, Any]
    created_at: datetime


class LineageCreate(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=36)
    record_type: str = Field(..., min_length=1, max_length=50)
    agent_id: str = Field(default="", max_length=255)
    action: str = Field(default="", max_length=255)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageResponse(BaseModel):
    record_id: str
    node_id: str
    record_type: str
    agent_id: str
    action: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime


class TraversalRequest(BaseModel):
    start_node_id: str
    direction: str = Field(default="out", pattern="^(out|in|both)$")
    max_depth: int = Field(default=10, ge=1, le=50)
    node_types: list[str] | None = None


class TraversalResponse(BaseModel):
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]
    path: list[str]
    depth: int


class LineagePathResponse(BaseModel):
    node_id: str
    lineage: list[NodeResponse]


class ProvenanceChainResponse(BaseModel):
    node_id: str
    records: list[LineageResponse]
