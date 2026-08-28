"""Tests for test-factory package."""
import pytest

from test_factory.db_factories import ChannelFactory, ScriptFactory
from test_factory.temporal_worker import TemporalWorkerHarness
from test_factory.mock_providers import MockProviderGateway


def test_channel_factory():
    ch = ChannelFactory.build(name="Custom")
    assert ch["name"] == "Custom"
    assert ch["channel_id"].startswith("CH-")


def test_script_factory():
    scr = ScriptFactory.build(word_count=2000)
    assert scr["word_count"] == 2000
    assert scr["script_id"].startswith("SCR-")


@pytest.mark.asyncio
async def test_temporal_harness():
    harness = TemporalWorkerHarness()
    async def dummy_workflow(x: int) -> int:
        return x * 2
    harness.register_workflow("double", dummy_workflow)
    result = await harness.execute_workflow("double", args=(5,))
    assert result == 10


@pytest.mark.asyncio
async def test_mock_provider():
    mock = MockProviderGateway()
    result = await mock.complete("hello")
    assert result["text"] == "Mock completion"
    assert len(mock.get_call_log()) == 1
