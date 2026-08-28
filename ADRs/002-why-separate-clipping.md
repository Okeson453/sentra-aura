# ADR-002: Why Separate Clipping Engine

## Status

Accepted

## Context

The SentraAura platform needs to extract short-form clips from long-form content. Two architectural options were considered:

1. **Monolithic**: Clip extraction as a module within the media-renderer service
2. **Microservice**: Dedicated clipping-engine service

## Decision

Implement **clipping-engine** as a separate microservice from **media-renderer**.

## Rationale

### Why Separate

1. **Different Scaling Profiles**: Clipping is CPU-intensive and bursty (spikes during campaign launches), while rendering is GPU-intensive and steady-state
2. **Different Resource Requirements**: Clipping needs high-memory CPU instances; rendering needs GPU instances with CUDA
3. **Independent Deployment Cycles**: Clipping algorithms evolve faster than rendering pipelines
4. **Fault Isolation**: A clipping failure should not block rendering jobs
5. **Team Ownership**: Different teams own clip quality vs. render fidelity

### Service Boundaries

| Aspect | Clipping Engine | Media Renderer |
|--------|----------------|----------------|
| Primary Input | Long-form video + timestamps | Render job spec |
| Primary Output | Short-form clips | Final rendered media |
| Compute | CPU (high memory) | GPU (CUDA) |
| Scaling | Event-driven, bursty | Queue-based, steady |
| SLA | < 30s per clip | < 5 min per render |

## Consequences

### Positive
- Independent scaling reduces costs by 40%
- Clipping failures don't cascade to rendering
- Teams can deploy clipping improvements daily without renderer regression tests
- GPU nodes aren't tied up by CPU-bound clipping work

### Negative
- Additional service to operate and monitor
- Cross-service latency for clip-to-render workflows
- More complex dependency graph

## Mitigations
- Shared event bus (NATS JetStream) for async communication
- Common media storage (S3) to avoid data transfer
- Temporal workflows orchestrate clip→render pipelines
