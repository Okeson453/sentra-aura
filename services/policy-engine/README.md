# policy-engine

SentraAura Policy Engine — Autonomy levels, risk scoring, and policy enforcement.

## Architecture

This service is part of the SentraAura Autonomous AI Media Operating System — Batch 2 (Control & State Layer).

Evaluates decisions against L0-L4 autonomy policies with weighted risk scoring. Supports adaptive policies, human-in-the-loop approval routing, and audit logging of all evaluations.

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
uvicorn policy_engine.main:app --reload
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
pytest --cov=policy_engine --cov-report=html
```

## Docker

```bash
docker build -t sentraaura/policy-engine:latest .
docker run -p 8000:8000 --env-file .env sentraaura/policy-engine:latest
```

## Directory Structure

```
src/policy_engine/
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
