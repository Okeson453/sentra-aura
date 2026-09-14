"""Durable agent checkpoint store (Architecture §10).

``DurableAgentState`` (durable_state.py) carries the checkpoint/cost/error fields
for fault-tolerant automation, and migrations/versions/001_baseline.py owns the
``agent_checkpoints`` table - but nothing was writing to it. Invocations were
therefore unrecoverable: a process restart lost in-flight work with no record.

This store persists a checkpoint after every invocation (success or failure), so
work is recoverable and cost is auditable. It defaults to the same database URL
the migration targets and is explicitly disabled only when no DSN is configured.

Schema note: the table is created by Alembic. The store does not create tables;
``ensure_ready()`` verifies reachability so ``/ready`` can report honestly.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    func,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

metadata = MetaData()

# Mirrors migrations/versions/001_baseline.py exactly.
agent_checkpoints = Table(
    "agent_checkpoints",
    metadata,
    Column("id", Integer(), primary_key=True, autoincrement=True),
    Column("agent_id", String(128), nullable=False, index=True),
    Column("checkpoint_id", String(64), nullable=False, unique=True),
    Column("phase", String(64), nullable=False, server_default="idle"),
    Column("cost_accrued_usd", Float(), nullable=False, server_default="0"),
    Column("tokens_consumed", Integer(), nullable=False, server_default="0"),
    Column("payload", JSON(), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)


def _normalise_dsn(dsn: str) -> str:
    """Return an async-driver DSN for SQLAlchemy.

    ``postgresql://...`` must become ``postgresql+asyncpg://...`` for the async
    engine; sqlite DSNs are passed through unchanged.
    """
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    if dsn.startswith("postgres://"):
        return dsn.replace("postgres://", "postgresql+asyncpg://", 1)
    return dsn


class CheckpointStore:
    """Durable store for agent execution checkpoints."""

    def __init__(self, database_url: str | None) -> None:
        self.database_url = database_url
        self._engine: AsyncEngine | None = None

    @property
    def enabled(self) -> bool:
        """Whether a durable backing store is configured."""
        return bool(self.database_url)

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            if not self.database_url:
                raise RuntimeError(
                    "CheckpointStore has no database_url configured; durable state "
                    "is required in production (AGENT_RUNTIME_DATABASE_URL)"
                )
            self._engine = create_async_engine(
                _normalise_dsn(self.database_url),
                pool_pre_ping=True,
                future=True,
            )
        return self._engine

    async def ensure_ready(self) -> None:
        """Verify the backing store is reachable and the table exists."""
        if not self.enabled:
            raise RuntimeError("checkpoint store disabled: no database_url configured")
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM agent_checkpoints LIMIT 1"))

    async def save(
        self,
        *,
        agent_id: str,
        phase: str,
        checkpoint_id: str | None = None,
        cost_accrued_usd: float = 0.0,
        tokens_consumed: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Persist a checkpoint and return its id.

        The write is idempotent per ``checkpoint_id``: replaying the same
        checkpoint upserts rather than duplicating history, which keeps workflow
        replay safe.
        """
        checkpoint_id = checkpoint_id or f"ckpt-{uuid.uuid4().hex[:16]}"
        values = {
            "agent_id": agent_id,
            "checkpoint_id": checkpoint_id,
            "phase": phase,
            "cost_accrued_usd": float(cost_accrued_usd or 0.0),
            "tokens_consumed": int(tokens_consumed or 0),
            "payload": payload or {},
        }
        async with self.engine.begin() as conn:
            existing = await conn.execute(
                select(agent_checkpoints.c.id).where(
                    agent_checkpoints.c.checkpoint_id == checkpoint_id
                )
            )
            row = existing.first()
            if row is None:
                await conn.execute(agent_checkpoints.insert().values(**values))
            else:
                await conn.execute(
                    agent_checkpoints.update()
                    .where(agent_checkpoints.c.checkpoint_id == checkpoint_id)
                    .values(**values, updated_at=datetime.now(timezone.utc))
                )
        return checkpoint_id

    async def latest(self, agent_id: str) -> dict[str, Any] | None:
        """Return the most recent checkpoint for an agent, or ``None``."""
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(agent_checkpoints)
                .where(agent_checkpoints.c.agent_id == agent_id)
                .order_by(agent_checkpoints.c.id.desc())
                .limit(1)
            )
            row = result.mappings().first()
        if row is None:
            return None
        record = dict(row)
        payload = record.get("payload")
        if isinstance(payload, str):  # sqlite/JSON backends may hand back text
            try:
                record["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                record["payload"] = {}
        for key in ("created_at", "updated_at"):
            value = record.get(key)
            if isinstance(value, datetime):
                record[key] = value.isoformat()
        return record

    async def close(self) -> None:
        """Dispose the connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
