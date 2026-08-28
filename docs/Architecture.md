# SentraAura — Architecture Documentation

## Overview

SentraAura is an enterprise-grade Autonomous AI Media Operating System. It orchestrates specialized AI agents, durable workflows, and multi-channel content operations through a unified control plane.

## System Architecture

```
+------------------------------------------------------------------+
|                        Carbon Slate UI                           |
|  (Configure | Observe | Inspect | Override | Analyze)            |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                    Control Plane API (Go)                        |
|  - REST + GraphQL endpoints                                      |
|  - Tenant isolation                                              |
|  - Rate limiting via Quota Broker                                |
|  - Authentication & Authorization                                |
+------------------------------------------------------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
+----------------+  +----------------+  +----------------+
|   Orchestrator |  |  Policy Engine |  |  Event Schema  |
|   (Temporal)   |  |  (L0-L4 Rules) |  |   Registry     |
+----------------+  +----------------+  +----------------+
          |                   |                   |
          v                   v                   v
+------------------------------------------------------------------+
|                        Agent Runtime                             |
|  (Research | Script | Render | Score | Publish | Compliance)     |
+------------------------------------------------------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
+----------------+  +----------------+  +----------------+
| Media Renderer |  | Clipping Engine|  | Provider Gateway|
|   (GPU nodes)  |  |  (CPU nodes)   |  | (OpenAI, etc.) |
+----------------+  +----------------+  +----------------+
                              |
                              v
+------------------------------------------------------------------+
|                    Content Asset Graph                           |
|  (Neo4j / PostgreSQL — Channels, Topics, Assets, Relationships)  |
+------------------------------------------------------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
+----------------+  +----------------+  +----------------+
|  Data Ingestion|  | Analytics      |  |   Publishing   |
|   Pipeline     |  |  Ingestion     |  |    Service     |
+----------------+  +----------------+  +----------------+
```

## Core Services

### Control Plane API
- **Language**: Go
- **Responsibility**: External API gateway, tenant management, request routing
- **Endpoints**: REST + GraphQL
- **Scaling**: Horizontal, CPU-bound

### Orchestrator
- **Language**: Go
- **Responsibility**: Temporal workflow engine integration, job scheduling
- **Scaling**: Horizontal, memory-bound

### Agent Runtime
- **Language**: Python
- **Responsibility**: AI agent execution, prompt management, tool orchestration
- **Scaling**: Horizontal with GPU support

### Policy Engine
- **Language**: Go
- **Responsibility**: L0-L4 autonomy enforcement, guardrails, compliance checks
- **Scaling**: Horizontal, CPU-bound

### Media Renderer
- **Language**: Python
- **Responsibility**: Video/audio rendering, format conversion
- **Scaling**: GPU nodes (g4dn/g5)

### Clipping Engine
- **Language**: Python
- **Responsibility**: Content segmentation, highlight extraction
- **Scaling**: CPU nodes (c6i)

## Data Layer

### Primary Database
- **Technology**: Aurora PostgreSQL
- **Purpose**: Relational data, user management, billing
- **Scaling**: Multi-AZ, read replicas

### Content Asset Graph
- **Technology**: Neo4j (or PostgreSQL with pg_graphql)
- **Purpose**: Channel-Topic-Asset relationships, content lineage
- **Scaling**: Read replicas, sharding by tenant

### Event Bus
- **Technology**: NATS JetStream
- **Purpose**: Async communication, event sourcing
- **Scaling**: 3-node cluster, persistent streams

### Cache
- **Technology**: ElastiCache Redis
- **Purpose**: Session storage, rate limiting, agent state
- **Scaling**: Cluster mode, multi-AZ

### Object Storage
- **Technology**: S3
- **Purpose**: Media assets, rendered output, archival
- **Organization**: Tenant-prefixed keys

## Security Architecture

### Authentication
- OAuth 2.0 / OIDC via external IdP
- JWT tokens with short expiry
- Refresh token rotation

### Authorization
- RBAC with domain-specific permissions
- Tenant isolation at database and storage layers
- Service-to-service mTLS (planned Phase 2)

### Data Protection
- Encryption at rest (KMS)
- Encryption in transit (TLS 1.3)
- Secret rotation via AWS Secrets Manager

### Network Security
- Default deny network policies
- VPC isolation
- Private subnets for databases and caches

## Deployment Architecture

### Environments
- **local**: Docker Compose for development
- **dev**: EKS with reduced instance sizes
- **staging**: Production-like sizing
- **canary**: Production mirror for progressive rollout
- **production**: Full redundancy, maximum protection

### CI/CD Pipeline
1. Lint & Type Check
2. Unit Tests (per service)
3. Contract Tests
4. Build, SBOM, Scan & Sign
5. Integration Tests
6. Workflow Tests
7. Media Quality Tests
8. Agent Evaluation
9. Security Scan

### Progressive Rollout
1. Deploy to canary
2. Validate SLOs (error rate < 1%, P99 latency < 2s)
3. Rollout 10% → validate
4. Rollout 50% → validate
5. Rollout 100% → validate
6. Automatic rollback on SLO breach

## Observability

### Metrics
- Prometheus for service metrics
- Custom business metrics via OpenTelemetry
- Cost attribution per tenant

### Logs
- Loki for centralized log aggregation
- Structured JSON logging
- Tenant ID in every log line

### Tracing
- OpenTelemetry for distributed tracing
- Jaeger/Tempo planned for Phase 2

### Alerting
- PagerDuty for SEV-1/SEV-2
- Slack for SEV-3/SEV-4
- Automated runbook linking
