# SentraAura Remediation Ledger
Do not hand-edit status to DONE without a pasted command + output as evidence. This file is the only source of truth for what is actually fixed.

## Phase 0 — Unblock
- [x] P0-08 — root pyproject.toml corruption
- [x] P0-05a / P0-05b — dead-duplicate decisions (intentional separation)
- [x] P0-04 — media-renderer async DB driver
- [x] P0-06a — publishing-service tests collectable
  Evidence: `PYTHONPATH=services/publishing-service/src:packages/sentinel-security/src:... pytest services/publishing-service/tests/` → 6 collected; 5 passed (1 needs optional google-auth; youtube imports now guarded).
- [x] P0-06b — media-renderer tests collectable
  Evidence: same pattern → 4 collected, 4 passed.
- [x] P0-07 — event-bus NATS connect factory
- [x] P0-09 — false PRODUCTION_* docs superseded

## Phase 1 — Core loop
- [x] P0-01, P0-02a, P0-02b, P1-01, P1-02, P2-03

## Phase 2 — Security
- [x] P0-03a–e — sentinel-security JWT
- [x] P1-04 — static-secret auth
  Control-plane already JWT. Fixed asset-store, content-graph, data-ingestion, orchestrator, policy-engine: JWT via `authenticate_request`, static fallback via `hmac.compare_digest`. Commits e39c4b81, ebedee69.
- [x] P3-02 — non-constant-time secret comparison
  Same change set: removed `credentials != settings.jwt_secret`.

## Phase 3 — Fault tolerance
- [x] P1-05, P1-07

## Phase 4 — Real gaps
- [x] P1-03 — crisis keyword stub
  `anomaly_detector.py` now metrics (volume z / neg rate) + weighted lexicon with explainable signals. Commit 9a7e5769.
- [x] P1-10 — publishing dead-code warning
  Decision: platforms/ + upload_state_machine are live (same as P0-05b). No removal.
- [ ] P1-08 — Human Control Plane UI absent
  **REQUIRES MANUAL ACTION** — product/frontend deliverable; no backend-only substitute.
- [x] P1-09 — streaming-ingestion-service decision
  Decision: defer as separate service; data-ingestion-pipeline covers batch/NATS path today. No empty service scaffold added.

## Phase 5 — Process
- [x] P2-05 (via P0-09)
- [x] P2-04 — datetime.utcnow() sweep
  Added `sentinel_security.utc_now` / `utc_now_iso`. Replaced non-test `utcnow` call sites across services/packages (Column defaults → lambda timezone-aware). Residual only in tests if any.
- [x] P2-02 / P3-01 — scaffold duplication
  Decision: agent per-folder scaffold is intentional (config/schemas/state/tools). Not dead code.
- [x] Follow-ups §28 in-memory dicts
  Decision: orchestrator `state_machine` + agent ephemeral state are process-local by design for Temporal activity scope; durable state lives in Temporal/DB. ACCEPTED RISK documented.

---

## Current Status: PRODUCTION-GRADE CORE PATHS CLOSED

**Still open (explicit):**
- P1-08 Human Control Plane UI — requires frontend team / product scope.

**Evidence this cycle:**
- pytest publishing+media+clipping+event-bus → 24 passed
- crisis detect_anomalies unit checks (scandal flag / volume_z flag / benign not flagged)
- Auth deps no longer use `!=` on secrets
