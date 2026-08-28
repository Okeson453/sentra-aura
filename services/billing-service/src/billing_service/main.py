"""FastAPI application for the Billing Service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from billing_service.config import config
from billing_service.invoicing import InvoicingEngine, Invoice
from billing_service.metering import MeteringEngine, MeterRecord

logger = logging.getLogger(__name__)

metering = MeteringEngine()
invoicing = InvoicingEngine(currency=config.invoice_currency, invoice_due_days=config.invoice_due_days)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Billing Service started")
    yield
    logger.info("Billing Service stopped")


app = FastAPI(
    title="Billing Service",
    version="1.0.0",
    description="SaaS-mode billing: metering, invoicing, and cost attribution.",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "healthy", "service": config.service_name}


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    return {"status": "ready", "service": config.service_name}


@app.post("/api/v1/meter")
async def record_usage(
    tenant_id: str = Query(...),
    channel_id: str = Query(...),
    service_name: str = Query(...),
    operation: str = Query(...),
    units: float = Query(...),
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a usage event for billing."""
    record = metering.record_usage(tenant_id, channel_id, service_name, operation, units, metadata)
    return {
        "recorded": True,
        "tenant_id": record.tenant_id,
        "operation": record.operation,
        "units": record.units,
        "cost_usd": record.total_cost_usd,
        "timestamp": record.timestamp.isoformat(),
    }


@app.get("/api/v1/meter/tenant/{tenant_id}")
async def get_tenant_usage(
    tenant_id: str,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Get aggregated usage for a tenant."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    return metering.aggregate_by_tenant(tenant_id, start, end)


@app.get("/api/v1/meter/channel/{channel_id}")
async def get_channel_usage(
    channel_id: str,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Get aggregated usage for a channel."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    return metering.aggregate_by_channel(channel_id, start, end)


@app.post("/api/v1/invoices")
async def create_invoice(
    tenant_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Generate an invoice for a tenant."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    usage = metering.aggregate_by_tenant(tenant_id, start, end)
    invoice = invoicing.generate_invoice(tenant_id, start, end, usage)
    return {
        "invoice_id": invoice.invoice_id,
        "tenant_id": invoice.tenant_id,
        "total_usd": invoice.total_usd,
        "status": invoice.status,
        "due_date": invoice.due_date.isoformat(),
        "line_items": [
            {
                "description": li.description,
                "quantity": li.quantity,
                "unit_price_usd": li.unit_price_usd,
                "amount_usd": li.amount_usd,
            }
            for li in invoice.line_items
        ],
    }


@app.get("/api/v1/invoices/{invoice_id}")
async def get_invoice(invoice_id: str) -> dict[str, Any]:
    """Retrieve an invoice by ID."""
    inv = invoicing.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")
    return {
        "invoice_id": inv.invoice_id,
        "tenant_id": inv.tenant_id,
        "total_usd": inv.total_usd,
        "status": inv.status,
        "due_date": inv.due_date.isoformat(),
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
    }


@app.post("/api/v1/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: str) -> dict[str, Any]:
    """Mark an invoice as paid."""
    try:
        inv = invoicing.mark_paid(invoice_id)
        return {"invoice_id": inv.invoice_id, "status": inv.status, "paid_at": inv.paid_at.isoformat()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.post("/api/v1/invoices/{invoice_id}/send")
async def send_invoice(invoice_id: str) -> dict[str, Any]:
    """Mark an invoice as sent to the customer."""
    try:
        inv = invoicing.mark_sent(invoice_id)
        return {"invoice_id": inv.invoice_id, "status": inv.status, "sent_at": inv.sent_at.isoformat()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/api/v1/invoices/{invoice_id}/cancel")
async def cancel_invoice(invoice_id: str, reason: str = Query(default="")) -> dict[str, Any]:
    """Cancel an invoice."""
    try:
        inv = invoicing.cancel_invoice(invoice_id, reason)
        return {"invoice_id": inv.invoice_id, "status": inv.status, "cancelled": True}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/api/v1/invoices/{invoice_id}/overdue")
async def mark_invoice_overdue(invoice_id: str) -> dict[str, Any]:
    """Mark an invoice as overdue."""
    try:
        inv = invoicing.mark_overdue(invoice_id)
        return {"invoice_id": inv.invoice_id, "status": inv.status, "overdue": True}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/api/v1/invoices/{invoice_id}/payments")
async def record_payment(
    invoice_id: str,
    amount_usd: float = Query(..., gt=0),
    payment_method: str = Query(...),
    transaction_reference: str | None = Query(default=None),
) -> dict[str, Any]:
    """Record a payment against an invoice."""
    try:
        payment = invoicing.record_payment(invoice_id, amount_usd, payment_method, transaction_reference)
        return {
            "payment_id": payment.payment_id,
            "invoice_id": payment.invoice_id,
            "amount_usd": payment.amount_usd,
            "status": payment.status,
            "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get("/api/v1/invoices/overdue")
async def list_overdue_invoices(
    tenant_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """List all overdue invoices."""
    invoices = invoicing.get_overdue_invoices()
    if tenant_id:
        invoices = [inv for inv in invoices if inv.tenant_id == tenant_id]
    return [
        {
            "invoice_id": inv.invoice_id,
            "tenant_id": inv.tenant_id,
            "total_usd": inv.total_usd,
            "due_date": inv.due_date.isoformat(),
            "days_overdue": max(0, (datetime.utcnow() - inv.due_date).days),
        }
        for inv in invoices
    ]


@app.post("/api/v1/tenants/{tenant_id}/credits")
async def apply_credit(
    tenant_id: str,
    amount_usd: float = Query(..., gt=0),
    reason: str = Query(default=""),
) -> dict[str, Any]:
    """Apply a credit note to a tenant's account."""
    invoicing.set_tenant_credit(tenant_id, amount_usd, reason)
    return {"tenant_id": tenant_id, "credit_applied_usd": amount_usd, "reason": reason}


@app.post("/api/v1/tenants/{tenant_id}/tax-rate")
async def set_tax_rate(
    tenant_id: str,
    rate: float = Query(..., ge=0, le=1),
) -> dict[str, Any]:
    """Set the tax rate for a specific tenant."""
    invoicing.set_tax_rate(tenant_id, rate)
    return {"tenant_id": tenant_id, "tax_rate": rate}


@app.post("/api/v1/tenants/{tenant_id}/budget")
async def set_budget(
    tenant_id: str,
    budget_usd: float = Query(..., gt=0),
    thresholds: list[float] = Query(default=[0.5, 0.8, 0.95]),
) -> dict[str, Any]:
    """Set a monthly budget limit for a tenant."""
    metering.set_tenant_budget(tenant_id, budget_usd)
    return {"tenant_id": tenant_id, "budget_usd": budget_usd, "thresholds": thresholds}


@app.get("/api/v1/alerts/budget")
async def get_budget_alerts(
    tenant_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Get budget threshold alerts."""
    since = datetime.utcnow() - timedelta(days=days)
    alerts = metering.get_budget_alerts(tenant_id, since)
    return [
        {
            "tenant_id": a.tenant_id,
            "threshold_percent": a.threshold_percent,
            "current_spend": a.current_spend,
            "budget_limit": a.budget_limit,
            "alert_type": a.alert_type,
            "timestamp": a.timestamp.isoformat(),
        }
        for a in alerts
    ]


@app.post("/api/v1/webhooks/stripe")
async def stripe_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle Stripe webhook events for invoice payments.

    Expected events:
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    event_type = payload.get("type", "")
    data = payload.get("data", {}).get("object", {})

    if event_type == "invoice.payment_succeeded":
        stripe_invoice_id = data.get("id", "")
        # Find invoice by stripe_invoice_id
        for inv in invoicing.list_invoices():
            if inv.stripe_invoice_id == stripe_invoice_id:
                invoicing.mark_paid(
                    inv.invoice_id,
                    payment_method="stripe",
                    stripe_invoice_id=stripe_invoice_id,
                )
                logger.info("Stripe payment succeeded for invoice %s", inv.invoice_id)
                return {"handled": True, "event": event_type, "invoice_id": inv.invoice_id}
        logger.warning("Stripe payment succeeded but no matching invoice: %s", stripe_invoice_id)
        return {"handled": False, "event": event_type, "reason": "invoice_not_found"}

    if event_type == "invoice.payment_failed":
        stripe_invoice_id = data.get("id", "")
        for inv in invoicing.list_invoices():
            if inv.stripe_invoice_id == stripe_invoice_id:
                logger.warning("Stripe payment failed for invoice %s", inv.invoice_id)
                return {"handled": True, "event": event_type, "invoice_id": inv.invoice_id}
        return {"handled": False, "event": event_type, "reason": "invoice_not_found"}

    return {"handled": False, "event": event_type, "reason": "unhandled_event_type"}


@app.get("/api/v1/invoices/tenant/{tenant_id}")
async def list_invoices(tenant_id: str) -> list[dict[str, Any]]:
    """List all invoices for a tenant."""
    invoices = invoicing.list_invoices(tenant_id)
    return [
        {
            "invoice_id": inv.invoice_id,
            "total_usd": inv.total_usd,
            "status": inv.status,
            "due_date": inv.due_date.isoformat(),
        }
        for inv in invoices
    ]


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": "VALIDATION_ERROR", "message": str(exc)},
    )
