# Content Strategist & Ideation Agent

**Domain:** creative · **ID:** `content_strategist_ideation_agent`

## Architecture §4.2
Converts market intelligence + research into `ContentStrategy`, `TopicPortfolio`,
idea set, and hook candidates.

## Tools (tool_permissions.py)
| Name | Backend |
|------|---------|
| `generate_concepts` | provider-gateway |
| `score_ideas` | ranking over generated concepts |

## Downstream
`scripting_handoff` maps to `scripting_agent.ScriptRequest`
(`video_title`, `audience_profile`, `target_keywords`, …).
