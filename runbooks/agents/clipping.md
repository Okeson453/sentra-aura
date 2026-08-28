# Clipping Domain Runbook

## Scope
ai_clipping_agent, reframing_agent, captioning_agent, repurposing_agent, and the clipping-engine service (HTTP owner of ClipScore).

## ai_clipping_agent low-quality or policy-violating clips
### Symptoms
Selected candidates have low composite scores but still ship; pronoun-heavy fragments without context reconstruction; near-duplicate clips published.

### Diagnosis
1. Inspect `FeatureScores` / engine `scores`: hook, narrative, context_dependency, novelty, composite.
2. Confirm `score_threshold` and `max_clips` on the request payload.
3. Confirm `rank_and_dedup` `rejected_reason` values (`below_threshold`, `duplicate_of_selected`, `max_clips`).
4. Confirm `# REAL_INTEGRATION: clipping-engine` path: agent `tools.select_clips` must POST `{CLIPPING_ENGINE_URL}/clips/detect` (not local re-scoring).

### Mitigation
Raise `score_threshold`; force re-clip with timed segments from clipping-engine rather than script-only synthesis. Hold `publishing_agent` approvals until QC passes.

### Prevention
Deploy must keep `rank_and_dedup` in the agent layer and `score_highlights` in `clipping_engine.pipeline.highlight_scoring` — do not reintroduce dual ClipScore ownership.

## reframing_agent mid-frame crops when subject metadata is missing
### Symptoms
Vertical/square outputs show faces or subjects cut off; `crop_box` always centers at (0.5, 0.5); Shorts look static while source has clear motion.

### Diagnosis
1. Inspect `reframe_clip` results: each crop should include `crop_box` with `x,y,w,h` derived from subject center (`cx`, `cy`), defaulting to mid-frame only when subject metadata is absent.
2. Confirm request payload still carries clip candidates from `ai_clipping_agent` (start/end seconds + text) — empty `clips` forces the single default mid-frame path in `tools.py`.
3. Check `ReframingPhase` progression in durable state; stalled `RUNNING` without `COMPLETED` usually means `invoke_tool("reframe_clip")` never ran (permission revoke or sandbox).

### Mitigation
Re-run with explicit subject boxes or face landmarks when available; if only mid-frame defaults appear, treat as upstream metadata loss from clipping-engine shot detection, not a captioning bug. Restore `ALLOW` for `reframe_clip` on `reframing_agent` in the permission matrix if `PermissionDeniedError` appears in logs.

### Prevention
Regression tests must assert non-default `crop_box` when subject center is provided; reject deploys that remove `register_tool("reframe_clip", ...)`.

## captioning_agent / repurposing_agent
Caption word timings scale with text length; empty captions usually mean missing reframed input. Repurposing platform packs should still list distinct aspect targets per platform key.

## clipping-engine pipeline
ASR/diarization/shot detection failures: `/clips/detect` should still return scored structure when segments are supplied in the body. If extract_audio raises `FileNotFoundError`, the source URI is wrong — not agent selection logic.

## Contacts
Clipping eng; policy-engine for brand-safety blocks on clip text.

## Additional operational checklist
- Verify agent-runtime deploy SHA matches the last green CI run before paging secondary on-call.
- Capture task envelopes, permission decisions, and sandbox limits in the incident ticket.
- After mitigation, re-run the domain pytest path with PYTHONPATH unset and record results in the ticket.
- Update this runbook if a new failure mode is confirmed more than once in thirty days.
