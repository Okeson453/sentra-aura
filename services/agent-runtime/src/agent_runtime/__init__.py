"""SentraAura Agent Runtime.

The agent-runtime is a single deployable that hosts all 30 specialized agents.
Agents are selected at invocation time by the Orchestrator, differing only in
their registry entry (model, prompt version, budget, tool manifest).

Matches Architecture §1.1, §1.3, §4.1, §4.2.
"""
from agent_runtime.envelope import AgentMessageEnvelope, AgentMessagePriority
from agent_runtime.execution_policy import ExecutionPolicy
from agent_runtime.registry_client import RegistryClient as AgentRegistryClient
from agent_runtime.tool_permissions import ToolPermissionEnforcer as ToolPermissionChecker

__all__ = [
    "AgentMessageEnvelope",
    "AgentMessagePriority",
    "ExecutionPolicy",
    "AgentRegistryClient",
    "ToolPermissionChecker",
]
