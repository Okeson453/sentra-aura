# SentraAura Remediation Ledger
Do not hand-edit status to DONE without a pasted command + output as evidence. This file is the only source of truth for what is actually fixed — it exists specifically to not repeat the failure mode documented in the audit's section 22 and section 29 (self-attestation docs that claimed completion the code didn't support).

## Phase 0 — Unblock
- [ ] P0-08 — root pyproject.toml corruption
- [ ] P0-05a — clipping-engine dead duplicate: decision + removal
- [ ] P0-05b — publishing-service dead duplicate: decision + removal
- [ ] P0-04 — media-renderer async DB driver mismatch
- [ ] P0-06a — publishing-service test suite uncollectable
- [ ] P0-06b — media-renderer test suite uncollectable

## Phase 1 — Core loop
- [ ] P0-01 — clipping perception pipeline stubbed/disconnected
- [ ] P0-02a — clipping-engine worker no-op
- [ ] P0-02b — media-renderer worker no-op
- [ ] P1-01 — render_clip fabricates output URL
- [ ] P1-02 — create_segment doesn't persist
- [ ] P2-03 — highlight_scoring hardcoded novelty/weights

## Phase 2 — Security
- [ ] P0-03a — clipping-engine decorative auth
- [ ] P0-03b — publishing-service decorative auth
- [ ] P0-03c — media-renderer decorative auth
- [ ] P0-03d — research-service decorative auth
- [ ] P0-03e — rights-registry-service decorative auth
- [ ] P1-04 — control-plane-api static-secret auth
- [ ] P3-02 — non-constant-time secret comparison

## Phase 3 — Fault tolerance and correctness
- [ ] P0-07 — event bus never wired to real NATS
- [ ] P1-05 — orchestrator swallows activity failures
- [ ] P1-07 — orchestrator hardcoded Temporal host

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

## Current Status: NOT STARTED

All items are TODO. Previous self-attestation documents (PRODUCTION_FIXES_SUMMARY.md, PRODUCTION_IMPLEMENTATION_COMPLETE.md) have been identified as false/stale by the audit and must not be trusted.

## Evidence Trail

Each completed item must have the exact command run and output (summary line preserved).

Example format:
Command: poetry install
Output: Installing dependencies... All 45 packages installed successfully (5.2s)

Without pasted evidence, the item is NOT considered done.
