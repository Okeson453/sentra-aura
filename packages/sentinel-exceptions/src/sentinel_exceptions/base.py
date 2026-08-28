"""SentraAura canonical exception base.

Every exception in the system carries a trace_id for distributed tracing
and an error_code for machine-readable classification.
"""
from __future__ import annotations

from typing import Any


class SentraAuraException(Exception):
    """Base exception for all SentraAura errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "UNKNOWN_ERROR",
        trace_id: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.trace_id = trace_id or ""
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "trace_id": self.trace_id,
            "details": self.details,
        }


class TransientError(SentraAuraException):
    """Errors that may resolve on retry."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="TRANSIENT_ERROR", status_code=503, **kwargs)


class PermanentError(SentraAuraException):
    """Errors that will not resolve on retry."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="PERMANENT_ERROR", status_code=400, **kwargs)
