"""Map SentraAura exceptions to HTTP status codes."""
from __future__ import annotations

from sentinel_exceptions.base import SentraAuraException
from sentinel_exceptions import domain

_HTTP_MAP: dict[str, int] = {
    "UNKNOWN_ERROR": 500,
    "TRANSIENT_ERROR": 503,
    "PERMANENT_ERROR": 400,
    "TOPIC_REJECTED": 400,
    "BUDGET_EXCEEDED": 402,
    "WORKFLOW_STUCK": 500,
    "WORKFLOW_NOT_FOUND": 404,
    "AGENT_INVOCATION_ERROR": 503,
    "AGENT_OUTPUT_INVALID": 422,
    "TOOL_PERMISSION_DENIED": 403,
    "PUBLISH_REJECTED": 400,
    "COPYRIGHT_CLAIM": 403,
    "PROVIDER_UNAVAILABLE": 503,
    "PROVIDER_RATE_LIMIT": 429,
    "ALL_PROVIDERS_FAILED": 503,
    "AUTHENTICATION_ERROR": 401,
    "AUTHORIZATION_ERROR": 403,
    "PROMPT_INJECTION": 400,
    "NODE_NOT_FOUND": 404,
    "SCHEMA_VALIDATION_ERROR": 422,
}


def get_status_code(exc: SentraAuraException) -> int:
    """Return the HTTP status code for a given exception."""
    return _HTTP_MAP.get(exc.error_code, exc.status_code)


def get_error_response(exc: SentraAuraException) -> dict:
    """Return a standardized error response dict."""
    return {
        "error_code": exc.error_code,
        "message": exc.message,
        "trace_id": exc.trace_id,
        "details": exc.details,
    }
