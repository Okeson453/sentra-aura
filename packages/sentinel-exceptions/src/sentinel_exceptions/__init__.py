"""SentraAura canonical exceptions.

Re-exports all exception types for convenience.
"""
from sentinel_exceptions.base import (
    PermanentError,
    SentraAuraException,
    TransientError,
)
from sentinel_exceptions.domain import (
    AgentInvocationError,
    AgentOutputValidationError,
    AllProvidersFailed,
    AuthenticationError,
    AuthorizationError,
    BudgetExceeded,
    CopyrightClaim,
    NodeNotFound,
    PromptInjectionDetected,
    ProviderRateLimit,
    ProviderUnavailable,
    PublishRejected,
    SchemaValidationError,
    ToolPermissionDenied,
    TopicRejected,
    WorkflowNotFound,
    WorkflowStuck,
)
from sentinel_exceptions.http_map import get_error_response, get_status_code

__all__ = [
    "SentraAuraException",
    "TransientError",
    "PermanentError",
    "TopicRejected",
    "BudgetExceeded",
    "WorkflowStuck",
    "WorkflowNotFound",
    "AgentInvocationError",
    "AgentOutputValidationError",
    "ToolPermissionDenied",
    "PublishRejected",
    "CopyrightClaim",
    "ProviderUnavailable",
    "ProviderRateLimit",
    "AllProvidersFailed",
    "AuthenticationError",
    "AuthorizationError",
    "PromptInjectionDetected",
    "NodeNotFound",
    "SchemaValidationError",
    "get_status_code",
    "get_error_response",
]
