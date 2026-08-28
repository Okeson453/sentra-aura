"""Exception handling utilities for SentraAura services."""
from __future__ import annotations

from typing import Any

from sentinel_exceptions import SentraAuraException, get_error_response, get_status_code


def handle_exception(exc: Exception, trace_id: str = "") -> dict[str, Any]:
    """Convert any exception to a standardized error response."""
    if isinstance(exc, SentraAuraException):
        return get_error_response(exc)
    return {
        "error_code": "INTERNAL_ERROR",
        "message": str(exc),
        "trace_id": trace_id,
        "details": {},
    }


def get_http_status(exc: Exception) -> int:
    """Get HTTP status code for an exception."""
    if isinstance(exc, SentraAuraException):
        return get_status_code(exc)
    return 500
