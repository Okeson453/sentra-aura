# ADR-004: Why Four Platform Services (NATS, cert-manager, Prometheus, Default Deny)

## Status

Accepted

## Context

SentraAura's Kubernetes platform requires shared infrastructure services. We needed to decide which services to include in the base platform layer versus application-specific deployments.

## Decision

Standardize on **four platform services** as the base layer:

1. **NATS JetStream** — Event bus and message queue
2. **cert-manager** — TLS certificate management
3. **Prometheus + Grafana + Loki** — Observability stack
4. **Default Deny Network Policies** — Zero-trust network security

## Rationale

### Why These Four

1. **NATS JetStream**
   - Unified event bus for all async communication
   - Replaces need for separate Kafka, RabbitMQ, or SQS
   - JetStream provides persistence for critical events
   - Lightweight enough for local development

2. **cert-manager**
   - Automated TLS certificate lifecycle
   - Let's Encrypt integration for free certificates
   - Certificate rotation without service restarts
   - Required for all HTTPS ingress

3. **Prometheus + Grafana + Loki**
   - Metrics, dashboards, and logs in one stack
   - Native Kubernetes integration
   - Industry standard, rich ecosystem
   - Cost-effective compared to SaaS alternatives

4. **Default Deny Network Policies**
   - Zero-trust by default
   - Explicit allow rules only
   - Defense in depth against lateral movement
   - Required for compliance (SOC 2, ISO 27001)

### Why Not Others

| Service | Reason for Exclusion |
|---------|---------------------|
| Istio/Linkerd | Service mesh adds complexity; not needed at current scale |
| Vault | AWS Secrets Manager sufficient; avoid self-managed secrets |
| Consul | Kubernetes DNS and etcd sufficient for service discovery |
| Fluentd | Loki + Promtail handles log aggregation natively |
| Jaeger | OpenTelemetry + Prometheus sufficient for tracing MVP |

## Consequences

### Positive
- Minimal platform footprint reduces operational overhead
- Consistent observability across all environments
- Strong security posture by default
- Easy to replicate across dev/staging/prod

### Negative
- No service mesh means manual mTLS between services
- No distributed tracing in MVP (planned for Phase 2)
- NATS single point of failure (mitigated by 3-node cluster)

## Future Evolution

- Phase 2: Add Jaeger/Tempo for distributed tracing
- Phase 2: Evaluate Istio for mTLS and advanced traffic management
- Phase 3: Consider Vault for advanced secret management
