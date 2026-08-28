FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
COPY --from=local-packages /packages ./packages/

RUN pip install --no-cache-dir -e ./packages/service-kit -e ./packages/sentinel-exceptions -e .

EXPOSE 8000

CMD ["uvicorn", "asset_store.main:app", "--host", "0.0.0.0", "--port", "8000"]
