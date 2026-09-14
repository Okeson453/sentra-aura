# Agent Runtime — hosts all 30 specialized agents behind the production HTTP surface.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build toolchain for wheels that lack prebuilt binaries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy workspace metadata + shared packages first for layer caching.
COPY pyproject.toml poetry.lock* ./
COPY packages/ ./packages/
COPY services/agent-runtime/ ./services/agent-runtime/

# Workspace packages are declared by bare name, so install the whole graph the
# service depends on before installing the runtime itself.
RUN pip install --upgrade pip \
    && pip install ./packages/sentinel-exceptions \
       ./packages/sentinel-security \
       ./packages/observability \
       ./packages/service-kit \
       ./packages/agent-contracts \
    && pip install ./services/agent-runtime

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8000"]
