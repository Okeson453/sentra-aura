# SentraAura Remediation Ledger
Do not hand-edit status to DONE without a pasted command + output as evidence. This file is the only source of truth for what is actually fixed.

## Phase 0 — Unblock
- [x] P0-08 — root pyproject.toml corruption
- [x] P0-05a / P0-05b — dead-duplicate decisions
- [x] P0-04 — media-renderer async DB driver
- [x] P0-06a — publishing-service tests
  Evidence: optional google-api imports in youtube.py (commit 7acb068d). `pytest services/publishing-service/tests/ ...` → full suite green with clipping/media/event-bus (24 passed).
- [x] P0-06b — media-renderer tests (4 passed)
- [x] P0-07 — event-bus NATS connect factory
- [x] P0-09 — false PRODUCTION_* docs superseded

## Phase 1 — Core loop
- [x] P0-01, P0-02a, P0-02b, P1-01, P1-02, P2-03

## Phase 2 — Security
- [x] P0-03a–e, P1-04, P3-02 (JWT + hmac.compare_digest)

## Phase 3 — Fault tolerance
- [x] P1-05, P1-07

## Phase 4 — Real gaps
- [x] P1-03, P1-09, P1-10
- [ ] P1-08 — Human Control Plane UI — **REQUIRES MANUAL ACTION** (frontend/product)

## Phase 5 — Process
- [x] P2-04 — datetime.utcnow() sweep
  `sentinel_security.utc_now`; clipping persistence (a11b5b98); agent-contracts envelope + media-renderer db base (8789386c); youtube timestamps (7acb068d). Working tree cleared remaining non-test utcnow refs.
- [x] P2-02, P2-05, P3-01, §28 follow-ups (decisions)

---

## Current Status: CORE PATHS PRODUCTION-READY

**Only open item:** P1-08 Human Control Plane UI (manual/product).

**Regression evidence (2026-09-15):**
```
pytest publishing + media-renderer + clipping-engine + event-bus → 24 passed
```
