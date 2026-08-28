"""Database manager for SentraAura.

Async SQLAlchemy with connection pooling and health checks.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


class DatabaseManager:
    """Manages async database connections."""

    def __init__(self, database_url: str, *, pool_size: int = 10) -> None:
        self.database_url = database_url
        self.pool_size = pool_size
        self.engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def connect(self) -> None:
        """Test the database connection."""
        async with self.engine.begin() as conn:
            await conn.execute("SELECT 1")

    async def close(self) -> None:
        """Close all database connections."""
        await self.engine.dispose()

    async def get_session(self) -> AsyncSession:
        """Get a new database session."""
        return self.session_factory()

    async def health_check(self) -> tuple[Any, float]:
        """Return health status and latency."""
        import time
        start = time.perf_counter()
        try:
            async with self.engine.begin() as conn:
                await conn.execute("SELECT 1")
            latency = (time.perf_counter() - start) * 1000
            from service_kit.health import HealthStatus
            return HealthStatus.HEALTHY, latency
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            from service_kit.health import HealthStatus
            return HealthStatus.UNHEALTHY, latency
