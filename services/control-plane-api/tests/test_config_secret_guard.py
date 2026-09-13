"""Security regression: production must refuse the insecure default JWT secret.

A repository-visible or short shared signing key lets any caller mint valid
JWTs and bypass authentication entirely (CWE-1188 / CWE-798). Each service
config must fail closed when it is told it is running in production while the
signing key is still the shipped default.
"""
from __future__ import annotations

import importlib

import pytest

# Settings-style services keyed off ENVIRONMENT == "production".
CLASS_BASED = [
    ("asset_store.config", "Settings"),
    ("content_graph_service.config", "Settings"),
    ("control_plane_api.config", "Settings"),
    ("data_ingestion_pipeline.config", "Settings"),
    ("orchestrator.config", "Settings"),
    ("policy_engine.config", "Settings"),
]

# ServiceConfig-style services keyed off LOG_LEVEL (is_production) and a
# per-service env prefix.
PREFIX_BASED = [
    ("clipping_engine.config", "ServiceConfig", "CLIPPING_ENGINE_"),
    ("media_renderer.config", "ServiceConfig", "MEDIA_RENDERER_"),
    ("publishing_service.config", "ServiceConfig", "PUBLISHING_SERVICE_"),
    ("rights_registry_service.config", "ServiceConfig", "RIGHTS_REGISTRY_SERVICE_"),
]

WEAK_SECRET = "change-me-in-production"
STRONG_SECRET = "s3ntra-aura-strong-unique-signing-key-0123456789"


def _load(module: str, name: str):
    try:
        mod = importlib.import_module(module)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"cannot import {module}: {exc}")
    return getattr(mod, name)


@pytest.mark.parametrize("module,name", CLASS_BASED)
def test_class_based_config_rejects_weak_secret_in_production(module, name, monkeypatch):
    config_cls = _load(module, name)

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", WEAK_SECRET)
    with pytest.raises(Exception):
        config_cls()  # must fail closed

    # Same production mode, strong secret -> accepted (no over-blocking).
    monkeypatch.setenv("JWT_SECRET", STRONG_SECRET)
    config_cls()

    # Dev with the default secret stays usable (no dev regression).
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET", WEAK_SECRET)
    config_cls()


@pytest.mark.parametrize("module,name,prefix", PREFIX_BASED)
def test_prefix_based_config_rejects_weak_secret_in_production(module, name, prefix, monkeypatch):
    config_cls = _load(module, name)

    monkeypatch.setenv(f"{prefix}LOG_LEVEL", "ERROR")  # is_production == True
    monkeypatch.setenv(f"{prefix}JWT_SECRET", WEAK_SECRET)
    with pytest.raises(Exception):
        config_cls()

    monkeypatch.setenv(f"{prefix}JWT_SECRET", STRONG_SECRET)
    config_cls()
