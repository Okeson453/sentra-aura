# Market & Audience Intelligence Agent

**Domain:** intelligence · **ID:** `market_audience_intelligence_agent`

## Architecture

- **§4.2:** sole consumer of Data Ingestion Pipeline signals; outputs opportunity scores (0–100), ranked `TrendSignal`, competitor gaps, audience personas.
- **§51.1:** does **not** call external trend APIs directly — only `data-ingestion-pipeline`.

## Tools (must match `tool_permissions.py`)

| Tool | Backend |
|------|---------|
| `fetch_trends` | `data_ingestion_client` → `/ingest/trends` (+ youtube/competitors) |
| `analyze_sentiment` | provider-gateway `/v1/complete` synthesis |

## Layout

`agent.py`, `data_ingestion_client.py`, `tools.py`, `schemas.py`, `config.py`, `state.py`, `tests/`
