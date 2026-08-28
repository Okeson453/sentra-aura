# Fact Verification Agent

**Domain:** creative · **ID:** `fact_verification_agent`

## Architecture §4.2
Validates claims via multi-source cross-reference.
**Inputs:** draft segments, `ResearchBundle`, claim graph.
**Outputs:** verified claims + confidence, contradiction alerts.

## Tools (tool_permissions.py)
| Name | Backend |
|------|---------|
| `verify_claim` | research-service `POST /fact-check` |
| `cross_reference` | provider-gateway synthesis |

## Research handoff
Accepts `research_bundle` matching `research_agent.schemas.ResearchResponse`
(claims, sources, key_findings, executive_summary).
