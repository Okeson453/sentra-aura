"""SentraAura shared security primitives.

Authentication, RBAC, audit logging, and prompt-injection defense.
"""
from sentinel_security.auth import authenticate_request, create_service_token
from sentinel_security.rbac import require_permission, require_role
from sentinel_security.audit import AuditLogBuilder
from sentinel_security.injection_defense import InjectionClassifier, sanitize_untrusted_input

__all__ = [
    "authenticate_request",
    "create_service_token",
    "require_permission",
    "require_role",
    "AuditLogBuilder",
    "InjectionClassifier",
    "sanitize_untrusted_input",
]
