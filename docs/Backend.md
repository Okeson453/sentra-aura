# SentraAura — Backend Documentation

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language (Core) | Go | 1.22+ |
| Language (AI/ML) | Python | 3.12 |
| Framework (Go) | Gin / Echo | latest |
| Framework (Python) | FastAPI | 0.110+ |
| Workflow Engine | Temporal | 1.22+ |
| Message Bus | NATS JetStream | 2.10+ |
| Database | Aurora PostgreSQL | 16.3 |
| Graph DB | Neo4j | 5.x |
| Cache | ElastiCache Redis | 7.x |
| Object Storage | S3 | - |
| Container Orchestration | EKS | 1.29 |
| IaC | Terraform | 1.9+ |
| Packaging | Helm | 3.15+ |

## Service Structure

Each backend service follows a consistent structure:

```
services/<service-name>/
├── src/
│   └── <service_name>/
│       ├── __init__.py
│       ├── main.py              # Entry point
│       ├── api/                 # HTTP handlers
│       ├── domain/              # Business logic
│       ├── infrastructure/      # DB, cache, external clients
│       └── config.py            # Configuration
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── fixtures/                # Test data
├── Dockerfile
├── pyproject.toml               # Python deps
└── README.md
```

## Inter-Service Communication

### Synchronous
- HTTP/REST for request/response patterns
- gRPC for high-performance internal calls (planned)
- GraphQL for complex queries

### Asynchronous
- NATS JetStream for event-driven communication
- Temporal for durable workflows
- Topics:
  - `content.created` — New content asset created
  - `content.rendered` — Rendering completed
  - `content.published` — Publishing completed
  - `agent.completed` — Agent task completed
  - `quota.exceeded` — Quota threshold breached

## Database Schema Conventions

### Table Naming
- Singular nouns: `user`, `channel`, `asset`
- Tenant-scoped tables: `<tenant>_user`, `<tenant>_channel`
- Audit tables: `<table>_audit`

### Column Conventions
- Primary key: `id` (UUID v7)
- Timestamps: `created_at`, `updated_at`, `deleted_at` (soft delete)
- Tenant column: `tenant_id` (every table)
- JSONB for flexible metadata

### Migrations
- Managed by Alembic (Python) or golang-migrate (Go)
- Forward-only migrations in production
- Backward-compatible changes required

## API Design

### REST Conventions
- Resource-oriented URLs: `/api/v1/channels`, `/api/v1/assets/{id}`
- HTTP methods: GET, POST, PUT, PATCH, DELETE
- Status codes: 200, 201, 204, 400, 401, 403, 404, 409, 422, 500
- Pagination: cursor-based for large collections
- Filtering: query parameters with `filter[field]=value`
- Sorting: `sort=field:asc|desc`

### GraphQL Conventions
- Queries for reads, mutations for writes
- Relay-style connections for pagination
- DataLoader for N+1 prevention
- Complexity limits for query depth

### Error Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input provided",
    "details": [
      {
        "field": "title",
        "message": "Title must be between 1 and 200 characters"
      }
    ],
    "request_id": "req-uuid",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

## Authentication & Authorization

### JWT Claims
```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "roles": ["admin", "editor"],
  "permissions": ["content:create", "content:read"],
  "iat": 1704067200,
  "exp": 1704153600
}
```

### Middleware Stack
1. Request ID generation
2. Logging
3. CORS
4. Rate limiting (Quota Broker)
5. Authentication (JWT validation)
6. Authorization (RBAC check)
7. Tenant isolation

## Testing Strategy

### Unit Tests
- Coverage target: 85%
- Mock external dependencies
- Table-driven tests (Go)
- pytest fixtures (Python)

### Integration Tests
- Test against real databases (testcontainers)
- HTTP client tests against running service
- Event bus integration tests

### Contract Tests
- OpenAPI spec validation
- Event schema validation
- GraphQL schema validation

### Workflow Tests
- Temporal workflow unit tests
- End-to-end pipeline tests
- Compensation/rollback tests

## Local Development

### Prerequisites
- Docker & Docker Compose
- Go 1.22+ (for core services)
- Python 3.12 (for AI services)
- kubectl & Helm (for K8s testing)
- Temporal CLI

### Quick Start
```bash
# Start infrastructure
docker compose -f local/docker-compose.yml up -d

# Run database migrations
alembic upgrade head

# Seed local data
python local/seed/seed_channels.py
python local/seed/seed_topics.py
python local/seed/seed_assets.py

# Start services
make dev-up
```

## Environment Configuration

### Required Secrets
- `DB_PASSWORD` — Aurora PostgreSQL master password
- `REDIS_PASSWORD` — ElastiCache password
- `NATS_CREDENTIALS` — NATS authentication
- `TEMPORAL_TLS_CERT` — Temporal mTLS certificate
- `OPENAI_API_KEY` — OpenAI provider key
- `ANTHROPIC_API_KEY` — Anthropic provider key
- `STRIPE_API_KEY` — Billing integration

### Environment Variables
- `ENVIRONMENT` — local, dev, staging, canary, production
- `LOG_LEVEL` — debug, info, warn, error
- `OTEL_ENABLED` — true/false
- `METRICS_PORT` — Prometheus metrics port (default 9090)
