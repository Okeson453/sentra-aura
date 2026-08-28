"""Prompt template validator enforcing structure, variable contracts, and versioning discipline."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    """Result of prompt validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    agent_id: str
    prompt_type: str
    version: str


class PromptValidator:
    """Validates prompt templates and their metadata against the SentraAura schema."""

    REQUIRED_META_FIELDS = {"description", "author", "created_at", "variables"}
    ALLOWED_VARIABLE_TYPES = {"string", "number", "boolean", "array", "object", "enum"}
    MAX_PROMPT_LENGTH = 50000  # characters
    MAX_VARIABLES = 50

    def __init__(self, registry_path: str | None = None) -> None:
        self.registry_path = Path(registry_path or self._default_registry_path())

    def _default_registry_path(self) -> str:
        here = Path(__file__).resolve().parent
        candidates = [
            here.parent / "prompts",
            here.parent.parent / "prompts",
            Path("/app/packages/prompt-registry/prompts"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return str(here.parent / "prompts")

    def validate(self, agent_id: str, prompt_type: str, version: str = "v1") -> ValidationResult:
        """Validate a prompt template and its metadata."""
        errors: list[str] = []
        warnings: list[str] = []

        template_path = self.registry_path / agent_id / prompt_type / f"{version}.jinja2"
        meta_path = template_path.with_suffix(".meta.yaml")

        # Check template exists
        if not template_path.exists():
            errors.append(f"Template file missing: {template_path}")
            return ValidationResult(False, errors, warnings, agent_id, prompt_type, version)

        template_text = template_path.read_text(encoding="utf-8")

        # Check meta exists
        if not meta_path.exists():
            warnings.append(f"Metadata file missing: {meta_path}")
        else:
            meta_errors, meta_warnings = self._validate_meta(meta_path, template_text)
            errors.extend(meta_errors)
            warnings.extend(meta_warnings)

        # Validate template structure
        tmpl_errors, tmpl_warnings = self._validate_template(template_text)
        errors.extend(tmpl_errors)
        warnings.extend(tmpl_warnings)

        # Cross-check variables between meta and template
        if meta_path.exists() and _YAML_AVAILABLE:
            meta_data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
            meta_vars = {v["name"] for v in meta_data.get("variables", [])}
            template_vars = self._extract_jinja2_variables(template_text)
            missing_in_meta = template_vars - meta_vars
            missing_in_template = meta_vars - template_vars
            if missing_in_meta:
                warnings.append(f"Variables used in template but not declared in meta: {missing_in_meta}")
            if missing_in_template:
                warnings.append(f"Variables declared in meta but not used in template: {missing_in_template}")

        valid = len(errors) == 0
        return ValidationResult(valid, errors, warnings, agent_id, prompt_type, version)

    def _validate_meta(self, meta_path: Path, template_text: str) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        if not _YAML_AVAILABLE:
            warnings.append("PyYAML not installed; skipping metadata validation")
            return errors, warnings

        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Invalid YAML in metadata: {exc}")
            return errors, warnings

        if not isinstance(meta, dict):
            errors.append("Metadata must be a YAML mapping")
            return errors, warnings

        missing = self.REQUIRED_META_FIELDS - set(meta.keys())
        if missing:
            errors.append(f"Missing required metadata fields: {missing}")

        # Validate variables schema
        variables = meta.get("variables", [])
        if not isinstance(variables, list):
            errors.append("'variables' must be a list")
        else:
            if len(variables) > self.MAX_VARIABLES:
                errors.append(f"Too many variables: {len(variables)} > {self.MAX_VARIABLES}")
            for i, var in enumerate(variables):
                if not isinstance(var, dict):
                    errors.append(f"Variable {i} must be a mapping")
                    continue
                if "name" not in var:
                    errors.append(f"Variable {i} missing 'name'")
                if "type" in var and var["type"] not in self.ALLOWED_VARIABLE_TYPES:
                    errors.append(f"Variable '{var.get('name', i)}' has invalid type: {var['type']}")

        # Version consistency
        if "version" in meta and meta["version"] != meta_path.stem.replace(".meta", "").replace(".", ""):
            warnings.append("Metadata version does not match filename")

        return errors, warnings

    def _validate_template(self, template_text: str) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        if len(template_text) > self.MAX_PROMPT_LENGTH:
            errors.append(f"Template exceeds max length: {len(template_text)} > {self.MAX_PROMPT_LENGTH}")

        if not template_text.strip():
            errors.append("Template is empty")

        # Check for potentially dangerous constructs
        if "{% raw %}" in template_text and "{% endraw %}" not in template_text:
            errors.append("Unclosed {% raw %} block")

        # Check for system prompt leakage
        if "system" in template_text.lower() and "user" not in template_text.lower():
            warnings.append("Template contains 'system' without 'user' — verify role separation")

        # Check for hardcoded secrets
        secret_patterns = [
            re.compile(r"\b(?:sk-|pk-|AKIA|ghp_|glpat-)[A-Za-z0-9_\-]{20,}\b"),
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        ]
        for pattern in secret_patterns:
            if pattern.search(template_text):
                errors.append("Template appears to contain hardcoded secrets or PII")
                break

        return errors, warnings

    def _extract_jinja2_variables(self, template_text: str) -> set[str]:
        """Extract top-level Jinja2 variables from template text."""
        pattern = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\b")
        return set(pattern.findall(template_text))

    def validate_all(self) -> list[ValidationResult]:
        """Validate all prompts in the registry."""
        results: list[ValidationResult] = []
        if not self.registry_path.exists():
            logger.warning("Registry path does not exist: %s", self.registry_path)
            return results

        for agent_dir in sorted(self.registry_path.iterdir()):
            if not agent_dir.is_dir():
                continue
            for prompt_type_dir in sorted(agent_dir.iterdir()):
                if not prompt_type_dir.is_dir():
                    continue
                for template_file in sorted(prompt_type_dir.glob("*.jinja2")):
                    version = template_file.stem
                    result = self.validate(agent_dir.name, prompt_type_dir.name, version)
                    results.append(result)
        return results
