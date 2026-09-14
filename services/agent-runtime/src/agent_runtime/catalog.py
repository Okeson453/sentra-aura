"""Canonical agent catalog - resolves an ``agent_type`` to its implementation.

The agent-runtime is a single deployable that hosts all 30 specialized agents
(Architecture §1.1, §1.3, §4.1, §4.2). Agents are selected at
invocation time by the Orchestrator and differ only in their registry entry
(model, prompt version, budget, tool manifest).

Agents are imported lazily so that API startup and ``/health`` never depend on
any single agent module. Agent modules execute arbitrary work at import time
(provider clients, prompt registries), so they are treated as third-party code:
an agent whose module fails to import is reported through ``catalog_errors()``
and excluded from dispatch, rather than taking down the whole runtime.

This module is the single source of truth for "which agent types exist".
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentEntry:
    """Static description of one agent shipped by the runtime."""

    agent_type: str
    domain: str
    agent_class: str
    config_class: str

    @property
    def module_root(self) -> str:
        """Importable package for this agent."""
        return f"agent_runtime.agents.{self.domain}.{self.agent_type}"


#: Every agent the runtime is contracted to host. Keep in lockstep with
#: ``contracts/openapi/agent-runtime.yaml`` and the agent structural gate in CI
#: (Stage 1), which requires agent.py/schemas.py/config.py/state.py/tools.py/README.md.
AGENT_ENTRIES: tuple[AgentEntry, ...] = (
    # --- clipping ---
    AgentEntry("ai_clipping_agent", "clipping", "AIClippingAgent", "AgentConfig"),
    AgentEntry("captioning_agent", "clipping", "CaptioningAgent", "AgentConfig"),
    AgentEntry("reframing_agent", "clipping", "ReframingAgent", "AgentConfig"),
    AgentEntry("repurposing_agent", "clipping", "RepurposingAgent", "AgentConfig"),
    # --- creative ---
    AgentEntry("content_strategist_ideation_agent", "creative", "ContentStrategistIdeationAgent", "ContentStrategistConfig"),
    AgentEntry("fact_verification_agent", "creative", "FactVerificationAgent", "FactVerificationConfig"),
    AgentEntry("scripting_agent", "creative", "ScriptingAgent", "ScriptingAgentConfig"),
    AgentEntry("visual_asset_agent", "creative", "VisualAssetAgent", "VisualAssetConfig"),
    AgentEntry("voice_agent", "creative", "VoiceAgent", "VoiceAgentConfig"),
    # --- distribution ---
    AgentEntry("community_engagement_agent", "distribution", "CommunityEngagementAgent", "AgentConfig"),
    AgentEntry("publishing_agent", "distribution", "PublishingAgent", "AgentConfig"),
    AgentEntry("scheduling_agent", "distribution", "SchedulingAgent", "AgentConfig"),
    AgentEntry("seo_packaging_agent", "distribution", "SEOPackagingAgent", "AgentConfig"),
    AgentEntry("thumbnail_agent", "distribution", "ThumbnailAgent", "AgentConfig"),
    # --- intelligence ---
    AgentEntry("executive_orchestrator_agent", "intelligence", "ExecutiveOrchestratorAgent", "ExecutiveOrchestratorConfig"),
    AgentEntry("market_audience_intelligence_agent", "intelligence", "MarketAudienceIntelligenceAgent", "MarketAudienceConfig"),
    AgentEntry("portfolio_strategy_agent", "intelligence", "PortfolioStrategyAgent", "PortfolioStrategyConfig"),
    AgentEntry("research_agent", "intelligence", "ResearchAgent", "ResearchAgentConfig"),
    # --- operations ---
    AgentEntry("analytics_agent", "operations", "AnalyticsAgent", "AgentConfig"),
    AgentEntry("compliance_agent", "operations", "ComplianceAgent", "AgentConfig"),
    AgentEntry("cost_control_agent", "operations", "CostControlAgent", "AgentConfig"),
    AgentEntry("crisis_sentiment_anomaly_agent", "operations", "CrisisSentimentAnomalyAgent", "AgentConfig"),
    AgentEntry("experimentation_agent", "operations", "ExperimentationAgent", "AgentConfig"),
    AgentEntry("memory_agent", "operations", "MemoryAgent", "AgentConfig"),
    AgentEntry("optimization_agent", "operations", "OptimizationAgent", "AgentConfig"),
    AgentEntry("quality_control_agent", "operations", "QualityControlAgent", "AgentConfig"),
    AgentEntry("rights_remediation_agent", "operations", "RightsRemediationAgent", "AgentConfig"),
    # --- production ---
    AgentEntry("localization_agent", "production", "LocalizationAgent", "AgentConfig"),
    AgentEntry("scene_shot_agent", "production", "SceneShotAgent", "AgentConfig"),
    AgentEntry("video_production_agent", "production", "VideoProductionAgent", "AgentConfig"),
)

_BY_TYPE: dict[str, AgentEntry] = {entry.agent_type: entry for entry in AGENT_ENTRIES}

#: Agents whose primary effect is externally visible. Publishing and community
#: engagement must pass the documented human approval gate (Architecture §11, §19);
#: the runtime enforces it rather than relying on the caller to remember.
PUBLISH_APPROVAL_AGENTS: frozenset[str] = frozenset(
    {"publishing_agent", "community_engagement_agent"}
)

_import_errors: dict[str, str] = {}


def catalog_errors() -> dict[str, str]:
    """Return ``{agent_type: error}`` for agents whose module failed to import."""
    return dict(_import_errors)


def agent_types() -> list[str]:
    """Return every supported agent type, sorted."""
    return sorted(_BY_TYPE)


def entry_for(agent_type: str) -> AgentEntry:
    """Return the catalog entry for ``agent_type``.

    Raises ``KeyError`` (listing every supported type) for an unknown agent.
    """
    entry = _BY_TYPE.get(agent_type)
    if entry is None:
        raise KeyError(
            f"unknown agent_type {agent_type!r}; supported: {', '.join(sorted(_BY_TYPE))}"
        )
    return entry


def _load_config(config_class: str, module_root: str) -> Any | None:
    """Instantiate an agent's config class, tolerating a module without one.

    Agent configs are ``pydantic_settings.BaseSettings`` subclasses carrying
    defaults, so ``ConfigClass()`` yields a usable configuration and any
    environment override still applies.
    """
    try:
        module = importlib.import_module(f"{module_root}.config")
    except ImportError:
        logger.warning("agent config module missing for %s", module_root)
        return None
    cls = getattr(module, config_class, None)
    if cls is None:
        logger.warning("agent config class %s missing in %s.config", config_class, module_root)
        return None
    return cls()


def build_agent(
    agent_type: str,
    *,
    provider_gateway_url: str | None = None,
    timeout_seconds: float | None = None,
    approval_gate: Any | None = None,
) -> Any:
    """Import and construct one agent, bound to the provider gateway.

    Raises ``KeyError`` for an unknown agent type and ``ImportError`` when the
    agent's module cannot be imported.
    """
    entry = entry_for(agent_type)
    try:
        module = importlib.import_module(f"{entry.module_root}.agent")
    except ImportError as exc:
        _import_errors[agent_type] = str(exc)
        raise
    agent_cls = getattr(module, entry.agent_class, None)
    if agent_cls is None:
        msg = f"{entry.agent_class} not found in {entry.module_root}.agent"
        _import_errors[agent_type] = msg
        raise ImportError(msg)

    config = _load_config(entry.config_class, entry.module_root)
    if config is not None:
        # Every agent config carries these two fields; bind them to the runtime.
        if provider_gateway_url is not None and hasattr(config, "provider_gateway_url"):
            config.provider_gateway_url = provider_gateway_url
        if timeout_seconds is not None and hasattr(config, "timeout_seconds"):
            config.timeout_seconds = timeout_seconds

    kwargs: dict[str, Any] = {}
    if config is not None:
        kwargs["config"] = config
    if approval_gate is not None:
        kwargs["approval_gate"] = approval_gate
    return agent_cls(**kwargs)


def instantiate_all(
    *,
    provider_gateway_url: str | None = None,
    timeout_seconds: float | None = None,
    approval_gate: Any | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Construct every catalogued agent once, at startup.

    Returns ``(instances, errors)``. Agent construction happens eagerly so a
    broken agent is caught at boot (and surfaced through ``/health``) instead of
    at first invocation; failures never abort startup of the other agents.
    """
    instances: dict[str, Any] = {}
    errors: dict[str, str] = {}
    _import_errors.clear()

    for entry in AGENT_ENTRIES:
        try:
            instances[entry.agent_type] = build_agent(
                entry.agent_type,
                provider_gateway_url=provider_gateway_url,
                timeout_seconds=timeout_seconds,
                approval_gate=approval_gate,
            )
        except Exception as exc:  # noqa: BLE001 - one bad agent must not sink the runtime
            errors[entry.agent_type] = f"{type(exc).__name__}: {exc}"
            logger.warning("agent %s failed to initialise: %s", entry.agent_type, exc)

    if errors:
        logger.error("%d/%d agents failed to initialise", len(errors), len(AGENT_ENTRIES))
    else:
        logger.info("all %d agents initialised", len(instances))
    return instances, errors
