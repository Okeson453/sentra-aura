"""Routes for the Content Asset Graph service."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from content_graph_service.models import get_engine, get_sessionmaker, Base
from content_graph_service.repositories import NodeRepository, EdgeRepository, LineageRepository
from content_graph_service.graph_queries import GraphTraversal
from content_graph_service.schemas import (
    NodeCreate, NodeUpdate, NodeResponse,
    EdgeCreate, EdgeResponse,
    LineageCreate, LineageResponse,
    TraversalRequest, TraversalResponse,
    ProvenanceChainResponse,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)

def get_db():
    db = _sessionmaker()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()


@router.post("/nodes", response_model=NodeResponse, status_code=201)
async def create_node(data: NodeCreate, db: Session = Depends(get_db)) -> NodeResponse:
    repo = NodeRepository(db)
    node = repo.create(data.model_dump())
    return NodeResponse(
        node_id=str(node.id),
        node_type=node.node_type,
        channel_id=node.channel_id,
        tenant_id=node.tenant_id,
        title=node.title or "",
        description=node.description,
        status=node.status,
        version=node.version,
        payload=node.payload or {},
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str, db: Session = Depends(get_db)) -> NodeResponse:
    repo = NodeRepository(db)
    node = repo.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return NodeResponse(
        node_id=str(node.id),
        node_type=node.node_type,
        channel_id=node.channel_id,
        tenant_id=node.tenant_id,
        title=node.title or "",
        description=node.description,
        status=node.status,
        version=node.version,
        payload=node.payload or {},
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.get("/nodes", response_model=list[NodeResponse])
async def list_nodes(
    node_types: list[str] | None = None,
    channel_id: str | None = None,
    tenant_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[NodeResponse]:
    repo = NodeRepository(db)
    items, _ = repo.list(node_types=node_types, channel_id=channel_id, tenant_id=tenant_id, status=status, limit=limit, offset=offset)
    return [
        NodeResponse(
            node_id=str(n.id),
            node_type=n.node_type,
            channel_id=n.channel_id,
            tenant_id=n.tenant_id,
            title=n.title or "",
            description=n.description,
            status=n.status,
            version=n.version,
            payload=n.payload or {},
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in items
    ]


@router.patch("/nodes/{node_id}", response_model=NodeResponse)
async def update_node(node_id: str, updates: NodeUpdate, db: Session = Depends(get_db)) -> NodeResponse:
    repo = NodeRepository(db)
    node = repo.update(node_id, updates.model_dump(exclude_unset=True))
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return NodeResponse(
        node_id=str(node.id),
        node_type=node.node_type,
        channel_id=node.channel_id,
        tenant_id=node.tenant_id,
        title=node.title or "",
        description=node.description,
        status=node.status,
        version=node.version,
        payload=node.payload or {},
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.delete("/nodes/{node_id}", status_code=200)
async def delete_node(node_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    repo = NodeRepository(db)
    ok = repo.delete(node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"deleted": True}


@router.post("/edges", response_model=EdgeResponse, status_code=201)
async def create_edge(data: EdgeCreate, db: Session = Depends(get_db)) -> EdgeResponse:
    repo = EdgeRepository(db)
    edge = repo.create(data.model_dump())
    return EdgeResponse(
        edge_id=str(edge.id),
        source_id=str(edge.source_id),
        target_id=str(edge.target_id),
        edge_type=edge.edge_type,
        channel_id=edge.channel_id,
        tenant_id=edge.tenant_id,
        weight=edge.weight,
        metadata=edge.metadata_json or {},
        created_at=edge.created_at,
    )


@router.get("/nodes/{node_id}/edges", response_model=list[EdgeResponse])
async def get_edges(node_id: str, direction: str = "both", db: Session = Depends(get_db)) -> list[EdgeResponse]:
    repo = EdgeRepository(db)
    edges = repo.list_by_node(node_id, direction)
    return [
        EdgeResponse(
            edge_id=str(e.id),
            source_id=str(e.source_id),
            target_id=str(e.target_id),
            edge_type=e.edge_type,
            channel_id=e.channel_id,
            tenant_id=e.tenant_id,
            weight=e.weight,
            metadata=e.metadata_json or {},
            created_at=e.created_at,
        )
        for e in edges
    ]


@router.delete("/edges/{edge_id}", status_code=200)
async def delete_edge(edge_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    repo = EdgeRepository(db)
    ok = repo.delete(edge_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Edge not found")
    return {"deleted": True}


@router.post("/lineage", response_model=LineageResponse, status_code=201)
async def create_lineage(data: LineageCreate, db: Session = Depends(get_db)) -> LineageResponse:
    repo = LineageRepository(db)
    rec = repo.create(data.model_dump())
    return LineageResponse(
        record_id=str(rec.id),
        node_id=str(rec.node_id),
        record_type=rec.record_type,
        agent_id=rec.agent_id or "",
        action=rec.action or "",
        inputs=rec.inputs or {},
        outputs=rec.outputs or {},
        metadata=rec.metadata_json or {},
        created_at=rec.created_at,
    )


@router.get("/nodes/{node_id}/lineage", response_model=list[LineageResponse])
async def get_lineage(node_id: str, db: Session = Depends(get_db)) -> list[LineageResponse]:
    repo = LineageRepository(db)
    records = repo.list_by_node(node_id)
    return [
        LineageResponse(
            record_id=str(r.id),
            node_id=str(r.node_id),
            record_type=r.record_type,
            agent_id=r.agent_id or "",
            action=r.action or "",
            inputs=r.inputs or {},
            outputs=r.outputs or {},
            metadata=r.metadata_json or {},
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/lineage/{record_id}", response_model=LineageResponse)
async def get_lineage_record(record_id: str, db: Session = Depends(get_db)) -> LineageResponse:
    repo = LineageRepository(db)
    rec = repo.get(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Lineage record not found")
    return LineageResponse(
        record_id=str(rec.id),
        node_id=str(rec.node_id),
        record_type=rec.record_type,
        agent_id=rec.agent_id or "",
        action=rec.action or "",
        inputs=rec.inputs or {},
        outputs=rec.outputs or {},
        metadata=rec.metadata_json or {},
        created_at=rec.created_at,
    )


@router.post("/traverse", response_model=TraversalResponse)
async def traverse(req: TraversalRequest, db: Session = Depends(get_db)) -> TraversalResponse:
    gt = GraphTraversal(db)
    result = gt.bfs(
        start_node_id=req.start_node_id,
        direction=req.direction,
        max_depth=req.max_depth,
        node_types=req.node_types,
    )
    return TraversalResponse(
        nodes=[NodeResponse(**n) for n in result.nodes],
        edges=[EdgeResponse(**e) for e in result.edges],
        path=result.path,
        depth=result.depth,
    )


@router.get("/nodes/{node_id}/ancestors", response_model=TraversalResponse)
async def get_ancestors(node_id: str, max_depth: int = 10, db: Session = Depends(get_db)) -> TraversalResponse:
    gt = GraphTraversal(db)
    result = gt.get_ancestors(node_id, max_depth=max_depth)
    return TraversalResponse(
        nodes=[NodeResponse(**n) for n in result.nodes],
        edges=[EdgeResponse(**e) for e in result.edges],
        path=result.path,
        depth=result.depth,
    )


@router.get("/nodes/{node_id}/descendants", response_model=TraversalResponse)
async def get_descendants(node_id: str, max_depth: int = 10, db: Session = Depends(get_db)) -> TraversalResponse:
    gt = GraphTraversal(db)
    result = gt.get_descendants(node_id, max_depth=max_depth)
    return TraversalResponse(
        nodes=[NodeResponse(**n) for n in result.nodes],
        edges=[EdgeResponse(**e) for e in result.edges],
        path=result.path,
        depth=result.depth,
    )


@router.get("/nodes/{node_id}/lineage-path", response_model=list[NodeResponse])
async def get_lineage_path(node_id: str, max_depth: int = 20, db: Session = Depends(get_db)) -> list[NodeResponse]:
    gt = GraphTraversal(db)
    lineage = gt.get_lineage_path(node_id, max_depth=max_depth)
    return [NodeResponse(**n) for n in lineage]


@router.get("/nodes/{node_id}/provenance", response_model=ProvenanceChainResponse)
async def get_provenance(node_id: str, db: Session = Depends(get_db)) -> ProvenanceChainResponse:
    gt = GraphTraversal(db)
    records = gt.get_provenance_chain(node_id)
    return ProvenanceChainResponse(
        node_id=node_id,
        records=[LineageResponse(**r) for r in records],
    )
