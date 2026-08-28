"""Database session management for SentraAura services.

Provides engine creation, session factory, dependency injection, and transaction helpers.
Matches Backend Spec §4.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool

from control_plane_api.config import get_settings
from control_plane_api.db.base import Base


_settings = get_settings()


def get_engine():
    """Create and return a SQLAlchemy engine with connection pooling."""
    if _settings.environment == "test":
        return create_engine(
            _settings.database_url,
            poolclass=NullPool,
            echo=_settings.database_echo,
        )
    return create_engine(
        _settings.database_url,
        poolclass=QueuePool,
        pool_size=_settings.database_pool_size,
        max_overflow=_settings.database_max_overflow,
        pool_timeout=_settings.database_pool_timeout,
        pool_pre_ping=True,
        echo=_settings.database_echo,
    )


def get_async_engine():
    """Create and return an async SQLAlchemy engine."""
    async_url = _settings.database_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    if _settings.environment == "test":
        return create_async_engine(async_url, poolclass=NullPool, echo=_settings.database_echo)
    return create_async_engine(
        async_url,
        pool_size=_settings.database_pool_size,
        max_overflow=_settings.database_max_overflow,
        pool_timeout=_settings.database_pool_timeout,
        pool_pre_ping=True,
        echo=_settings.database_echo,
    )


# Synchronous session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

# Async session factory
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=get_async_engine(), class_=AsyncSession)


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
        try:
            yield session
        finally:
            await session.close()


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


@event.listens_for(get_engine(), "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key support for SQLite connections."""
    if "sqlite" in _settings.database_url:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
