# Metering Discrepancy

## Symptoms

Invoiced amount does not match internal cost tracking. Customer dispute.

## Impact

Revenue leakage, customer churn, audit failure.

## Detection

Alert: `billing_reconciliation_variance > 1%` between metering and provider invoices.

## Mitigation

1. Identify the time window and service causing discrepancy. 2. Cross-reference with provider-gateway cost logs. 3. If rounding error, apply correction in next invoice. 4. If missing events, backfill from event bus.

## Recovery

Issue corrected invoice or credit note. Update customer balance.

## Post-Incident

Improve metering idempotency. Add daily reconciliation job with provider bills.
