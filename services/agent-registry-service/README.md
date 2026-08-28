# Agent Registry Service

Central registry for all 30 SentraAura agents: registration, versioning, health, lifecycle state machine, and CANARY evaluation tracking.

## Structure

- `src/agent_registry_service/main.py` — FastAPI application
- `src/agent_registry_service/config.py` — Settings
- `src/agent_registry_service/models.py` — Pydantic schemas
- `src/agent_registry_service/store.py` — In-memory store (production: Postgres)
- `src/agent_registry_service/registry.py` — Registry operations
- `src/agent_registry_service/lifecycle_state_machine.py` — Agent lifecycle FSM

## Run

```bash
uvicorn agent_registry_service.main:app --reload
```
