"""Unit tests for notification channels."""
from __future__ import annotations

import pytest

from notification_service.channels.slack import SlackClient
from notification_service.channels.pagerduty import PagerDutyClient
from notification_service.channels.email import EmailClient


@pytest.mark.asyncio
async def test_slack_client_initialization():
    client = SlackClient(webhook_url="https://hooks.slack.com/test")
    assert client.webhook_url == "https://hooks.slack.com/test"
    await client.close()


@pytest.mark.asyncio
async def test_pagerduty_client_initialization():
    client = PagerDutyClient(routing_key="test-key")
    assert client.routing_key == "test-key"
    await client.close()


def test_email_client_initialization():
    client = EmailClient(
        host="smtp.example.com",
        port=587,
        username="test@example.com",
        password="secret",
    )
    assert client.host == "smtp.example.com"
    assert client.port == 587


def test_slack_severity_colors():
    client = SlackClient(webhook_url="test")
    assert client._severity_color("info") == "#36a64f"
    assert client._severity_color("warning") == "#ff9900"
    assert client._severity_color("error") == "#ff0000"
    assert client._severity_color("critical") == "#990000"
    assert client._severity_color("unknown") == "#808080"
