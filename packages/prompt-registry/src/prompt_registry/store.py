"""Prompt store with CRUD, versioning, and agent-scoped retrieval.

The store is the canonical interface for the control plane and agents
to fetch, register, and evolve prompts over time.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prompt_registry.loader import PromptLoader, TemplateNotFoundError
from prompt_registry.validator import PromptValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class PromptRecord:
    """A canonical prompt record in the store."""

    agent_id: str
    prompt_type: str
    version: str
    template: str
    template_hash: str
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deprecated: bool = False
    deprecated_reason: str | None = None


class PromptStore:
    """Persistent prompt store with versioning and agent scoping."""

    def __init__(self, registry_path: str | None = None) -> None:
        self.loader = PromptLoader(registry_path)
        self.validator = PromptValidator(registry_path)
        self._records: dict[str, PromptRecord] = {}
        self._index()

    def _record_key(self, agent_id: str, prompt_type: str, version: str) -> str:
        return f"{agent_id}:{prompt_type}:{version}"

    def _index(self) -> None:
        """Index all prompts in the registry into memory."""
        prompts = self.loader.list_prompts()
        for p in prompts:
            key = self._record_key(p["agent_id"], p["prompt_type"], p["version"])
            try:
                template = self.loader.load_template(p["agent_id"], p["prompt_type"], p["version"])
                meta: dict[str, Any] = {}
                meta_path = self.loader.registry_path / p["agent_id"] / p["prompt_type"] / f"{p['version']}.meta.yaml"
                if meta_path.exists():
                    try:
                        import yaml
                        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        logger.warning("Failed to load meta for %s: %s", key, exc)

                self._records[key] = PromptRecord(
                    agent_id=p["agent_id"],
                    prompt_type=p["prompt_type"],
                    version=p["version"],
                    template=template,
                    template_hash=hashlib.sha256(template.encode("utf-8")).hexdigest()[:16],
                    meta=meta,
                )
            except Exception as exc:
                logger.warning("Failed to index prompt %s: %s", key, exc)

        logger.info("Indexed %d prompts in registry", len(self._records))

    def get(
        self,
        agent_id: str,
        prompt_type: str,
        version: str = "v1",
        render_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get a prompt by agent, type, and version. Optionally render with context."""
        key = self._record_key(agent_id, prompt_type, version)
        record = self._records.get(key)
        if not record:
            raise TemplateNotFoundError(agent_id, prompt_type, version, "")

        if record.deprecated:
            logger.warning("Accessing deprecated prompt %s: %s", key, record.deprecated_reason)

        result: dict[str, Any] = {
            "agent_id": record.agent_id,
            "prompt_type": record.prompt_type,
            "version": record.version,
            "template": record.template,
            "template_hash": record.template_hash,
            "meta": record.meta,
            "deprecated": record.deprecated,
        }

        if render_context is not None:
            result["rendered"] = self.loader.render(agent_id, prompt_type, version, render_context)
            result["render_context"] = render_context

        return result

    def get_latest(self, agent_id: str, prompt_type: str) -> dict[str, Any]:
        """Get the latest non-deprecated version of a prompt."""
        # Find all versions for this agent+type
        prefix = f"{agent_id}:{prompt_type}:"
        candidates = [
            (k, r) for k, r in self._records.items()
            if k.startswith(prefix) and not r.deprecated
        ]
        if not candidates:
            raise TemplateNotFoundError(agent_id, prompt_type, "latest", "")

        # Sort by version string (v1, v2, v1.1, etc.)
        def version_key(item: tuple[str, PromptRecord]) -> tuple[int, ...]:
            v = item[1].version.lstrip("v")
            try:
                return tuple(int(x) for x in v.split("."))
            except ValueError:
                return (0,)

        candidates.sort(key=version_key, reverse=True)
        latest = candidates[0][1]
        return self.get(latest.agent_id, latest.prompt_type, latest.version)

    def list_agents(self) -> list[str]:
        """List all agent IDs in the registry."""
        agents: set[str] = set()
        for record in self._records.values():
            agents.add(record.agent_id)
        return sorted(agents)

    def list_prompt_types(self, agent_id: str) -> list[str]:
        """List all prompt types for an agent."""
        types: set[str] = set()
        for record in self._records.values():
            if record.agent_id == agent_id:
                types.add(record.prompt_type)
        return sorted(types)

    def list_versions(self, agent_id: str, prompt_type: str) -> list[str]:
        """List all versions for an agent+prompt_type."""
        prefix = f"{agent_id}:{prompt_type}:"
        versions: set[str] = set()
        for k, r in self._records.items():
            if k.startswith(prefix):
                versions.add(r.version)
        return sorted(versions, key=lambda v: tuple(int(x) for x in v.lstrip("v").split(".")))

    def validate(self, agent_id: str, prompt_type: str, version: str = "v1") -> ValidationResult:
        """Validate a specific prompt."""
        return self.validator.validate(agent_id, prompt_type, version)

    def validate_all(self) -> list[ValidationResult]:
        """Validate all prompts in the registry."""
        return self.validator.validate_all()

    def refresh(self) -> None:
        """Re-index the registry (call after external changes)."""
        self._records.clear()
        self._index()

    def stats(self) -> dict[str, Any]:
        """Return registry statistics."""
        total = len(self._records)
        deprecated = sum(1 for r in self._records.values() if r.deprecated)
        agents = len(self.list_agents())
        return {
            "total_prompts": total,
            "deprecated_prompts": deprecated,
            "active_prompts": total - deprecated,
            "agents": agents,
        }
