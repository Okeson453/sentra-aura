"""Schema validator for SentraAura events.

Validates event payloads against canonical schemas in contracts/events/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import ValidationError


class SchemaValidator:
    """Validate events against JSON schemas from contracts/events/."""

    def __init__(self, schemas_dir: str | None = None) -> None:
        if schemas_dir is None:
            # Default: resolve from package location up to repo root
            # by searching for contracts/ directory marker
            here = Path(__file__).resolve().parent
            repo_root = here
            while repo_root.parent != repo_root:
                if (repo_root / "contracts").exists():
                    break
                repo_root = repo_root.parent
            schemas_dir = str(repo_root / "contracts" / "events" / "v1")
        self.schemas_dir = Path(schemas_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    def _load_schema(self, name: str) -> dict[str, Any]:
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
        """Validate an event against a named schema.

        Returns (is_valid, list_of_error_messages).
        """
        try:
            schema = self._load_schema(schema_name)
            jsonschema.validate(instance=event, schema=schema)
            return True, []
        except ValidationError as exc:
            return False, [str(exc.message)]
        except FileNotFoundError as exc:
            return False, [str(exc)]
        except Exception as exc:
            return False, [f"Unexpected validation error: {exc}"]
