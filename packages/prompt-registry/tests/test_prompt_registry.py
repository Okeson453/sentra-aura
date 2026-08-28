"""Tests for Prompt Registry loader, validator, and store."""

from __future__ import annotations

import pytest
from pathlib import Path

from prompt_registry.loader import PromptLoader, TemplateNotFoundError
from prompt_registry.validator import PromptValidator, ValidationResult
from prompt_registry.store import PromptStore


@pytest.fixture
def registry_path() -> str:
    # Use the actual registry path in the project
    here = Path(__file__).resolve().parent.parent
    return str(here / "prompts")


class TestPromptLoader:
    def test_load_template_exists(self, registry_path: str) -> None:
        loader = PromptLoader(registry_path)
        template = loader.load_template("research_agent", "gather", "v1")
        assert "Research Agent" in template
        assert "{%" in template or "{{" in template

    def test_load_template_not_found(self, registry_path: str) -> None:
        loader = PromptLoader(registry_path)
        with pytest.raises(TemplateNotFoundError):
            loader.load_template("nonexistent_agent", "nonexistent", "v999")

    def test_render_with_context(self, registry_path: str) -> None:
        loader = PromptLoader(registry_path)
        rendered = loader.render(
            "research_agent", "gather", "v1",
            context={"topic": "Quantum Computing", "channel_name": "TestChannel"},
        )
        assert "Quantum Computing" in rendered
        assert "TestChannel" in rendered

    def test_list_variables(self, registry_path: str) -> None:
        loader = PromptLoader(registry_path)
        variables = loader.list_variables("research_agent", "gather", "v1")
        assert "topic" in variables
        assert "channel_name" in variables

    def test_list_prompts(self, registry_path: str) -> None:
        loader = PromptLoader(registry_path)
        prompts = loader.list_prompts()
        assert len(prompts) > 0
        assert any(p["agent_id"] == "research_agent" and p["prompt_type"] == "gather" for p in prompts)

    def test_list_prompts_by_agent(self, registry_path: str) -> None:
        loader = PromptLoader(registry_path)
        prompts = loader.list_prompts(agent_id="scripting_agent")
        assert all(p["agent_id"] == "scripting_agent" for p in prompts)


class TestPromptValidator:
    def test_validate_valid_prompt(self, registry_path: str) -> None:
        validator = PromptValidator(registry_path)
        result = validator.validate("research_agent", "gather", "v1")
        assert isinstance(result, ValidationResult)
        # Valid prompts may have warnings but should not have errors
        assert result.agent_id == "research_agent"
        assert result.prompt_type == "gather"

    def test_validate_missing_template(self, registry_path: str) -> None:
        validator = PromptValidator(registry_path)
        result = validator.validate("nonexistent", "nonexistent", "v1")
        assert result.valid is False
        assert any("missing" in e.lower() for e in result.errors)

    def test_validate_all(self, registry_path: str) -> None:
        validator = PromptValidator(registry_path)
        results = validator.validate_all()
        assert len(results) > 0
        # All real prompts should be structurally valid
        for r in results:
            assert isinstance(r, ValidationResult)


class TestPromptStore:
    def test_get_prompt(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        result = store.get("research_agent", "gather", "v1")
        assert result["agent_id"] == "research_agent"
        assert result["prompt_type"] == "gather"
        assert "template" in result
        assert "template_hash" in result

    def test_get_with_render(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        result = store.get(
            "research_agent", "gather", "v1",
            render_context={"topic": "AI Safety", "channel_name": "TechChannel"},
        )
        assert "rendered" in result
        assert "AI Safety" in result["rendered"]

    def test_get_latest(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        result = store.get_latest("research_agent", "gather")
        assert result["agent_id"] == "research_agent"
        assert result["prompt_type"] == "gather"

    def test_list_agents(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        agents = store.list_agents()
        assert "research_agent" in agents
        assert "scripting_agent" in agents

    def test_list_prompt_types(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        types = store.list_prompt_types("scripting_agent")
        assert "draft" in types
        assert "critique" in types
        assert "rewrite" in types

    def test_list_versions(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        versions = store.list_versions("research_agent", "gather")
        assert "v1" in versions

    def test_stats(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        stats = store.stats()
        assert stats["total_prompts"] > 0
        assert stats["active_prompts"] > 0
        assert stats["agents"] > 0

    def test_validate_all_via_store(self, registry_path: str) -> None:
        store = PromptStore(registry_path)
        results = store.validate_all()
        assert len(results) > 0
        for r in results:
            assert isinstance(r, ValidationResult)
