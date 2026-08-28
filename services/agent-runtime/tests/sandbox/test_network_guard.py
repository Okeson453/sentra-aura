from __future__ import annotations

import httpx
import pytest

from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.network_guard import NetworkAccessDeniedError
from agent_runtime.sandbox.runner import SandboxLimits, SandboxRunner
from agent_runtime.tool_permissions import (
    PermissionDecision,
    PermissionMatrix,
    ToolPermission,
)


@pytest.mark.asyncio
async def test_allow_network_false_blocks_httpx(mock_gateway_url=None):
    """allow_network=False must block a real httpx outbound attempt."""
    runner = SandboxRunner(SandboxLimits(allow_network=False, max_cpu_time_seconds=10.0))

    async def _http_get() -> dict:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://127.0.0.1:9/")  # connection attempt
            return {"status_code": r.status_code}

    result = await runner.run(_http_get, (), {}, agent_id="probe", tool_name="http_get")
    assert result.success is False
    assert "Network egress denied" in (result.stderr or "")
    assert result.audit_log.get("error") == "network_denied"


@pytest.mark.asyncio
async def test_allow_network_true_allows_httpx():
    """allow_network=True must still allow real HTTP (regression)."""
    # Use a local closed port only for connect semantics with allow — better use mock if up.
    # Call example.com would need network; use 127.0.0.1 with something that fails for other reasons.
    # Start a tiny local server via asyncio? Use httpx against invalid but with allow True:
    # Connection refused is NOT NetworkAccessDeniedError.
    runner = SandboxRunner(SandboxLimits(allow_network=True, max_cpu_time_seconds=10.0))

    async def _http_get() -> str:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                await client.get("http://127.0.0.1:1/")
        except httpx.HTTPError as exc:
            return f"network-ok:{type(exc).__name__}"
        return "network-ok:unexpected"

    result = await runner.run(_http_get, (), {}, agent_id="probe", tool_name="http_get")
    assert result.success is True
    assert str(result.output).startswith("network-ok:")
    assert "NetworkAccessDenied" not in str(result.output)


@pytest.mark.asyncio
async def test_restriction_does_not_leak_outside_sandbox():
    """Harness calls outside sandbox.run must not be blocked after a restricted run."""
    runner = SandboxRunner(SandboxLimits(allow_network=False, max_cpu_time_seconds=5.0))

    async def _blocked() -> None:
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.get("http://127.0.0.1:9/")

    result = await runner.run(_blocked, (), {}, agent_id="probe", tool_name="x")
    assert result.success is False

    # Outside sandbox — should get ConnectError/Timeout, not NetworkAccessDeniedError
    with pytest.raises(Exception) as ei:
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.get("http://127.0.0.1:1/")
    assert not isinstance(ei.value, NetworkAccessDeniedError)
    assert "Network egress denied" not in str(ei.value)


@pytest.mark.asyncio
async def test_agent_with_allow_network_false_blocks_tool():
    from agent_runtime.envelope import AgentMessageEnvelope
    from agent_contracts.envelope import AgentMessage

    matrix = PermissionMatrix(
        custom_permissions=[
            ToolPermission("net_probe", "http_get", "execute", PermissionDecision.ALLOW, "t"),
        ]
    )

    class Probe(BaseAgent[dict]):
        def __init__(self) -> None:
            super().__init__(
                agent_id="net_probe",
                name="Probe",
                domain="test",
                permission_matrix=matrix,
                sandbox_limits=SandboxLimits(allow_network=False, max_cpu_time_seconds=10.0),
            )
            self.register_tool("http_get", self._http_get)

        @property
        def capabilities(self) -> list[str]:
            return ["http_get"]

        async def execute(self, envelope: AgentMessageEnvelope) -> dict:
            return {}

        async def _http_get(self, url: str) -> dict:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(url)
                return {"status_code": r.status_code}

    probe = Probe()
    with pytest.raises(RuntimeError) as ei:
        await probe.invoke_tool("http_get", args=("http://127.0.0.1:9/",))
    assert "Network egress denied" in str(ei.value)
