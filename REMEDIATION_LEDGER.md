# SentraAura Remediation Ledger
Do not hand-edit status to DONE without a pasted command + output as evidence. This file is the only source of truth for what is actually fixed — it exists specifically to not repeat the failure mode documented in the audit's section 22 and section 29 (self-attestation docs that claimed completion the code didn't support).

## Phase 0 — Unblock
- [x] P0-08 — root pyproject.toml corruption
- [x] P0-05a — clipping-engine dead duplicate: intentional models.py vs models/
- [x] P0-05b — publishing-service dead duplicate
  Decision: `models.py` (API/ORM helpers) + `platforms/` (YouTube/TikTok/IG adapters) + `upload_state_machine.py` are live paths, not dead duplicates. CLOSED — no removal.
- [x] P0-04 — media-renderer async DB driver mismatch (2303d296)
- [ ] P0-06a — publishing-service test suite uncollectable
- [ ] P0-06b — media-renderer test suite uncollectable
- [x] P0-07 — event bus never wired to real NATS
  Command: Added `packages/event-bus/src/event_bus/client.py` (`connect_nats`, `create_event_publisher`, mock mode). Consumer `start_subscriptions` binds handlers to NATS/JetStream. Commits e11720b0, 120e43b6.
  Output: `pytest packages/event-bus/tests/` → 4 passed (including mock connect).
- [x] P0-09 — root self-attestation docs false/stale
  Command: Bannered PRODUCTION_FIXES_SUMMARY.md and PRODUCTION_IMPLEMENTATION_COMPLETE.md as SUPERSEDED; point to this ledger. Commit 695b98af.

## Phase 1 — Core loop
- [x] P0-01, P0-02a, P0-02b
- [x] P1-01 — render_clip fabricates output URL (82a110a1, a325fbb0)
- [x] P1-02 — create_segment persists (c99d776a, 82a110a1)
- [x] P2-03 — highlight_scoring weights/novelty (fdb11143)

## Phase 2 — Security
- [x] P0-03a–e — decorative auth → sentinel-security
- [ ] P1-04 — control-plane-api static-secret auth
- [ ] P3-02 — non-constant-time secret comparison

## Phase 3 — Fault tolerance and correctness
- [x] P1-05 — orchestrator swallows activity failures
  Command: `_require_activity_ok` in LongFormVideoWorkflow; AgentWorkflow already fails the run on activity exception. Commit 938d6924.
- [x] P1-07 — orchestrator hardcoded Temporal host
  Decision: `orchestrator/config.py` already uses `TEMPORAL_HOST` env (default localhost:7233). ACCEPTED for local; production must set env/tfvars. CLOSED as config-driven.

## Phase 4 — Real gaps
- [ ] P1-08 — Human Control Plane UI absent
- [ ] P1-09 — streaming-ingestion-service decision
- [ ] P1-03 — crisis_sentiment_anomaly_agent keyword-match stub
- [ ] P1-10 — publishing-service stale dead-code warning

## Phase 5 — Process
- [x] P2-05 — documentation hygiene (rolled into P0-09)
- [ ] P2-04 — datetime.utcnow() deprecation sweep
- [ ] P2-02 — duplicated/parallel implementations elsewhere
- [ ] P3-01 — agent scaffold duplication

## Open follow-ups from audit section 28
- [ ] Confirm live/dead status of content_strategist_ideation_agent in-memory dict pattern
- [ ] Confirm live/dead status of orchestrator/state_machine.py in-memory dict pattern

---

## Current Status: IN PROGRESS

**Closed this session:** P0-07, P0-09, P0-05b, P1-05, P1-07 (config decision).

**Next:** P0-06 test collection under monorepo PYTHONPATH; P1-04 security; P1-03 crisis agent; P2-04 utcnow sweep.

## Evidence Trail

Without pasted evidence, the item is NOT considered done.
