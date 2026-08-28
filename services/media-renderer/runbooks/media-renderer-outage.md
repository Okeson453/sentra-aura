# Media Renderer Runbook

## Service Overview

The Media Renderer is part of the SentraAura Batch 4 delivery.

## Common Issues

### Service Unhealthy

1. Check logs: `kubectl logs -f deployment/media-renderer`
2. Verify database connectivity
3. Check resource limits

### High Latency

1. Check CPU/memory usage
2. Verify no lock contention on _store
3. Scale horizontally if needed

## Escalation

- P1: Page on-call engineer
- P2: Create incident ticket
- P3: Log for next sprint
