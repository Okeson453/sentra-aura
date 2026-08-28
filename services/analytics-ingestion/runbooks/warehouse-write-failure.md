# Warehouse Write Failure

## Symptoms

Analytics ingestion service reports write errors. Metrics dashboard shows stale data.

## Impact

Delayed performance insights, stale optimization signals, incorrect experiment results.

## Detection

Alert: `warehouse_write_error_rate > 1%` or `data_freshness > 2h`.

## Mitigation

1. Check ClickHouse/BigQuery connectivity and credentials. 2. If transient network issue, retry with exponential backoff. 3. If schema mismatch, halt ingestion and alert data engineering.

## Recovery

Replay failed batches from dead-letter queue. Verify data completeness with row-count checks.

## Post-Incident

Review ingestion pipeline resilience. Consider adding intermediate buffer (Redis stream) before warehouse.
