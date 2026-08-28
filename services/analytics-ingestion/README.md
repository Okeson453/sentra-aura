# Analytics Ingestion Service

Ingests, normalizes, and writes YouTube Analytics and internal performance data to the data warehouse.

## Structure

- `src/analytics_ingestion/main.py` — FastAPI application
- `src/analytics_ingestion/config.py` — Settings
- `src/analytics_ingestion/youtube_analytics_client.py` — YouTube Data API client
- `src/analytics_ingestion/normalization.py` — Metric normalization
- `src/analytics_ingestion/warehouse_writer.py` — ClickHouse/BigQuery writer

## Run

```bash
uvicorn analytics_ingestion.main:app --reload
```
