"""Generate typed inter-service HTTP clients from OpenAPI specs."""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICES = [
    "control-plane-api",
    "orchestrator",
    "data-ingestion-pipeline",
    "content-graph-service",
    "policy-engine",
    "asset-store",
    "agent-runtime",
    "provider-gateway",
    "clipping-engine",
    "media-renderer",
    "research-service",
    "analytics-ingestion",
    "event-schema-registry",
    "quota-broker",
    "rights-registry-service",
    "publishing-service",
    "notification-service",
    "agent-registry-service",
    "model-eval-service",
    "billing-service",
]

OPENAPI_BASE = Path("../../contracts/openapi")
OUTPUT_BASE = Path("src/api_clients")


def generate_client(service: str, spec_path: Path, output_dir: Path) -> bool:
    """Generate a Python client for a service using openapi-generator-cli."""
    if not spec_path.exists():
        logger.warning("OpenAPI spec not found for %s at %s", service, spec_path)
        return False

    pkg_name = service.replace("-", "_")
    out = output_dir / pkg_name
    out.mkdir(parents=True, exist_ok=True)

    cmd = [
        "openapi-generator-cli",
        "generate",
        "-i", str(spec_path),
        "-g", "python",
        "-o", str(out),
        "--package-name", f"api_clients.{pkg_name}",
        "--additional-properties=library=asyncio,generateSourceCodeOnly=true",
    ]

    logger.info("Generating client for %s...", service)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("Client generated for %s", service)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to generate client for %s: %s", service, exc.stderr)
        return False
    except FileNotFoundError:
        logger.error("openapi-generator-cli not found. Install with: npm install -g @openapitools/openapi-generator-cli")
        return False


def generate_all() -> int:
    """Generate clients for all services."""
    success = 0
    for service in SERVICES:
        spec = OPENAPI_BASE / f"{service}.yaml"
        if not spec.exists():
            spec = OPENAPI_BASE / f"{service}.json"
        if generate_client(service, spec, OUTPUT_BASE):
            success += 1
    logger.info("Generated %d/%d clients", success, len(SERVICES))
    return 0 if success == len(SERVICES) else 1


def generate_stub_client(service: str) -> str:
    """Generate a minimal typed stub client when OpenAPI spec is unavailable."""
    pkg_name = service.replace("-", "_")
    return f""""""Typed HTTP client stub for {service}.

Stubs consolidate into api_clients.clients (shared BaseServiceClient). Replace with full OpenAPI-generated client
when the service's OpenAPI specification is available.
""""""
from __future__ import annotations

from typing import Any

import httpx


class {pkg_name.title().replace("_", "")}Client:
    """Async HTTP client for {service}."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.get(f"{{self.base_url}}/health")
        response.raise_for_status()
        return response.json()

    async def ready(self) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.get(f"{{self.base_url}}/ready")
        response.raise_for_status()
        return response.json()
""""""


def generate_all_stubs() -> None:
    """Generate stub clients for all services."""
    for service in SERVICES:
        pkg_name = service.replace("-", "_")
        pkg_dir = OUTPUT_BASE / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        init_file = pkg_dir / "__init__.py"
        client_file = pkg_dir / "client.py"
        stub_code = generate_stub_client(service)
        client_file.write_text(stub_code)
        init_file.write_text(f'from api_clients.{pkg_name}.client import {pkg_name.title().replace("_", "")}Client\n')
        logger.info("Stub client created for %s", service)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SentraAura API clients")
    parser.add_argument("--stubs", action="store_true", help="Generate stub clients instead of OpenAPI")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.stubs:
        generate_all_stubs()
        return 0
    return generate_all()


if __name__ == "__main__":
    sys.exit(main())
