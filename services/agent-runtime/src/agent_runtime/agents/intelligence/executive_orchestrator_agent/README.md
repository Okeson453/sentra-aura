# Executive Orchestrator Agent

**Domain:** intelligence  
**Agent ID:** `executive_orchestrator_agent`

## Role (Architecture §4.2)

Central coordination: content strategy, resource allocation, and **inter-swarm**
workflow initiation. Consumes optional `portfolio_plan` and `market_intelligence`
payloads (from peer intelligence agents) via the AgentMessage envelope; produces
strategy plus agent assignments and a workflow DAG.

## Layout

| File | Role |
|------|------|
| `agent.py` | Entrypoint |
| `coordination.py` | Assignments + DAG from strategy + peer inputs |
| `tools.py` | Prompt-registry + provider-gateway `/v1/complete` |
| `schemas.py` | Request/response models |
| `config.py` / `state.py` | Settings and phase tracking |

Prompts: `packages/prompt-registry/prompts/executive_orchestrator_agent/strategy/`
