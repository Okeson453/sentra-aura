# SentraAura Remediation Ledger

Authoritative status only — never trust PRODUCTION_* self-attestation docs.

## Closed on main (evidence-backed)

### Phase 0–1 / design-gap (prior)
- P0-04..P0-09, P1-01..P1-07, P2-03, P2-04, P3-02, SERVICE_OWNERS, Argo+KEDA values, bitemporal edges, ClipScore weights, encode+signed URL, P4 clipping heuristics, injection/rights/community, quality gates

### Forensic audit findings (this cycle)
| Finding | Status | Evidence |
|---------|--------|----------|
| **Audit §2** `yield from` in `async def get_db_session` (5 services) | **FIXED** | Sync generator `def get_db_session`; py_compile OK for orchestrator, data-ingestion, content-graph, policy-engine, asset-store |
| **Audit §3** asset-store always LocalStorageBackend | **FIXED** | `backend_factory.create_storage_backend()` selects s3/gcs/azure/local from `STORAGE_BACKEND`; wired in routes + service |
| **Audit §4** packages/event-bus unused | **PARTIAL** | data-ingestion `connect_via_event_bus()`; media-renderer publishes `video_rendered`; clipping publishes `clip_candidate_created` (mock_mode default for offline); full mesh migration still progressive |

## Explicitly open / deferred

| ID | Status |
|----|--------|
| **P1-08 / P4-19** Human Control Plane UI | REQUIRES MANUAL — frontend |
| Full event-driven mesh for all 20 services | Progressive — backbone now consumed by 3 paths |
| Part III streaming / feature store / multimodal / synthetic | Deferred |
| Full Sentence-BERT when weights absent | Optional dep; hash backend in place |

## Regression evidence

```
py_compile 5 dependencies.py → OK
pytest publishing + clipping-engine + media-renderer → 20 passed
backend_factory → LocalStorageBackend default
```
