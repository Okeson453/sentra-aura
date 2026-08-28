# Batch 3 Collection Errors — Out-of-Scope Documentation

**Status:** Documented as out-of-scope (Batch 3)

**Date:** 2026-08-16

## Summary

Seven test collection errors exist in the codebase. These errors occur in services and packages that are explicitly **outside the scope of Batch 2** (Foundation + Long-Form Autonomy). All seven belong to **Batch 3** (Clipping) or **Batch 4** (Closed-Loop Optimization) per the SentraAura implementation phases defined in the Project Targets.

## Affected Files

| # | File Path | Error Type | Batch |
|---|---|---|---|
| 1 | `packages/prompt-registry/tests/test_prompt_registry.py` | `ModuleNotFoundError: No module named 'prompt_registry'` | Batch 4 |
| 2 | `services/agent-runtime/.../ai_clipping_agent/tests/test_ai_clipping_agent.py` | Module name import error | Batch 3 |
| 3 | `services/agent-runtime/.../captioning_agent/tests/test_captioning_agent.py` | Module name import error | Batch 3 |
| 4 | `services/agent-runtime/.../reframing_agent/tests/test_reframing_agent.py` | Module name import error | Batch 3 |
| 5 | `services/provider-gateway/tests/test_adapters.py` | Module name import error | Batch 4 |
| 6 | `services/provider-gateway/tests/test_router.py` | Module name import error | Batch 4 |
| 7 | `services/research-service/tests/test_research_service.py` | Module name import error | Batch 4 |

## Root Cause

The collection errors are caused by:
1. **Missing package source code** — The `prompt-registry` package has tests but no installable source module.
2. **Module path mismatches** — The agent-runtime, provider-gateway, and research-service tests reference module names that do not match the actual directory structure or Python package layout.

These are **not regressions introduced by Batch 2 work**. They exist because the corresponding source modules were never implemented (they are scheduled for Batch 3–4).

## Resolution

These errors are **intentionally not fixed** as part of Batch 2 remediation. They will be resolved when:
- Batch 3 implements the `agent-runtime` service (AI clipping, captioning, reframing agents)
- Batch 4 implements the `provider-gateway` service and `prompt-registry` package
- Batch 4 implements the `research-service`

## Verification Command

To run Batch 2 tests while excluding Batch 3–4 collection errors, use:

```bash
pytest \
  --ignore=packages/prompt-registry/tests \
  --ignore=services/agent-runtime \
  --ignore=services/provider-gateway/tests \
  --ignore=services/research-service/tests
```

This command is the canonical way to verify Batch 2 correctness independently of unimplemented Batch 3–4 modules.
