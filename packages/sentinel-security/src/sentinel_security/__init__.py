"""SentraAura shared security primitives.

Authentication, RBAC, audit logging, and prompt-injection defense.
"""
from sentinel_security.auth import AuthContext, authenticate_request, create_service_token
from sentinel_security.rbac import require_permission, require_role
from sentinel_security.audit import AuditLogBuilder
from sentinel_security.injection_defense import InjectionClassifier, sanitize_untrusted_input
from sentinel_security.tenant import (
    TENANT_ID_MAX_LENGTH,
    auth_error_to_http_status,
    resolve_tenant_id,
    validate_tenant_id,
)
from sentinel_security.timeutil import utc_now, utc_now_iso

__all__ = [
    "AuthContext",
    "authenticate_request",
    "create_service_token",
    "require_permission",
    "require_role",
    "AuditLogBuilder",
    "InjectionClassifier",
    "sanitize_untrusted_input",
    "TENANT_ID_MAX_LENGTH",
    "auth_error_to_http_status",
    "resolve_tenant_id",
    "validate_tenant_id",
    "utc_now",
    "utc_now_iso",
]
