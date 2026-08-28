"""Domain-specific exceptions used across SentraAura services."""
from __future__ import annotations

from typing import Any

from sentinel_exceptions.base import SentraAuraException, TransientError


# --- Content / Workflow ---
class TopicRejected(SentraAuraException):
    def __init__(self, message: str = "Topic rejected", **kwargs: Any) -> None:
        super().__init__(message, error_code="TOPIC_REJECTED", status_code=400, **kwargs)


class BudgetExceeded(SentraAuraException):
    def __init__(self, message: str = "Budget exceeded", **kwargs: Any) -> None:
        super().__init__(message, error_code="BUDGET_EXCEEDED", status_code=402, **kwargs)


class WorkflowStuck(SentraAuraException):
    def __init__(self, message: str = "Workflow stuck", **kwargs: Any) -> None:
        super().__init__(message, error_code="WORKFLOW_STUCK", status_code=500, **kwargs)


class WorkflowNotFound(SentraAuraException):
    def __init__(self, message: str = "Workflow not found", **kwargs: Any) -> None:
        super().__init__(message, error_code="WORKFLOW_NOT_FOUND", status_code=404, **kwargs)


# --- Agent ---
class AgentInvocationError(TransientError):
    def __init__(self, message: str = "Agent invocation failed", **kwargs: Any) -> None:
        super().__init__(message, error_code="AGENT_INVOCATION_ERROR", **kwargs)


class AgentOutputValidationError(SentraAuraException):
    def __init__(self, message: str = "Agent output validation failed", **kwargs: Any) -> None:
        super().__init__(message, error_code="AGENT_OUTPUT_INVALID", status_code=422, **kwargs)


class ToolPermissionDenied(SentraAuraException):
    def __init__(self, message: str = "Tool permission denied", **kwargs: Any) -> None:
        super().__init__(message, error_code="TOOL_PERMISSION_DENIED", status_code=403, **kwargs)


# --- Publishing ---
class PublishRejected(SentraAuraException):
    def __init__(self, message: str = "Publish rejected by platform", **kwargs: Any) -> None:
        super().__init__(message, error_code="PUBLISH_REJECTED", status_code=400, **kwargs)


class CopyrightClaim(SentraAuraException):
    def __init__(self, message: str = "Copyright claim detected", **kwargs: Any) -> None:
        super().__init__(message, error_code="COPYRIGHT_CLAIM", status_code=403, **kwargs)


# --- Provider ---
class ProviderUnavailable(TransientError):
    def __init__(self, message: str = "Provider unavailable", **kwargs: Any) -> None:
        super().__init__(message, error_code="PROVIDER_UNAVAILABLE", **kwargs)


class ProviderRateLimit(TransientError):
    def __init__(self, message: str = "Provider rate limit hit", **kwargs: Any) -> None:
        super().__init__(message, error_code="PROVIDER_RATE_LIMIT", status_code=429, **kwargs)


class AllProvidersFailed(SentraAuraException):
    def __init__(self, message: str = "All providers failed", **kwargs: Any) -> None:
        super().__init__(message, error_code="ALL_PROVIDERS_FAILED", status_code=503, **kwargs)


# --- Security ---
class AuthenticationError(SentraAuraException):
    def __init__(self, message: str = "Authentication failed", **kwargs: Any) -> None:
        super().__init__(message, error_code="AUTHENTICATION_ERROR", status_code=401, **kwargs)


class AuthorizationError(SentraAuraException):
    def __init__(self, message: str = "Authorization failed", **kwargs: Any) -> None:
        super().__init__(message, error_code="AUTHORIZATION_ERROR", status_code=403, **kwargs)


class PromptInjectionDetected(SentraAuraException):
    def __init__(self, message: str = "Prompt injection detected", **kwargs: Any) -> None:
        super().__init__(message, error_code="PROMPT_INJECTION", status_code=400, **kwargs)


# --- Data / Graph ---
class NodeNotFound(SentraAuraException):
    def __init__(self, message: str = "Graph node not found", **kwargs: Any) -> None:
        super().__init__(message, error_code="NODE_NOT_FOUND", status_code=404, **kwargs)


class SchemaValidationError(SentraAuraException):
    def __init__(self, message: str = "Schema validation failed", **kwargs: Any) -> None:
        super().__init__(message, error_code="SCHEMA_VALIDATION_ERROR", status_code=422, **kwargs)
