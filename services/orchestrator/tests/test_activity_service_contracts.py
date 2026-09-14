"""Regression tests for orchestrator activity service contracts and failure semantics.

These cover three defects fixed in the hourly engineering loop:

1. Activities called service routes that do not exist (analytics-ingestion was
   addressed at ``/v1/events`` and ``/v1/learning``, policy-engine at
   ``/policies/optimize`` -- none of which the target services expose), and
   ``_call_service`` silently retargeted an unmapped service at localhost:8000.
2. Every activity converted a service failure into a ``status="failed"`` dict,
   so Temporal recorded the activity as COMPLETED and retry policies / crash
   recovery never engaged.
3. ``publish_content`` created a publication record but never called the
   ``/publications/{id}/publish`` endpoint, so nothing was ever sent to the
   external platform while the activity reported success.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from orchestrator import activities as acts

# Pinned so that a future edit which reintroduces a route the target service does
# not expose fails here instead of at runtime inside a Temporal activity.
EXPECTED_ROUTES = {
    "execute_agent_task": ("agent-runtime", "/v1/execute"),
    "research_topic": ("research-service", "/research"),
    "draft_script": ("agent-runtime", "/v1/draft-script"),
    "produce_voice": ("provider-gateway", "/v1/tts"),
    "generate_visuals": ("provider-gateway", "/v1/images/generate"),
    "render_video": ("media-renderer", "/render"),
    "generate_clips": ("clipping-engine", "/clips/detect"),
    "record_analytics": ("analytics-ingestion", "/api/v1/tasks/status"),
    "update_learning": ("analytics-ingestion", "/api/v1/signals"),
    "optimize_policy": ("policy-engine", "/api/v1/evaluate"),
}

FAILURE_CASES = {
    "execute_agent_task": lambda: acts.execute_agent_task("t", "a", {}),
    "research_topic": lambda: acts.research_topic("c", "topic"),
    "draft_script": lambda: acts.draft_script("c", {"topic": "t"}),
    "produce_voice": lambda: acts.produce_voice("c", {}),
    "generate_visuals": lambda: acts.generate_visuals("c", {}),
    "render_video": lambda: acts.render_video("c", {}, {}, {}),
    "generate_clips": lambda: acts.generate_clips("c", "v", {}),
    "publish_content": lambda: acts.publish_content("c", "v", {}, {}),
    "record_analytics": lambda: acts.record_analytics("c", "v", {}, {}),
    "update_learning": lambda: acts.update_learning("c", "v", {}, {}),
    "optimize_policy": lambda: acts.optimize_policy("c", {}, {}),
}


def _activities_source() -> str:
    return Path(acts.__file__).read_text()


def test_every_activity_service_name_is_mapped():
    """No activity may reference a service missing from the SERVICES map."""
    src = _activities_source()
    used = set(re.findall(r'_call_service(?:_or_raise)?\(\s*"([a-z0-9-]+)"', src))
    known_services = {svc for svc, _ in EXPECTED_ROUTES.values()} | {"publishing-service"}
    unmapped = used - set(acts.SERVICES)
    assert not unmapped, f"activities reference unmapped services: {sorted(unmapped)}"
    assert used <= known_services, (
        f"unexpected service names: {sorted(used - known_services)}"
    )


@pytest.mark.parametrize("name,expected", sorted(EXPECTED_ROUTES.items()))
def test_activity_routes_match_real_service_apis(name, expected):
    src = _activities_source()
    svc, ep = expected
    pattern = r'"' + re.escape(svc) + r'"\s*,\s*"' + re.escape(ep) + r'"'
    assert re.search(pattern, src), (
        f"{name} no longer calls {svc}{ep}"
    )


def test_services_map_has_no_localhost_fallback_target():
    assert not any("localhost" in base for base in acts.SERVICES.values())


@pytest.mark.asyncio
async def test_unknown_service_is_a_hard_error():
    with pytest.raises(ValueError):
        await acts._call_service("not-a-service", "/x", {})


@pytest.mark.asyncio
async def test_call_service_builds_url_from_services_map(monkeypatch):
    import httpx

    seen: dict[str, str] = {}

    class _Resp:
        content = b'{"ok": true}'

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, bool]:
            return {"ok": True}

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a) -> bool:
            return False

        async def post(self, url, json=None):
            seen["url"] = url
            return _Resp()

        async def get(self, url):
            seen["url"] = url
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    out = await acts._call_service("research-service", "/research", {"a": 1})
    assert out == {"ok": True}
    assert seen["url"] == "http://research-service:8000/research"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(FAILURE_CASES))
async def test_activity_raises_when_service_fails(monkeypatch, name):
    """A service failure must propagate, never be returned as a failed-success dict."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("service unavailable")

    monkeypatch.setattr(acts, "_call_service", _boom)
    with pytest.raises(RuntimeError):
        await FAILURE_CASES[name]()


@pytest.mark.asyncio
async def test_research_topic_completes_on_success(monkeypatch):
    async def _ok(service, endpoint, payload=None):
        assert (service, endpoint) == ("research-service", "/research")
        return {"sources": ["s1"], "claims": ["c1"]}

    monkeypatch.setattr(acts, "_call_service", _ok)
    out = await acts.research_topic("chan", "topic")
    assert out["status"] == "completed"
    assert out["sources"] == ["s1"]


@pytest.mark.asyncio
async def test_publish_content_requests_platform_publication(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def _fake(service, endpoint, payload=None):
        calls.append((service, endpoint))
        if endpoint == "/publications":
            return {"publication_id": "pub-1", "status": "pending"}
        return {"publication_id": "pub-1", "status": "published"}

    monkeypatch.setattr(acts, "_call_service", _fake)
    out = await acts.publish_content("chan", "vid", {"candidates": []}, {"title": "T"})
    assert ("publishing-service", "/publications/pub-1/publish") in calls
    assert out["video_publication_id"] == "pub-1"
    assert out["status"] == "completed"


def test_workflow_fails_loudly_on_activity_error():
    """The workflow must fail on activity exhaustion, and the retry policy must
    honour max_retries instead of pinning maximum_attempts to it."""
    wf_src = Path(acts.__file__).parent.joinpath("workflows.py").read_text()
    assert "maximum_attempts=max(1, task.max_retries + 1)" in wf_src
    assert "if task.retries >= task.max_retries:" not in wf_src
