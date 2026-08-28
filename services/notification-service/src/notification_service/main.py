"""FastAPI application for the Notification Service."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from notification_service.channels.email import EmailClient
from notification_service.channels.pagerduty import PagerDutyClient
from notification_service.channels.slack import SlackClient
from notification_service.config import config
from notification_service.routing.escalation_policy import EscalationPolicy
from notification_service.routing.severity_router import Alert, Channel, Severity, SeverityRouter

logger = logging.getLogger(__name__)

severity_router = SeverityRouter(
    dedup_window_seconds=config.dedup_window_seconds,
    rate_limit_per_minute=config.rate_limit_per_minute,
)
escalation_policy = EscalationPolicy()

slack_client = SlackClient(webhook_url=config.slack_webhook_url) if config.slack_webhook_url else None
pagerduty_client = PagerDutyClient(routing_key=config.pagerduty_service_key) if config.pagerduty_service_key else None
email_client = EmailClient(
    host=config.smtp_host,
    port=config.smtp_port,
    username=config.smtp_user,
    password=config.smtp_password,
) if config.smtp_user else None


async def _dispatch_alert(alert: Alert, channels: list[Channel]) -> dict[str, Any]:
    """Dispatch an alert to the specified channels."""
    results = {}
    for channel in channels:
        try:
            if channel == Channel.SLACK and slack_client:
                result = await slack_client.send_alert(
                    alert_id=alert.alert_id,
                    severity=alert.severity.value,
                    title=alert.title,
                    message=alert.message,
                    source_service=alert.source_service,
                    channel_id=alert.channel_id,
                    metadata=alert.metadata,
                )
                results["slack"] = result
            elif channel == Channel.PAGERDUTY and pagerduty_client:
                result = await pagerduty_client.trigger_incident(
                    alert_id=alert.alert_id,
                    title=alert.title,
                    message=alert.message,
                    severity=alert.severity.value,
                    source_service=alert.source_service,
                    metadata=alert.metadata,
                )
                results["pagerduty"] = result
            elif channel == Channel.EMAIL and email_client:
                # In production, recipient list would come from a config/registry
                recipients = ["ops@sentraaura.com"]
                result = await email_client.send_alert(
                    alert_id=alert.alert_id,
                    severity=alert.severity.value,
                    title=alert.title,
                    message=alert.message,
                    recipients=recipients,
                    source_service=alert.source_service,
                    metadata=alert.metadata,
                )
                results["email"] = result
        except Exception as exc:
            logger.error("Failed to dispatch to %s: %s", channel.value, exc)
            results[channel.value] = {"sent": False, "error": str(exc)}
    return results


escalation_policy.set_dispatch_callback(
    lambda alert, channels: asyncio.create_task(_dispatch_alert(alert, channels))
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    escalation_task = asyncio.create_task(escalation_policy.run_escalation_loop())
    logger.info("Notification Service started")
    yield
    escalation_task.cancel()
    try:
        await escalation_task
    except asyncio.CancelledError:
        pass
    if slack_client:
        await slack_client.close()
    if pagerduty_client:
        await pagerduty_client.close()
    logger.info("Notification Service stopped")


app = FastAPI(
    title="Notification Service",
    version="1.0.0",
    description="Routes alerts and operational notifications to the correct channel.",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "healthy", "service": config.service_name}


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    return {"status": "ready", "service": config.service_name}


@app.post("/api/v1/alerts")
async def send_alert(alert: Alert) -> dict[str, Any]:
    """Receive and route an alert."""
    channels = severity_router.route(alert)
    if not channels:
        return {"alert_id": alert.alert_id, "routed": False, "reason": "deduplicated_or_rate_limited"}

    results = await _dispatch_alert(alert, channels)
    escalation_policy.handle_alert(alert)

    return {
        "alert_id": alert.alert_id,
        "routed": True,
        "channels": [c.value for c in channels],
        "results": results,
    }


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str) -> dict[str, Any]:
    """Acknowledge an alert, cancelling escalation."""
    success = escalation_policy.acknowledge(alert_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")
    return {"alert_id": alert_id, "acknowledged": True}


@app.get("/api/v1/routing")
async def get_routing_table() -> dict[str, list[str]]:
    """Get current severity-to-channel routing table."""
    return {
        sev.value: [c.value for c in chans]
        for sev, chans in severity_router.routing_table.items()
    }


@app.patch("/api/v1/routing/{severity}")
async def update_routing(severity: Severity, channels: list[Channel]) -> dict[str, Any]:
    """Override routing for a severity level."""
    severity_router.override_routing(severity, channels)
    return {"severity": severity.value, "channels": [c.value for c in channels], "updated": True}


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": "VALIDATION_ERROR", "message": str(exc)},
    )
