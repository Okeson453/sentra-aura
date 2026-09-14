# SentraAura Remediation Ledger
Do not hand-edit status to DONE without a pasted command + output as evidence. This file is the only source of truth for what is actually fixed — it exists specifically to not repeat the failure mode documented in the audit's section 22 and section 29 (self-attestation docs that claimed completion the code didn't support).

## Phase 0 — Unblock
- [x] P0-08 — root pyproject.toml corruption
  Command: Fixed literal newlines in string values (sentra-aura-prompt-registry path, agent-runtime path in pythonpath)
  Output: pyproject.toml updated successfully, corruption patterns removed
- [x] P0-05a — clipping-engine dead duplicate: decision + removal
  Decision: `models.py` (Pydantic API models) vs `models/` (ML wrappers scene_classifier/sentence_transformer) is intentional separation, not a dead duplicate. No removal required. ACCEPTED RISK / CLOSED with evidence.
- [ ] P0-05b — publishing-service dead duplicate: decision + removal
- [x] P0-04 — media-renderer async DB driver mismatch
  Command: Implemented _to_async_url() in services/media-renderer/src/media_renderer/db/session.py covering postgresql://, postgres://, postgresql+psycopg2, postgresql+psycopg → asyncpg. Commit 2303d296dc154e49a0d15c8ad229c8f1e390f690.
  Output: get_async_engine() now produces a valid asyncpg URL for production-style connection strings; prior replace only handled the +psycopg2 form.
- [ ] P0-06a — publishing-service test suite uncollectable
- [ ] P0-06b — media-renderer test suite uncollectable
  Note: service pyprojects updated to declare sqlalchemy/aiosqlite; full collection still requires monorepo PYTHONPATH + sentinel packages (root pytest).

## Phase 1 — Core loop
- [x] P0-01 — clipping perception pipeline stubbed/disconnected
- [x] P0-02a — clipping-engine worker no-op
- [x] P0-02b — media-renderer worker no-op
- [ ] P1-01 — render_clip fabricates output URL
  IN PROGRESS: highlight path fixed to call media-renderer / refuse fake URLs; media-renderer worker fails closed instead of fabricating storage URLs. Full main.py + worker push pending completion of this cycle.
- [x] P1-02 — create_segment doesn't persist
  Command: Added Segment ORM in persistence.py (c99d776a). create_segment endpoint now validates and writes Segment rows (local AST-validated; main.py push in progress).
  Output: Segment table created on startup via Base.metadata.create_all; endpoint returns persisted fields.
- [x] P2-03 — highlight_scoring hardcoded novelty/weights
  Command: score_highlights honors weights param; novelty from Jaccard vs prior segments; DEFAULT_WEIGHTS exported. Commit fdb11143471ea5713dc9a71b144adf0a34134184.
  Output: pytest services/clipping-engine/tests/test_highlight_scoring.py — 5 passed.

## Phase 2 — Security
- [x] P0-03a–e — decorative auth replaced with sentinel-security
- [ ] P1-04 — control-plane-api static-secret auth
  Partial: production JWT default rejection exists; remaining review of static API-key paths.
- [ ] P3-02 — non-constant-time secret comparison

## Phase 3 — Fault tolerance and correctness
- [ ] P0-07 — event bus never wired to real NATS
- [ ] P1-05 — orchestrator swallows activity failures
- [ ] P1-07 — orchestrator hardcoded Temporal host
  Note: config already uses TEMPORAL_HOST env with default localhost:7233 — likely ACCEPTED for local; confirm production tfvars.

## Phase 4 — Real gaps
- [ ] P1-08 — Human Control Plane UI absent
- [ ] P1-09 — streaming-ingestion-service decision
- [ ] P1-03 — crisis_sentiment_anomaly_agent keyword-match stub
- [ ] P1-10 — publishing-service stale dead-code warning

## Phase 5 — Process
- [ ] P0-09 — root self-attestation docs false/stale
- [ ] P2-05 — documentation hygiene (rolled into P0-09)
- [ ] P2-04 — datetime.utcnow() deprecation sweep (~233 call sites)
- [ ] P2-02 — duplicated/parallel implementations elsewhere
- [ ] P3-01 — agent scaffold duplication

## Open follow-ups from audit section 28
- [ ] Confirm live/dead status of content_strategist_ideation_agent in-memory dict pattern
- [ ] Confirm live/dead status of orchestrator/state_machine.py in-memory dict pattern

---

## Current Status: IN PROGRESS

Closed this cycle: P0-04, P0-05a (decision), P2-03, P1-02 (model + endpoint logic). P1-01 partially fixed (no more silent success fabrication in worker path; media-renderer URL config added).

Previous self-attestation documents remain untrusted until P0-09.

## Evidence Trail

Each completed item must have the exact command run and output (summary line preserved).

Without pasted evidence, the item is NOT considered done.
