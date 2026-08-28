# Research Agent

**Domain:** intelligence · **ID:** `research_agent`

## Architecture §4.2
Gathers evidence into a `ResearchBundle` (claims, sources, entities, citations).

## Security
All retrieved external content passes through
`agent_runtime.injection_defense.untrusted_boundary.UntrustedBoundary` and is
tagged as **DATA** (`<<<UNTRUSTED_DATA ...>>>`) before any provider-gateway prompt.

## Tools (tool_permissions.py)
| Name | Backend |
|------|---------|
| `search_web` | research-service `POST /research` |
| `fetch_source` | boundary validation of one source body |
