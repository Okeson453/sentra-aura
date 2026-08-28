# Portfolio Strategy Agent

**Domain:** intelligence · **ID:** `portfolio_strategy_agent`

## Architecture §4.2

| | |
|--|--|
| **Purpose** | Channel-level goals, content mix, budget allocation |
| **Inputs** | Channel goals, historical performance, budget |
| **Outputs** | Portfolio plan, topic quotas, budget allocation |

## Tool (tool_permissions.py)

| Name | Backend |
|------|---------|
| `analyze_portfolio` | provider-gateway `/v1/complete` |

## Orchestrator contract

Response includes `portfolio_plan` dict consumable by `executive_orchestrator_agent`
(`topic_quotas`, `budget_allocation`, `emphasize_distribution`).
