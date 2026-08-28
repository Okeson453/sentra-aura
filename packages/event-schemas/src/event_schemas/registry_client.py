"""Schema registry client for SentraAura.

Provides typed access to canonical event schemas with validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


class SchemaRegistryClient:
    """Client for the SentraAura event schema registry."""

    def __init__(self, registry_url: str | None = None, local_schemas_dir: str | None = None) -> None:
        self.registry_url = registry_url
        if local_schemas_dir is None:
            here = Path(__file__).resolve().parent
            repo_root = here
            while repo_root.parent != repo_root:
                if (repo_root / "contracts").exists():
                    break
                repo_root = repo_root.parent
            self.schemas_dir = repo_root / "contracts" / "events" / "v1"
        else:
            self.schemas_dir = Path(local_schemas_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    def get_schema(self, name: str) -> dict[str, Any]:
        """Retrieve a schema by name."""
        if name in self._cache:
            return self._cache[name]

        if not name.endswith(".json"):
            name = f"{name}.json"

        path = self.schemas_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Schema not found: {path}")

        with open(path) as f:
            schema = json.load(f)
        self._cache[name] = schema
        return schema

    def validate(self, event: dict[str, Any], schema_name: str) -> tuple[bool, list[str]]:
        """Validate an event against a named schema."""
        try:
            schema = self.get_schema(schema_name)
            jsonschema.validate(instance=event, schema=schema)
            return True, []
        except jsonschema.ValidationError as exc:
            return False, [str(exc.message)]
        except Exception as exc:
            return False, [str(exc)]

    def list_schemas(self) -> list[str]:
        """List all available schema names."""
        return [p.stem for p in self.schemas_dir.glob("*.json")]
