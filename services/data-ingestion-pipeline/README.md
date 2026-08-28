# data-ingestion-pipeline

SentraAura Data Ingestion Pipeline — Collectors, normalizers, and NATS publishers.

## Architecture

This service is part of the SentraAura Autonomous AI Media Operating System — Batch 2 (Control & State Layer).

Collects data from YouTube Analytics, Google Trends, RSS news, and social listening. Normalizes raw events into canonical schemas and publishes to NATS for downstream agents. Supports scheduled jobs, backpressure, and dead-letter queues.

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
uvicorn data_ingestion_pipeline.main:app --reload
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
pytest --cov=data_ingestion_pipeline --cov-report=html
```

## Docker

```bash
docker build -t sentraaura/data-ingestion-pipeline:latest .
docker run -p 8000:8000 --env-file .env sentraaura/data-ingestion-pipeline:latest
```

## Directory Structure

```
src/data_ingestion_pipeline/
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
