# SentraAura Clipping Engine

## Overview

This service is part of the SentraAura Batch 4 delivery.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run locally
uvicorn clipping_engine.main:app --reload --port 8080

# Run tests
pytest tests/ -v

# Build Docker image
docker build -t sentra-aura/clipping-engine:latest .

# Run with docker-compose
docker-compose up
```

## Environment Variables

See `.env.example` for all available configuration options.

## API Documentation

When running, visit:
- OpenAPI docs: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
- Health: http://localhost:8080/health
