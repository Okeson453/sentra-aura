# SentraAura Remediation Ledger
Do not hand-edit status to DONE without a pasted command + output as evidence. This file is the only source of truth for what is actually fixed — it exists specifically to not repeat the failure mode documented in the audit's section 22 and section 29 (self-attestation docs that claimed completion the code didn't support).

## Phase 0 — Unblock
- [x] P0-08 — root pyproject.toml corruption
- [x] P0-05a — clipping-engine dead duplicate: decision + removal
  Decision: `models.py` (Pydantic) vs `models/` (ML wrappers) intentional. CLOSED.
- [ ] P0-05b — publishing-service dead duplicate: decision + removal
- [x] P0-04 — media-renderer async DB driver mismatch
  Commit 2303d296 — `_to_async_url()` for postgresql:// / +psycopg2 / +psycopg → asyncpg.
- [ ] P0-06a — publishing-service test suite uncollectable
- [ ] P0-06b — media-renderer test suite uncollectable

## Phase 1 — Core loop
- [x] P0-01 — clipping perception pipeline stubbed/disconnected
- [x] P0-02a — clipping-engine worker no-op
- [x] P0-02b — media-renderer worker no-op
- [x] P1-01 — render_clip fabricates output URL
  Command: clipping-engine `main.py` dispatches to media-renderer via httpx; refuses completed without real `output_url`. media-renderer worker fails closed (no `storage.sentraaura.com` fake URLs).
  Commits: a325fbb0 (worker), 82a110a1 (main.py restore after accidental placeholder).
  Output: `rg storage.sentraaura.com services/clipping-engine services/media-renderer` → no matches in worker/main paths. pytest clipping-engine → 10 passed.
- [x] P1-02 — create_segment doesn't persist
  Command: Segment ORM (c99d776a) + create_segment writes DB rows with validation (82a110a1).
  Output: endpoint requires video_id, end>start; persists Segment; returns created_at.
- [x] P2-03 — highlight_scoring hardcoded novelty/weights
  Commit fdb11143. pytest test_highlight_scoring → 5 passed.

## Phase 2 — Security
- [x] P0-03a–e — decorative auth → sentinel-security
- [ ] P1-04 — control-plane-api static-secret auth
- [ ] P3-02 — non-constant-time secret comparison

## Phase 3 — Fault tolerance and correctness
- [ ] P0-07 — event bus never wired to real NATS
- [ ] P1-05 — orchestrator swallows activity failures
- [ ] P1-07 — orchestrator hardcoded Temporal host (config already env-driven; verify prod tfvars)

## Phase 4 — Real gaps
- [ ] P1-08 — Human Control Plane UI absent
- [ ] P1-09 — streaming-ingestion-service decision
- [ ] P1-03 — crisis_sentiment_anomaly_agent keyword-match stub
- [ ] P1-10 — publishing-service stale dead-code warning

## Phase 5 — Process
- [ ] P0-09 — root self-attestation docs false/stale
- [ ] P2-05 — documentation hygiene (rolled into P0-09)
- [ ] P2-04 — datetime.utcnow() deprecation sweep
- [ ] P2-02 — duplicated/parallel implementations elsewhere
- [ ] P3-01 — agent scaffold duplication

## Open follow-ups from audit section 28
- [ ] Confirm live/dead status of content_strategist_ideation_agent in-memory dict pattern
- [ ] Confirm live/dead status of orchestrator/state_machine.py in-memory dict pattern

---

## Current Status: IN PROGRESS

**Closed this session:** P1-01, P1-02 (fully on main), P0-04, P0-05a, P2-03.

**Next:** P0-06 test collection, P0-07 NATS wiring, P0-09 retire false self-attestation docs, orchestrator P1-05/P1-07.

Previous PRODUCTION_* self-attestation docs remain untrusted until P0-09.

## Evidence Trail

Without pasted evidence, the item is NOT considered done.
