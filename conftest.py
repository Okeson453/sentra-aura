"""Root pytest configuration for SentraAura."""
from __future__ import annotations

import sys
from pathlib import Path

# Get absolute path to project root
ROOT = Path(__file__).parent.resolve()

# Add all src directories to sys.path
paths = [
    ROOT / "packages" / "content-graph-client" / "src",
    ROOT / "packages" / "agent-contracts" / "src",
    ROOT / "packages" / "service-kit" / "src",
    ROOT / "packages" / "event-bus" / "src",
    ROOT / "packages" / "event-schemas" / "src",
    ROOT / "packages" / "test-factory" / "src",
    ROOT / "packages" / "prompt-registry" / "src",
    ROOT / "packages" / "provider-interfaces" / "src",
    ROOT / "packages" / "observability" / "src",
    ROOT / "packages" / "sentinel-exceptions" / "src",
    ROOT / "packages" / "sentinel-security" / "src",
    ROOT / "services" / "control-plane-api" / "src",
    ROOT / "services" / "content-graph-service" / "src",
    ROOT / "services" / "policy-engine" / "src",
    ROOT / "services" / "asset-store" / "src",
    ROOT / "services" / "data-ingestion-pipeline" / "src",
    ROOT / "services" / "orchestrator" / "src",
    ROOT / "services" / "provider-gateway" / "src",
    ROOT / "services" / "research-service" / "src",
    ROOT / "services" / "agent-runtime" / "src",
    ROOT / "services" / "agent-registry-service" / "src",
    ROOT / "tools" / "sentra-cli" / "src",
]

for p in paths:
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
