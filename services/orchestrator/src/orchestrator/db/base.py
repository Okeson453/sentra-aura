"""SQLAlchemy declarative base for SentraAura services.

Provides the shared Base class, mixins for audit fields, soft-delete support,
and row-level security (RLS) tenant isolation.
Matches Backend Spec §4 and Security Targets §5.
"""
from __future__ import annotations

import contextvars
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, String, DateTime, Boolean, event, inspect, text
from sqlalchemy.orm import declarative_base, declared_attr, with_loader_criteria, Session
from sqlalchemy.dialects.postgresql import UUID as PGUUID

Base = declarative_base()

# ------------------------------------------------------------------
# Row-Level Security — tenant context
# ------------------------------------------------------------------

_current_tenant: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)


def set_tenant_context(tenant_id: str | None) -> contextvars.Token:
    """Set the current tenant context for RLS filtering.

    Returns a Token that can be used with reset_tenant_context() to restore
    the previous value. Use in a try/finally block.
    """
    return _current_tenant.set(tenant_id)


def get_tenant_context() -> str | None:
    """Return the current tenant_id from the active context, or None."""
    return _current_tenant.get()


def reset_tenant_context(token: contextvars.Token) -> None:
    """Reset the tenant context to the value captured by set_tenant_context()."""
    _current_tenant.reset(token)


def configure_tenant_for_connection(connection, tenant_id: str | None) -> None:
    """Set the PostgreSQL session variable used by RLS policies.

    This provides defense-in-depth: even raw SQL queries are filtered
    by the database-level RLS policy when this variable is set.
    """
    if tenant_id is not None:
        connection.execute(
            text("SELECT set_config('app.current_tenant', :tenant, false)"),
            {"tenant": tenant_id},
        )
    else:
        connection.execute(
            text("SELECT set_config('app.current_tenant', '', false)")
        )


def _has_tenant_id(mapper) -> bool:
    """Check whether the mapped class has a tenant_id column."""
    return hasattr(mapper.class_, "tenant_id")


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(orm_execute_state):
    """SQLAlchemy event hook: inject tenant_id filter into every SELECT.

    This enforces row-level security at the ORM query layer. When a tenant
    context is active, all SELECT queries against tables with a tenant_id
    column are automatically restricted to that tenant.
    """
    tenant_id = get_tenant_context()
    if tenant_id is None:
        return
    if not orm_execute_state.is_select:
        return
    mapper = orm_execute_state.bind_arguments.get("mapper")
    if mapper is None:
        return
    if _has_tenant_id(mapper):
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                mapper.class_,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True,
            )
        )


# ------------------------------------------------------------------
# Mixins
# ------------------------------------------------------------------

class AuditMixin:
    """Mixin adding created_at, updated_at, created_by, updated_by columns."""

    @declared_attr
    def created_at(cls) -> Column:
        return Column(DateTime, default=datetime.utcnow, nullable=False)

    @declared_attr
    def updated_at(cls) -> Column:
        return Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @declared_attr
    def created_by(cls) -> Column:
        return Column(String(255), nullable=True)

    @declared_attr
    def updated_by(cls) -> Column:
        return Column(String(255), nullable=True)


class SoftDeleteMixin:
    """Mixin adding soft-delete support."""

    @declared_attr
    def is_deleted(cls) -> Column:
        return Column(Boolean, default=False, nullable=False, index=True)

    @declared_attr
    def deleted_at(cls) -> Column:
        return Column(DateTime, nullable=True)

    @declared_attr
    def deleted_by(cls) -> Column:
        return Column(String(255), nullable=True)


class TenantMixin:
    """Mixin adding tenant_id and channel_id for multi-tenancy."""

    @declared_attr
    def tenant_id(cls) -> Column:
        return Column(String(32), nullable=False, index=True)

    @declared_attr
    def channel_id(cls) -> Column:
        return Column(String(32), nullable=False, index=True)


def generate_uuid() -> str:
    """Generate a short UUID string."""
    return str(uuid.uuid4())


def generate_short_id() -> str:
    """Generate a 22-character URL-safe UUID."""
    import base64
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")
