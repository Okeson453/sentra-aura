# asset-store — Incident Response Runbook

## Service Overview

- **Service**: asset-store
- **Version**: 0.1.0
- **Owner**: SentraAura Platform Team
- **SLA**: 99.9% uptime
- **Criticality**: High — all media assets stored and retrieved through this service

## Architecture

This service is part of the SentraAura Control & State Layer (Batch 2).
It runs as a containerized FastAPI service with the following dependencies:

- S3 / Azure Blob / GCS (object storage)
- PostgreSQL (asset metadata)
- Redis (presigned URL cache)

## Health Checks

- **Liveness**: `GET /health`
- **Readiness**: `GET /ready`
- **Metrics**: `GET /metrics` (Prometheus)

## Common Incidents

### Incident: Database Connection Pool Exhausted

**Symptoms**: 503 errors, `/ready` returns degraded, high latency.

**Diagnosis**:
```bash
kubectl logs -f deployment/asset-store --tail=100
# Look for: "QueuePool limit of size X overflow Y reached"
```

**Resolution**:
1. Check active connections: `SELECT count(*) FROM pg_stat_activity;`
2. Identify long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active';`
3. Kill blocking queries if safe
4. Scale DB connection pool: increase `DATABASE_POOL_SIZE`
5. If persistent, scale service replicas horizontally

### Incident: Service Memory Leak

**Symptoms**: Memory usage climbing steadily, OOMKilled pods.

**Diagnosis**:
```bash
kubectl top pods -l app=asset-store
```

**Resolution**:
1. Enable memory profiling
2. Check for unclosed DB sessions or file handles
3. Restart pods with rolling update
4. Review recent deployments for code changes

### Incident: Downstream Service Unavailable

**Symptoms**: Circuit breaker tripped, degraded health checks.

**Resolution**:
1. Check downstream service health
2. Verify network connectivity
3. Review circuit breaker logs
4. If downstream is critical, enable fallback mode
5. Escalate to downstream service owner

### Incident: High Error Rate

**Symptoms**: 5xx errors spiking, alert firing.

**Resolution**:
1. Check error logs for root cause
2. Identify if error is DB, cache, or downstream related
3. Rollback recent deployment if correlated
4. Enable debug logging temporarily
5. If data corruption suspected, engage DBA

## Escalation

1. **L1**: On-call engineer — initial triage (15 min)
2. **L2**: Service owner — deep investigation (1 hour)
3. **L3**: Platform architect — architecture-level fix (4 hours)
4. **L4**: VP Engineering — business continuity decision

## Post-Incident

- Update this runbook with new findings
- Create follow-up tickets for preventive measures
- Schedule blameless post-mortem within 48 hours
