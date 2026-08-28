"""Invoice generation, tax calculation, payment status tracking, and dunning management."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InvoiceLineItem:
    """A single line item on an invoice."""

    description: str
    quantity: float
    unit_price_usd: float
    amount_usd: float
    service_name: str = ""
    operation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Invoice:
    """A complete invoice record."""

    invoice_id: str
    tenant_id: str
    period_start: datetime
    period_end: datetime
    line_items: list[InvoiceLineItem]
    subtotal_usd: float
    tax_rate: float
    tax_amount_usd: float
    total_usd: float
    currency: str
    status: str  # draft, sent, paid, overdue, cancelled, disputed
    due_date: datetime
    created_at: datetime
    sent_at: datetime | None = None
    paid_at: datetime | None = None
    payment_method: str | None = None
    stripe_invoice_id: str | None = None
    notes: str = ""


@dataclass
class PaymentRecord:
    """A payment transaction record."""

    payment_id: str
    invoice_id: str
    tenant_id: str
    amount_usd: float
    currency: str
    payment_method: str
    status: str  # pending, completed, failed, refunded
    transaction_reference: str | None = None
    processed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class InvoicingEngine:
    """Production-grade invoicing engine for SaaS billing.

    Features:
    - Invoice generation from metered usage
    - Tax calculation with configurable rates
    - Payment status tracking
    - Overdue detection
    - Dunning management
    - Stripe integration hooks
    - Credit note support
    """

    def __init__(
        self,
        currency: str = "USD",
        invoice_due_days: int = 30,
        default_tax_rate: float = 0.0,
    ) -> None:
        self.currency = currency
        self.invoice_due_days = invoice_due_days
        self.default_tax_rate = default_tax_rate
        self._invoices: dict[str, Invoice] = {}
        self._payments: dict[str, PaymentRecord] = {}
        self._tax_rates: dict[str, float] = {}  # tenant_id -> tax_rate
        self._credit_notes: dict[str, list[dict[str, Any]]] = {}  # tenant_id -> credits

    def set_tax_rate(self, tenant_id: str, rate: float) -> None:
        """Set the tax rate for a specific tenant."""
        self._tax_rates[tenant_id] = rate
        logger.info("Set tax rate for tenant %s: %.2f%%", tenant_id, rate * 100)

    def set_tenant_credit(self, tenant_id: str, amount_usd: float, reason: str) -> None:
        """Apply a credit note to a tenant's account."""
        credit = {
            "amount_usd": amount_usd,
            "reason": reason,
            "created_at": datetime.utcnow().isoformat(),
            "credit_id": f"CR-{uuid.uuid4().hex[:8].upper()}",
        }
        self._credit_notes.setdefault(tenant_id, []).append(credit)
        logger.info("Applied $%.2f credit to tenant %s: %s", amount_usd, tenant_id, reason)

    def generate_invoice(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        usage_summary: dict[str, Any],
        notes: str = "",
    ) -> Invoice:
        """Generate an invoice from aggregated usage data.

        Args:
            tenant_id: The tenant to invoice
            period_start: Start of the billing period
            period_end: End of the billing period
            usage_summary: Output from MeteringEngine.aggregate_by_tenant()
            notes: Optional notes to include on the invoice

        Returns:
            The generated Invoice object
        """
        invoice_id = f"INV-{uuid.uuid4().hex[:12].upper()}"
        line_items: list[InvoiceLineItem] = []
        subtotal = 0.0

        operations = usage_summary.get("operations", {})
        for op, data in operations.items():
            units = data.get("units", 0.0)
            cost = data.get("cost_usd", 0.0)
            unit_price = cost / max(units, 1)

            item = InvoiceLineItem(
                description=f"{op} usage",
                quantity=round(units, 4),
                unit_price_usd=round(unit_price, 6),
                amount_usd=round(cost, 4),
                operation=op,
                metadata={"record_count": data.get("count", 0)},
            )
            line_items.append(item)
            subtotal += cost

        # Apply credits
        credits = self._credit_notes.get(tenant_id, [])
        total_credits = sum(c["amount_usd"] for c in credits)
        if total_credits > 0:
            credit_item = InvoiceLineItem(
                description=f"Account credit",
                quantity=1,
                unit_price_usd=-total_credits,
                amount_usd=-total_credits,
                metadata={"credits": credits},
            )
            line_items.append(credit_item)
            subtotal -= total_credits
            # Clear applied credits
            self._credit_notes[tenant_id] = []

        tax_rate = self._tax_rates.get(tenant_id, self.default_tax_rate)
        taxable_amount = max(0.0, subtotal)
        tax_amount = taxable_amount * tax_rate
        total = taxable_amount + tax_amount

        invoice = Invoice(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            line_items=line_items,
            subtotal_usd=round(subtotal, 2),
            tax_rate=tax_rate,
            tax_amount_usd=round(tax_amount, 2),
            total_usd=round(total, 2),
            currency=self.currency,
            status="draft",
            due_date=datetime.utcnow() + timedelta(days=self.invoice_due_days),
            created_at=datetime.utcnow(),
            notes=notes,
        )
        self._invoices[invoice_id] = invoice
        logger.info(
            "Generated invoice %s for tenant %s: subtotal=$%.2f, tax=$%.2f, total=$%.2f",
            invoice_id,
            tenant_id,
            subtotal,
            tax_amount,
            total,
        )
        return invoice

    def mark_sent(self, invoice_id: str, sent_at: datetime | None = None) -> Invoice:
        """Mark an invoice as sent to the customer."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status not in ("draft", "sent"):
            raise ValueError(f"Cannot mark invoice {invoice_id} as sent (status: {inv.status})")
        inv.status = "sent"
        inv.sent_at = sent_at or datetime.utcnow()
        logger.info("Invoice %s marked as sent", invoice_id)
        return inv

    def mark_paid(
        self,
        invoice_id: str,
        paid_at: datetime | None = None,
        payment_method: str | None = None,
        stripe_invoice_id: str | None = None,
    ) -> Invoice:
        """Mark an invoice as paid."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status == "paid":
            raise ValueError(f"Invoice {invoice_id} is already paid")
        inv.status = "paid"
        inv.paid_at = paid_at or datetime.utcnow()
        inv.payment_method = payment_method
        inv.stripe_invoice_id = stripe_invoice_id
        logger.info("Invoice %s marked as paid via %s", invoice_id, payment_method or "unknown")
        return inv

    def mark_overdue(self, invoice_id: str) -> Invoice:
        """Mark an invoice as overdue."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status not in ("sent", "overdue"):
            raise ValueError(f"Cannot mark invoice {invoice_id} as overdue (status: {inv.status})")
        inv.status = "overdue"
        logger.warning("Invoice %s marked as overdue", invoice_id)
        return inv

    def cancel_invoice(self, invoice_id: str, reason: str = "") -> Invoice:
        """Cancel an invoice."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status == "paid":
            raise ValueError(f"Cannot cancel paid invoice {invoice_id}")
        inv.status = "cancelled"
        logger.info("Invoice %s cancelled: %s", invoice_id, reason)
        return inv

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        """Retrieve an invoice by ID."""
        return self._invoices.get(invoice_id)

    def list_invoices(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
    ) -> list[Invoice]:
        """List invoices with optional filtering."""
        invoices = list(self._invoices.values())
        if tenant_id:
            invoices = [inv for inv in invoices if inv.tenant_id == tenant_id]
        if status:
            invoices = [inv for inv in invoices if inv.status == status]
        if since:
            invoices = [inv for inv in invoices if inv.created_at >= since]
        return sorted(invoices, key=lambda i: i.created_at, reverse=True)

    def get_overdue_invoices(self, as_of: datetime | None = None) -> list[Invoice]:
        """Get all invoices that are past their due date."""
        now = as_of or datetime.utcnow()
        return [
            inv for inv in self._invoices.values()
            if inv.status in ("sent", "overdue") and inv.due_date < now
        ]

    def record_payment(
        self,
        invoice_id: str,
        amount_usd: float,
        payment_method: str,
        transaction_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PaymentRecord:
        """Record a payment against an invoice."""
        inv = self._invoices.get(invoice_id)
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")

        payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        payment = PaymentRecord(
            payment_id=payment_id,
            invoice_id=invoice_id,
            tenant_id=inv.tenant_id,
            amount_usd=amount_usd,
            currency=inv.currency,
            payment_method=payment_method,
            status="completed",
            transaction_reference=transaction_reference,
            processed_at=datetime.utcnow(),
            metadata=metadata or {},
        )
        self._payments[payment_id] = payment

        # Auto-mark invoice as paid if payment covers total
        if amount_usd >= inv.total_usd:
            self.mark_paid(invoice_id, payment_method=payment_method)

        logger.info(
            "Recorded payment %s for invoice %s: $%.2f via %s",
            payment_id,
            invoice_id,
            amount_usd,
            payment_method,
        )
        return payment
