"""Unit tests for billing invoicing engine."""
from __future__ import annotations

from datetime import datetime, timedelta

from billing_service.invoicing import InvoicingEngine, InvoiceLineItem


def test_generate_invoice():
    engine = InvoicingEngine()
    usage = {
        "operations": {
            "llm_input_token": {"units": 10000, "cost_usd": 0.10},
            "llm_output_token": {"units": 5000, "cost_usd": 0.15},
        }
    }
    start = datetime.utcnow() - timedelta(days=30)
    end = datetime.utcnow()
    invoice = engine.generate_invoice("tenant-1", start, end, usage)
    assert invoice.tenant_id == "tenant-1"
    assert invoice.status == "draft"
    assert invoice.total_usd > 0
    assert len(invoice.line_items) == 2


def test_invoice_with_tax():
    engine = InvoicingEngine()
    engine.set_tax_rate("tenant-1", 0.20)
    usage = {
        "operations": {
            "api_call": {"units": 1000, "cost_usd": 1.00},
        }
    }
    invoice = engine.generate_invoice("tenant-1", datetime.utcnow(), datetime.utcnow(), usage)
    assert invoice.tax_rate == 0.20
    assert invoice.tax_amount_usd == pytest.approx(0.20, abs=0.01)
    assert invoice.total_usd == pytest.approx(1.20, abs=0.01)


def test_mark_paid():
    engine = InvoicingEngine()
    usage = {"operations": {}}
    invoice = engine.generate_invoice("tenant-1", datetime.utcnow(), datetime.utcnow(), usage)
    paid = engine.mark_paid(invoice.invoice_id)
    assert paid.status == "paid"
    assert paid.paid_at is not None


def test_get_invoice_not_found():
    engine = InvoicingEngine()
    assert engine.get_invoice("nonexistent") is None


def test_list_invoices():
    engine = InvoicingEngine()
    usage = {"operations": {}}
    engine.generate_invoice("tenant-1", datetime.utcnow(), datetime.utcnow(), usage)
    engine.generate_invoice("tenant-1", datetime.utcnow(), datetime.utcnow(), usage)
    engine.generate_invoice("tenant-2", datetime.utcnow(), datetime.utcnow(), usage)

    tenant1 = engine.list_invoices("tenant-1")
    assert len(tenant1) == 2


import pytest
