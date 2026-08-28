"""Role-Based Access Control for SentraAura.

Permission model from Architecture §16.2:
  SystemAdmin, ChannelOwner, ContentEditor, ContentViewer,
  Scheduler, BudgetManager, Operator, Agent (service account)
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request

from sentinel_exceptions import AuthorizationError
from sentinel_security.auth import AuthContext, authenticate_request


# Permission matrix: role -> set of permissions
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "SystemAdmin": set(),  # All permissions (checked specially)
    "ChannelOwner": {
        "content:read", "content:write", "content:approve",
        "channel:manage", "budget:read", "budget:write",
        "agent:manage", "analytics:read", "experiment:run",
        "publishing:approve", "publishing:schedule", "override:apply",
    },
    "ContentEditor": {
        "content:read", "content:write", "content:approve",
        "analytics:read", "experiment:run", "publishing:approve",
    },
    "ContentViewer": {"content:read", "analytics:read"},
    "Scheduler": {"publishing:schedule", "content:read"},
    "BudgetManager": {"budget:read", "budget:write", "analytics:read"},
    "Operator": {"system:health", "system:restart", "logs:read"},
    "Agent": set(),  # Least-privilege; permissions from tool manifest
}


def _has_permission(auth: AuthContext, permission: str) -> bool:
    if "SystemAdmin" in auth.roles:
        return True
    for role in auth.roles:
        perms = _ROLE_PERMISSIONS.get(role, set())
        if permission in perms:
            return True
    return False


def require_role(*roles: str) -> Callable:
    """FastAPI dependency factory: require one of the given roles."""
    def checker(auth: AuthContext = Depends(_get_auth_context)) -> AuthContext:
        if not any(r in auth.roles for r in roles) and "SystemAdmin" not in auth.roles:
            raise AuthorizationError(
                f"Required one of roles: {roles}, got: {auth.roles}"
            )
        return auth
    return checker


def require_permission(permission: str) -> Callable:
    """FastAPI dependency factory: require a specific permission."""
    def checker(auth: AuthContext = Depends(_get_auth_context)) -> AuthContext:
        if not _has_permission(auth, permission):
            raise AuthorizationError(
                f"Permission '{permission}' denied for roles: {auth.roles}"
            )
        return auth
    return checker


def _get_auth_context(request: Request) -> AuthContext:
    """Extract AuthContext from request state (set by middleware)."""
    auth: AuthContext | None = getattr(request.state, "auth_context", None)
    if auth is None:
        raise AuthorizationError("No authentication context found")
    return auth
