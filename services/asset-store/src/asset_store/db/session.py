"""Database session management for SentraAura services.

Provides engine creation, session factory, dependency injection, and transaction helpers.
Matches Backend Spec §4.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from functools import lru_cache
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from asset_store.config import get_settings
from asset_store.db.base import Base


def _async_database_url(database_url: str) -> str:
    """Return an async-driver URL for each supported synchronous URL form."""
    url = make_url(database_url)
    if url.drivername in {"postgresql", "postgresql+psycopg2"}:
        return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    if url.drivername == "sqlite":
        return url.set(drivername="sqlite+aiosqlite").render_as_string(hide_password=False)
    return database_url


def _set_sqlite_pragma(dbapi_conn, connection_record) -> None:
    """Enable SQLite foreign-key enforcement for every new connection."""
    del connection_record
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide synchronous SQLAlchemy engine, creating it lazily."""
    settings = get_settings()
    kwargs = {"echo": settings.database_echo}
    if settings.environment == "test":
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            poolclass=QueuePool,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_pre_ping=True,
        )

    engine = create_engine(settings.database_url, **kwargs)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragma)
    return engine


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return the process-wide async SQLAlchemy engine, creating it lazily."""
    settings = get_settings()
    async_url = _async_database_url(settings.database_url)
    kwargs = {"echo": settings.database_echo}
    if settings.environment == "test":
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_pre_ping=True,
        )
    engine = create_async_engine(async_url, **kwargs)
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)
    return engine


class _LazySessionMaker(sessionmaker):
    """A sessionmaker that binds to the memoized engine on first use."""

    def __call__(self, **local_kw):
        if self.kw.get("bind") is None:
            self.configure(bind=get_engine())
        return super().__call__(**local_kw)


class _LazyAsyncSessionMaker(async_sessionmaker):
    """An async_sessionmaker that binds to the memoized engine on first use."""

    def __call__(self, **local_kw):
        if self.kw.get("bind") is None:
            self.configure(bind=get_async_engine())
        return super().__call__(**local_kw)


# Public factories remain import-safe and callable without creating engines.
SessionLocal = _LazySessionMaker(autocommit=False, autoflush=False)
AsyncSessionLocal = _LazyAsyncSessionMaker(
    autocommit=False,
    autoflush=False,
    class_=AsyncSession,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for synchronous DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async DB sessions."""
    async with AsyncSessionLocal() as session:
        yield session


@contextmanager
def db_transaction() -> Generator[Session, None, None]:
    """Context manager for synchronous transactions with automatic rollback on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def async_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for transactions with automatic rollback on error."""
    async with AsyncSessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


def init_db() -> None:
    """Create all tables (development/testing only)."""
    Base.metadata.create_all(bind=get_engine())


async def init_db_async() -> None:
    """Async create all tables (development/testing only)."""
    async with get_async_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
