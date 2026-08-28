# Distribution Domain Runbook

## Scope
publishing_agent, community_engagement_agent, scheduling_agent, seo_packaging_agent, thumbnail_agent.

## publishing_agent stuck in ApprovalRequiredError
### Symptoms
Publish never reaches platforms; repeated `ApprovalRequiredError` / ESCALATE; control-plane shows pending approvals with no reviewer.

### Diagnosis
1. Confirm tool path hits publishing-service (`# REAL_INTEGRATION: publishing-service`) rather than a local mock return.
2. Inspect approval gate: `ApprovalGate` / authorized approvers list — unauthorized actors will always escalate.
3. Check policy-engine risk score on the entity; high risk forces human approval by design.
4. Verify permission matrix still `ALLOW`s the publish tool for `publishing_agent` after incidents (default-deny if revoked).

### Mitigation
Route approval to an authorized control-plane operator; do not disable the gate in production. If publishing-service is down, surface `unreachable` and page that service — do not bypass with direct platform credentials from the agent.

## community_engagement_agent reply loops or toxic replies
### Symptoms
Agent replies to itself; rate limits from platforms; replies ignore moderation flags.

### Diagnosis
Check engagement tool inputs for thread ids already owned by the bot; confirm sanitize_input on public comment text; review durable `cost_accrued_usd` for runaway loops.

### Mitigation
Pause the agent via agent-registry; clear stuck workflow ids in orchestrator; restore moderation blocklists before re-enable.

## scheduling_agent
Missed windows usually mean timezone-naive timestamps or channel-level quiet hours in metadata — confirm ISO-8601 UTC on schedule payloads.

## thumbnail / SEO
Thumbnail agent empty creatives → provider-gateway image path. SEO packs missing titles → upstream script/clip text empty, not packaging logic alone.

## Contacts
Distribution eng; control-plane operators for approvals; publishing-service on-call.

## Additional operational checklist
- Verify agent-runtime deploy SHA matches the last green CI run before paging secondary on-call.
- Capture task envelopes, permission decisions, and sandbox limits in the incident ticket.
- After mitigation, re-run the domain pytest path with PYTHONPATH unset and record results in the ticket.
- Update this runbook if a new failure mode is confirmed more than once in thirty days.
