# ADR-001: Why Go for Core Services

## Status

Accepted

## Context

SentraAura requires a systems programming language for core infrastructure services (orchestrator, data-ingestion-pipeline, content-graph-service) that provides:

- Strong concurrency primitives for high-throughput event processing
- Static typing for reliability at scale
- Efficient memory usage for cost-controlled cloud deployment
- Fast compilation for rapid iteration
- Strong ecosystem for cloud-native tooling

## Decision

Use **Go** for core backend services.

## Rationale

### Go Strengths

1. **Goroutines & Channels**: Native concurrency model perfectly suited for event-driven architectures and pipeline processing
2. **Fast Compilation**: Sub-second builds enable rapid development cycles
3. **Static Binary**: Single binary deployment simplifies containerization and reduces attack surface
4. **Memory Efficiency**: Garbage collected with low pause times, efficient for long-running services
5. **Standard Library**: Robust HTTP/2, gRPC, and JSON support without external dependencies
6. **Cloud-Native Ecosystem**: First-class Kubernetes client libraries, Prometheus metrics, OpenTelemetry

### Alternatives Considered

| Language | Pros | Cons | Verdict |
|----------|------|------|---------|
| Rust | Memory safety, performance | Steep learning curve, slower compile times | Rejected for team velocity |
| Java | Mature ecosystem, hiring pool | Heavy runtime, slower startup | Rejected for container efficiency |
| Python | Rapid prototyping, ML ecosystem | GIL limits concurrency, slower runtime | Used for AI/ML services only |
| Node.js | Async I/O, JS ecosystem | Single-threaded, callback complexity | Rejected for system services |

## Consequences

### Positive
- Consistent concurrency model across services
- Fast CI/CD pipelines
- Small container images
- Easy to hire for Go expertise

### Negative
- Less expressive type system than Rust
- Manual error handling can be verbose
- Smaller ML/AI library ecosystem (mitigated by using Python for AI services)

## Related Decisions
- ADR-002: Python for AI/ML services
- ADR-003: Temporal for workflow orchestration
