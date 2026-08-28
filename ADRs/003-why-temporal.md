# ADR-003: Why Temporal for Workflow Orchestration

## Status

Accepted

## Context

SentraAura's autonomous media operations require durable execution of long-running, multi-step workflows (content production pipelines, quality gates, publishing workflows). We evaluated several workflow engines.

## Decision

Use **Temporal** as the primary workflow orchestration engine.

## Rationale

### Temporal Strengths

1. **Durable Execution**: Workflow state is automatically persisted; server crashes don't lose progress
2. **Language SDKs**: Native Go and Python SDKs match our service languages
3. **Visibility**: Built-in UI for workflow state, history, and debugging
4. **Retries & Timeouts**: Declarative retry policies with exponential backoff
5. **Sagas**: Native compensation support for rollback in multi-step workflows
6. **Scalability**: Battle-tested at Uber, Netflix, Coinbase for millions of workflows/day

### Alternatives Considered

| Engine | Pros | Cons | Verdict |
|--------|------|------|---------|
| Apache Airflow | Rich UI, Python-native | Not designed for event-driven, state machine complexity | Rejected |
| Cadence (Uber) | Predecessor to Temporal | Less active community, fewer SDKs | Rejected |
| AWS Step Functions | Managed, serverless | Vendor lock-in, limited expressiveness | Rejected for portability |
| Argo Workflows | Kubernetes-native | Less durable, complex retry logic | Rejected for reliability |
| Custom (NATS + DB) | Full control | Re-inventing the wheel, maintenance burden | Rejected |

## Consequences

### Positive
- Workflows survive pod restarts, node failures, cluster upgrades
- Developers write workflows as code (Go/Python), not YAML
- Built-in observability and debugging
- Easy to test workflows deterministically

### Negative
- Additional infrastructure to operate (Temporal server cluster)
- Learning curve for workflow-as-code paradigm
- Potential vendor risk (Temporal Technologies Inc.)

## Mitigations
- Temporal server deployed as Helm chart on EKS (portable)
- Multi-region backup strategy for workflow history
- Team training and documentation
- Fallback to direct service calls for simple operations (L0 autonomy)
