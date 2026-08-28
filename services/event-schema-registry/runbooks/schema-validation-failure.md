# Schema Validation Failure

## Symptoms

Events are being rejected by the schema registry at high rate. Downstream consumers report missing events.

## Impact

Event bus backpressure, delayed workflow execution, potential data loss if producers do not retry.

## Detection

Alert: `schema_validation_rejection_rate > 5%` for 2 minutes. Check `/metrics` endpoint.

## Mitigation

1. Identify the offending producer via `X-Producer-ID` header in rejected events. 2. Check if schema was recently updated in `contracts/events/`. 3. If breaking change was unintentional, rollback schema version. 4. If intentional, coordinate producer upgrade.

## Recovery

Restart registry pods to clear any cached stale schemas. Verify validation rate returns to baseline.

## Post-Incident

Review schema change process. Ensure additive-only compatibility checks run in CI before merge.
