# Production Domain Runbook

## Scope
scene_shot_agent, video_production_agent, localization_agent, and downstream media-renderer.

## scene_shot_agent inconsistent shot plans
### Symptoms
Shot lists ignore script structure; zero-duration shots; missing visual_asset_id bindings that later break timeline assembly.

### Diagnosis
1. Diff `AgentResponse` shots against scripting_agent schema fields (`hook`, `sections`, `cta`).
2. Confirm handoff payload is not a hand-rolled double — tests must import scripting schemas.
3. Check `SceneShotPhase` durable state for incomplete advances.

### Mitigation
Re-invoke with full script object; reject partial scripts missing `hook`. Restore permission `ALLOW` for the primary planning tool if `PermissionDeniedError` is logged.

## video_production_agent render handoff failures
### Symptoms
`render_video` reports `unreachable` or `rejected_*`; timeline duration zero; no `job_id` from media-renderer.

### Diagnosis
1. Confirm `assemble_timeline` produced a non-empty `timeline` before `render_video`.
2. Confirm `AgentConfig.media_renderer_url` points at a live media-renderer; agent must POST `/render` (`# REAL_INTEGRATION: media-renderer`).
3. Inspect `render_job.status` and `render_plan` in the tool result.

### Mitigation
Restart media-renderer; fix URL/env; re-run with shots array so timeline clips > 0. Do not mark the incident closed on “timeline ready” without a `job_id`.

## localization_agent empty or identity “translations”
### Symptoms
Localized packs equal source language; missing locale keys; `translate_pack` returns status ok with empty strings; downstream publishers ship English-only Shorts for non-EN channels.

### Diagnosis
1. Inspect request `target_locales` / `locale` fields on `AgentRequest` — empty locale list short-circuits real work.
2. Confirm `invoke_tool` target matches a registered localization tool name in `tool_permissions` for `localization_agent` (default-deny if never listed).
3. Check provider-gateway errors in `raw_provider_text` / usage; injection-style locale tags should pass through `sanitize_input` without wiping body text.
4. Review `LocalizationPhase` (or domain phase enum) durable state — cost fields should move if the provider was actually called.

### Mitigation
Re-run with explicit BCP-47 locales (e.g. `es-419`, `pt-BR`); verify provider-gateway mock/live returns non-empty translated segments; revoke tests must still deny unknown tools while `ALLOW` remains for the real translate tool.

### Prevention
Keep at least one test that asserts output text differs from source for a non-EN locale. Reject deploys that drop `register_tool` for the localization primary tool.

## Media-renderer dependency
GPU worker saturation shows as queued jobs with flat `progress_percent`. Coordinate with media-renderer on-call; agent-runtime cannot clear the queue.

## Contacts
Production eng; media-renderer on-call; control-plane for approval-gated publish after render.

## Additional operational checklist
- Verify agent-runtime deploy SHA matches the last green CI run before paging secondary on-call.
- Capture task envelopes, permission decisions, and sandbox limits in the incident ticket.
- After mitigation, re-run the domain pytest path with PYTHONPATH unset and record results in the ticket.
- Update this runbook if a new failure mode is confirmed more than once in thirty days.
