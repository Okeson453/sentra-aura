FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
COPY --from=local-packages /packages ./packages/

RUN pip install --no-cache-dir -e ./packages/service-kit -e ./packages/sentinel-exceptions -e ./packages/sentinel-security -e ./packages/agent-contracts -e ./packages/content-graph-client -e ./packages/provider-interfaces -e .

EXPOSE 8000

CMD ["uvicorn", "control_plane_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
