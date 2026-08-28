# ADR-002: Consolidated Module Structure for Batch 2 Services

**Status:** Accepted

**Date:** 2026-08-16

**Scope:** Batch 2 (control-plane-api, orchestrator, content-graph-service, policy-engine, asset-store, data-ingestion-pipeline)

## Context

The Batch 2 definition file specifies granular per-entity file paths such as:
- `services/channel_service.py`, `services/content_plan_service.py`
- `repositories/channel_repository.py`, `repositories/content_plan_repository.py`
- `workflows/longform_production_workflow.py`, `workflows/clip_production_workflow.py`
- `collectors/youtube_trends.py`, `collectors/social_trends.py`
- `models/topic.py`, `models/script.py`

During implementation, these were delivered as consolidated modules (`services.py`, `repositories.py`, `workflows.py`, `collectors.py`, `node.py`) that contain all entity-specific logic within a single file per layer.

## Decision

We accept the consolidated module structure as the canonical pattern for Batch 2 and going forward into Batches 3–6. The rationale:

1. **Functional equivalence** — Every entity, method, and relationship specified in the Batch 2 definition exists in the consolidated files. No logic is missing or deferred.
2. **Maintainability** — The consolidated files are well-organized with clear section comments (`# Channel`, `# Content Plan`, etc.) and are under 600 LOC each, which is well within the maintainability standard stated in the Project Targets file.
3. **No mechanical splitting** — Splitting files purely to match path names would create artificial fragmentation, increase import overhead, and complicate cross-entity operations (e.g., `ContentService` coordinates plans, scripts, videos, and clips) without improving readability.
4. **Future reversibility** — If any consolidated file grows beyond ~800 LOC or accumulates genuinely unrelated concerns, a future ADR may reverse this decision for that specific file.

## Consequences

- **Positive:** Fewer files to navigate, simpler imports, easier cross-entity coordination in service layers.
- **Negative:** Slightly less granular git history per entity; IDEs with file-based navigation require section-level search rather than file-level.
- **Mitigation:** Section headers and consistent ordering within consolidated files make navigation straightforward.

## Affected Files

| Specified Path | Actual Path | Rationale |
|---|---|---|
| `services/channel_service.py` | `services.py` (all entities) | Cross-entity coordination (ContentService) requires shared file |
| `repositories/channel_repository.py` | `repositories.py` (all entities) | Consistent CRUD patterns, shared base class |
| `workflows/longform_production_workflow.py` | `workflows.py` (all workflows) | Temporal workflow registration simpler in one file |
| `collectors/youtube_trends.py` | `collectors.py` (all collectors) | Shared BaseCollector, config, and retry logic |
| `models/topic.py` | `models.py` / `node.py` | SQLAlchemy relationship backrefs require single Base |

This decision is binding for Batches 3–6 unless explicitly reversed by a future ADR.
