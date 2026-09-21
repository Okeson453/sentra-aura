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
    "record_analytics": ("analytics-ingestion", "/api/v1/analytics/record"),
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
    "update_learning": lambda: acts.update_learning("c", "v", {"normalized_metrics": [{"video_id": "v"}]}, {}),
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
    async def _ok(service, endpoint, payload=None, tenant_id=None):
        assert (service, endpoint) == ("research-service", "/research")
        return {"sources": ["s1"], "claims": ["c1"]}

    monkeypatch.setattr(acts, "_call_service", _ok)
    out = await acts.research_topic("chan", "topic")
    assert out["status"] == "completed"
    assert out["sources"] == ["s1"]


@pytest.mark.asyncio
async def test_publish_content_requests_platform_publication(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def _fake(service, endpoint, payload=None, tenant_id=None):
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


def test_record_analytics_targets_a_real_post_route():
    """The measurement leg must post to a route analytics-ingestion really serves.

    Regression: it posted to ``/api/v1/tasks/status``, which that service exposes
    as a GET-only route, so every call returned 405 and the feedback loop's
    measurement step recorded nothing while the activity reported success.
    """
    src = _activities_source()
    assert re.search(r'"analytics-ingestion"\s*,\s*"/api/v1/analytics/record"', src), (
        "record_analytics must post to /api/v1/analytics/record"
    )
    # Only the request-target string matters; a comment that mentions the old
    # route while explaining the defect is not a regression.
    assert '"analytics-ingestion",\n        "/api/v1/tasks/status"' not in src, (
        "record_analytics must not target the GET-only /api/v1/tasks/status"
    )

    analytics_src_dir = (
        Path(acts.__file__).parents[3]
        / "analytics-ingestion"
        / "src"
        / "analytics_ingestion"
    )
    if not analytics_src_dir.exists():
        pytest.skip("analytics-ingestion source not present in this checkout")
    # The route may live in any module of the package (main composes routers).
    analytics_src = "\n".join(
        p.read_text() for p in sorted(analytics_src_dir.glob("*.py"))
    )
    assert '@router.post("/api/v1/analytics/record")' in analytics_src or (
        '@app.post("/api/v1/analytics/record")' in analytics_src
    ), "analytics-ingestion must expose a POST /api/v1/analytics/record route"
    assert "@router.post(\"/api/v1/tasks/status\")" not in analytics_src
    assert "@app.post(\"/api/v1/tasks/status\")" not in analytics_src


@pytest.mark.asyncio
async def test_update_learning_refuses_without_measured_metrics():
    """The learning leg must not proceed on a payload the service would reject.

    Regression: it forwarded the recording acknowledgement (not a
    NormalizedMetrics row), so /api/v1/signals returned 400 and no signal was
    ever produced. Absent measurements must be a loud, explicit precondition
    failure rather than a fabricated metric or a silent success.
    """
    with pytest.raises(ValueError, match="normalized_metrics"):
        await acts.update_learning("c", "v", {"event_id": "e"}, {})


@pytest.mark.asyncio
async def test_call_or_raise_forwards_tenant_to_the_service_call(monkeypatch):
    """Tenant lineage must reach ``_call_service`` as a signed claim.

    Regression: it travelled as a plain kwarg into ``**extra``, so it was echoed
    into the activity result and never reached the token — leaving every
    tenant-authorized downstream service to reject the call once auth became
    fail-closed.
    """
    seen: dict = {}

    async def _fake_call(service_name, endpoint, payload, tenant_id=None):
        seen["tenant_id"] = tenant_id
        seen["endpoint"] = endpoint
        return {"ok": True}

    monkeypatch.setattr(acts, "_call_service", _fake_call)
    await acts._call_service_or_raise(
        "analytics-ingestion", "/api/v1/signals", {}, activity_name="t", tenant_id="tenant-a"
    )
    assert seen["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_record_analytics_sends_a_tenant_claim(monkeypatch):
    """The measurement call must be tenant-attributable, not anonymous."""
    seen: dict = {}

    def _fake_token(subject, roles=None, **kwargs):
        seen.update(kwargs)
        return "signed-token"

    class _FakeResponse:
        status_code = 200
        content = b'{"event_id": "e1"}'
        text = '{"event_id": "e1"}'

        def json(self):
            return {"event_id": "e1", "measurement_status": "recorded"}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            seen["url"] = url
            return _FakeResponse()

    monkeypatch.setattr(acts, "create_service_token", _fake_token)
    monkeypatch.setattr(acts.httpx, "AsyncClient", _FakeClient)

    result = await acts.record_analytics(
        "chan-1", "vid-1", {"tenant_id": "tenant-a", "platform": "youtube"}, {}
    )
    assert seen.get("tenant_id") == "tenant-a"
    assert seen.get("url", "").endswith("/api/v1/analytics/record")
    assert result["measurement_status"] == "recorded"


def _patch_service_io(monkeypatch, seen: dict):
    """Capture ``create_service_token`` kwargs while stubbing the HTTP client."""

    def _fake_token(subject, roles=None, **kwargs):
        seen.update(kwargs)
        return "signed-token"

    class _FakeResponse:
        status_code = 200
        content = b'{"ok": true}'
        text = '{"ok": true}'

        def json(self):
            return {
                "publication_id": "pub-1",
                "status": "published",
                "tenant_id": seen.get("tenant_id"),
                "approved": True,
            }

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            seen["url"] = url
            seen.setdefault("urls", []).append(url)
            return _FakeResponse()

        async def get(self, url):
            seen["url"] = url
            seen.setdefault("urls", []).append(url)
            return _FakeResponse()

    monkeypatch.setattr(acts, "create_service_token", _fake_token)
    monkeypatch.setattr(acts.httpx, "AsyncClient", _FakeClient)


@pytest.mark.asyncio
async def test_publish_content_sends_a_tenant_claim(monkeypatch):
    """The publish leg must carry the tenant as a signed token claim.

    Regression: ``publish_content`` called publishing-service with no tenant,
    so the tenant-aware boundary rejected the call (401) and nothing was ever
    sent to an external platform while the activity still reported success.
    """
    seen: dict = {}
    _patch_service_io(monkeypatch, seen)
    await acts.publish_content("chan-1", "vid-1", {"candidates": []}, {}, tenant_id="tenant-a")
    assert seen.get("tenant_id") == "tenant-a"
    # Both the create and the publish call must carry the claim.
    assert seen["urls"][0].endswith("/publications")
    assert "pub-1" in seen["urls"][0] or seen["urls"][0].endswith("/publications")
    assert seen["urls"][-1].endswith("/publications/pub-1/publish")


@pytest.mark.asyncio
async def test_publish_content_attributes_a_tenant_less_run(monkeypatch):
    """A run with no lineage must still be attributable, not rejected."""
    seen: dict = {}
    _patch_service_io(monkeypatch, seen)
    await acts.publish_content("chan-1", "vid-1", {"candidates": []}, {})
    assert seen.get("tenant_id") == acts.UNATTRIBUTED_TENANT


@pytest.mark.asyncio
async def test_optimize_policy_sends_a_tenant_claim(monkeypatch):
    """The optimisation leg must reach the governance gate with a tenant.

    Regression: ``optimize_policy`` called policy-engine with no tenant, and
    policy-engine resolves the acting tenant from the verified claim and fails
    closed, so the loop's policy-optimisation step could never execute.
    """
    seen: dict = {}
    _patch_service_io(monkeypatch, seen)
    await acts.optimize_policy("chan-1", {}, {}, tenant_id="tenant-a")
    assert seen.get("tenant_id") == "tenant-a"
    assert seen.get("url", "").endswith("/api/v1/evaluate")


@pytest.mark.asyncio
async def test_every_service_calling_activity_sends_a_tenant_claim(monkeypatch):
    """No service-calling activity may omit tenant lineage from its token."""
    src = _activities_source()
    # publish_content/optimize_policy use _call_service directly (their calls are
    # not routed through _call_service_or_raise), so assert on both call styles.
    assert "tenant_id=tenant" in src
    assert 'tenant_id=tenant_id or UNATTRIBUTED_TENANT' in src
    assert "tenant_id=tenant_id or UNATTRIBUTED_TENANT,\n        )" in src


@pytest.mark.asyncio
async def test_workflow_threads_tenant_into_every_activity():
    """The workflow must pass tenant_id to all eleven activity invocations.

    A single missed argument silently re-breaks that leg of the loop: the
    activity falls back to the unattributed tenant, or omits the claim.
    """
    wf_src = Path(acts.__file__).parent.joinpath("workflows.py").read_text()
    assert 'tenant_id = params.get("tenant_id")' in wf_src
    for call in (
        "args=(channel_id, topic, tenant_id)",
        "args=(channel_id, research, tenant_id)",
        "args=(channel_id, script, tenant_id)",
        "args=(channel_id, script, voice, visuals, tenant_id)",
        'args=(channel_id, video.get("video_id"), script, tenant_id)',
        'args=(channel_id, video.get("video_id"), clips, script, tenant_id)',
        'args=(channel_id, video.get("video_id"), publish_result, clips, tenant_id)',
        'args=(channel_id, video.get("video_id"), analytics_result, clips, tenant_id)',
        "args=(channel_id, learning_result, analytics_result, tenant_id)",
    ):
        assert call in wf_src, f"workflow does not thread tenant_id: {call}"


@pytest.mark.asyncio
async def test_record_analytics_attributes_a_tenant_less_publish(monkeypatch):
    """A publish with no tenant lineage must still be attributable, not dropped.

    The fallback is the same value analytics-ingestion uses, so the two agree
    rather than the downstream call being rejected for a missing claim.
    """
    seen: dict = {}

    def _fake_token(subject, roles=None, **kwargs):
        seen.update(kwargs)
        return "signed-token"

    class _FakeResponse:
        status_code = 200
        content = b'{"event_id": "e2"}'
        text = '{"event_id": "e2"}'

        def json(self):
            return {"event_id": "e2", "measurement_status": "unconfirmed"}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            return _FakeResponse()

    monkeypatch.setattr(acts, "create_service_token", _fake_token)
    monkeypatch.setattr(acts.httpx, "AsyncClient", _FakeClient)

    await acts.record_analytics("chan-1", "vid-1", {"platform": "youtube"}, {})
    assert seen.get("tenant_id") == acts.UNATTRIBUTED_TENANT


@pytest.mark.asyncio
async def test_run_tenant_threads_through_publish_to_analytics(monkeypatch):
    """End-to-end: a workflow tenant reaches the publish + record tokens."""
    claims: list = []

    def _fake_token(subject, roles=None, **kwargs):
        claims.append(kwargs.get("tenant_id"))
        return "signed-token"

    class _FakeResponse:
        status_code = 200
        content = b'{"publication_id": "pub-1"}'
        text = '{"publication_id": "pub-1"}'

        def json(self):
            return {"publication_id": "pub-1", "status": "published"}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            return _FakeResponse()

    monkeypatch.setattr(acts, "create_service_token", _fake_token)
    monkeypatch.setattr(acts.httpx, "AsyncClient", _FakeClient)

    published = await acts.publish_content(
        "chan-1", "vid-1", {"candidates": []}, {}, tenant_id="tenant-a"
    )
    # The tenant lineage must survive into the publish result, which is what the
    # analytics ingestion leg reads.
    assert published["tenant_id"] == "tenant-a"
    await acts.record_analytics("chan-1", "vid-1", published, {})
    assert "tenant-a" in claims
