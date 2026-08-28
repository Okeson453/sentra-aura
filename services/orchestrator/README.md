# orchestrator

SentraAura Orchestrator — Durable workflow orchestration with Temporal.

## Architecture

This service is part of the SentraAura Autonomous AI Media Operating System — Batch 2 (Control & State Layer).

Manages workflow definitions, activity execution, state machines, and DAG scheduling. Supports long-form video production, clipping, publishing, and localization workflows with saga pattern, checkpointing, and compensation.

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
uvicorn orchestrator.main:app --reload
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
pytest --cov=orchestrator --cov-report=html
```

## Docker

```bash
docker build -t sentraaura/orchestrator:latest .
docker run -p 8000:8000 --env-file .env sentraaura/orchestrator:latest
```

## Directory Structure

```
src/orchestrator/
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
