# content-graph-service

SentraAura Content Asset Graph Service — Persistent content graph with lineage.

## Architecture

This service is part of the SentraAura Autonomous AI Media Operating System — Batch 2 (Control & State Layer).

Stores content nodes (topics, scripts, videos, clips, publications), edges (derived_from, clipped_from, published_as), and immutable lineage records. Supports graph traversal, path queries, and temporal versioning.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start service
uvicorn content_graph_service.main:app --reload
```

## API Documentation

- OpenAPI docs: http://localhost:8000/docs
- Re docs: http://localhost:8000/redoc
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

## Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# With coverage
pytest --cov=content_graph_service --cov-report=html
```

## Docker

```bash
docker build -t sentraaura/content-graph-service:latest .
docker run -p 8000:8000 --env-file .env sentraaura/content-graph-service:latest
```

## Directory Structure

```
src/content_graph_service/
├── __init__.py
├── main.py              # FastAPI app factory
├── config.py            # Pydantic Settings
├── db/
│   ├── __init__.py
│   ├── base.py          # Declarative base + mixins
│   └── session.py       # Engine, session factory
├── api/
│   ├── __init__.py
│   ├── dependencies.py  # Auth, rate limit, tenant
│   └── routes/          # HTTP route handlers
├── services/            # Business logic layer
├── repositories/        # Data access layer
└── models/              # SQLAlchemy models

migrations/              # Alembic migrations
├── env.py
├── script.py.mako
└── versions/

tests/
├── unit/
├── integration/
└── fixtures/

runbooks/                # Incident response
```

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md)

## License

Proprietary — SentraAura / Okeson Holdings
