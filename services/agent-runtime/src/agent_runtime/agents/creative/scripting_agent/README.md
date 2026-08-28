# Scripting Agent

**Domain:** creative  
**Agent ID:** `scripting_agent`

## Description

Merged Draft → Critique → Rewrite agent for YouTube (and multi-platform) video scripts.
Optional sponsorship injection (Backend §46.2) places a compliant sponsor mention
according to placement rules without discarding provider-generated creative text.

## Canonical layout

| File | Role |
|------|------|
| `agent.py` | Entry point; orchestrates reflection + sponsorship |
| `schemas.py` | Pydantic request/response models |
| `config.py` | `SCRIPTING_*` settings (gateway URL, model, rounds) |
| `state.py` | Reflection loop state machine |
| `tools.py` | Prompt render + `POST /v1/complete` against provider-gateway |
| `reflection_loop.py` | Draft → Critique → Rewrite cycle |
| `sponsorship_injection.py` | Sponsor mention placement |
| `tests/` | Unit + gateway integration tests |

Prompts live in `packages/prompt-registry/prompts/scripting_agent/`
(`draft`, `critique`, `rewrite` — each with `v1.jinja2` + `v1.meta.yaml`).
They are **not** duplicated under this agent directory.

## Tools / external calls

- **provider-gateway** `POST /v1/complete` — every LLM step (draft, critique, rewrite)
- Default local URL: `http://localhost:8081` (`PROVIDER_GATEWAY_URL` / `SCRIPTING_PROVIDER_GATEWAY_URL`)

## Evaluation

Datasets: `evals/scripting_agent/v1/` (and `v2/`).
