"""Prompt template loader with Jinja2 rendering and variable injection."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, BaseLoader, TemplateNotFound, meta
    _JINJA_AVAILABLE = True
except ImportError:
    _JINJA_AVAILABLE = False

logger = logging.getLogger(__name__)


class PromptLoader:
    """Loads and renders Jinja2 prompt templates from the registry."""

    def __init__(self, registry_path: str | None = None) -> None:
        self.registry_path = Path(registry_path or self._default_registry_path())
        self._env: Any = None
        if _JINJA_AVAILABLE:
            self._env = Environment(loader=BaseLoader())
        self._cache: dict[str, str] = {}

    def _default_registry_path(self) -> str:
        """Compute default registry path relative to this package."""
        here = Path(__file__).resolve().parent
        # Look for prompts/ at package root or repo root
        candidates = [
            here.parent / "prompts",
            here.parent.parent / "prompts",
            Path("/app/packages/prompt-registry/prompts"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return str(here.parent / "prompts")

    def load_template(self, agent_id: str, prompt_type: str, version: str = "v1") -> str:
        """Load a raw Jinja2 template string for an agent."""
        cache_key = f"{agent_id}/{prompt_type}/{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        template_path = self.registry_path / agent_id / prompt_type / f"{version}.jinja2"
        if not template_path.exists():
            raise TemplateNotFoundError(agent_id, prompt_type, version, str(template_path))

        template_text = template_path.read_text(encoding="utf-8")
        self._cache[cache_key] = template_text
        logger.debug("Loaded template %s", cache_key)
        return template_text

    def render(self, agent_id: str, prompt_type: str, version: str = "v1", context: dict[str, Any] | None = None) -> str:
        """Render a prompt template with the given context variables."""
        template_text = self.load_template(agent_id, prompt_type, version)
        if not _JINJA_AVAILABLE:
            # Simple string substitution fallback
            return self._simple_render(template_text, context or {})

        template = self._env.from_string(template_text)
        return template.render(context or {})

    def list_variables(self, agent_id: str, prompt_type: str, version: str = "v1") -> set[str]:
        """List all Jinja2 variables required by a template."""
        template_text = self.load_template(agent_id, prompt_type, version)
        if not _JINJA_AVAILABLE:
            return self._extract_variables_simple(template_text)
        ast = self._env.parse(template_text)
        return meta.find_undeclared_variables(ast)

    def list_prompts(self, agent_id: str | None = None) -> list[dict[str, str]]:
        """List all available prompts in the registry."""
        results: list[dict[str, str]] = []
        search_root = self.registry_path
        if agent_id:
            search_root = search_root / agent_id
        if not search_root.exists():
            return results

        for agent_dir in sorted(search_root.iterdir()):
            if not agent_dir.is_dir():
                continue
            aid = agent_dir.name
            for prompt_type_dir in sorted(agent_dir.iterdir()):
                if not prompt_type_dir.is_dir():
                    continue
                ptype = prompt_type_dir.name
                for template_file in sorted(prompt_type_dir.glob("*.jinja2")):
                    version = template_file.stem
                    meta_file = template_file.with_suffix(".meta.yaml")
                    results.append({
                        "agent_id": aid,
                        "prompt_type": ptype,
                        "version": version,
                        "has_meta": meta_file.exists(),
                    })
        return results

    def _simple_render(self, template: str, context: dict[str, Any]) -> str:
        """Fallback rendering when Jinja2 is not installed."""
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{ {key} }}}}", str(value))
            result = result.replace(f"{{{{ {key} | default('') }}}}", str(value))
        return result

    def _extract_variables_simple(self, template: str) -> set[str]:
        """Simple variable extraction fallback."""
        import re
        pattern = re.compile(r"\{\{\s*(\w+)")
        return set(pattern.findall(template))


class TemplateNotFoundError(Exception):
    def __init__(self, agent_id: str, prompt_type: str, version: str, path: str) -> None:
        super().__init__(f"Template not found: {agent_id}/{prompt_type}/{version} at {path}")
        self.agent_id = agent_id
        self.prompt_type = prompt_type
        self.version = version
        self.path = path
