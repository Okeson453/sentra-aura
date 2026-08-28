# Creative Domain Runbook

## Scope
research_agent, scripting_agent, visual_asset_agent, fact_verification_agent, content_strategist_ideation_agent, voice_agent.

## research_agent injection-defense false negatives
### Symptoms
Untrusted web or tool text alters system instructions; research_bundle contains prompt-injection phrases that later appear in scripting_agent drafts; classifier threshold bypassed.

### Diagnosis
1. Confirm every external string path uses `BaseAgent.sanitize_input(..., source=...)` before provider prompts (topic, claims, retrieved snippets).
2. Check `AgentRuntimeConfig.injection_defense_enabled` and `injection_classifier_threshold` (default 0.7) on the running agent-runtime deploy.
3. Inspect research-service responses at `# REAL_INTEGRATION: research-service` call sites in `research_agent/tools.py` — raw HTML/text must not be concatenated into system role messages.
4. Review sandbox limits: research tools that need HTTP must set `SandboxLimits(allow_network=True)`; `NetworkAccessDeniedError` is a different failure mode than injection miss.

### Mitigation
Enable injection defense if disabled; lower threshold only with security review. Quarantine the offending source URL in research-service allowlists. Re-run scripting only after a clean research_bundle without attacker-controlled instruction text.

### Prevention
Keep dual tests: (1) malicious snippet does not appear in final research fields; (2) legitimate content still flows. Contract with security-officer when threshold changes.

## scripting_agent reflection issues
### Symptoms
Draft ships without critique/rewrite; sponsorship block missing when `enable_sponsorship_injection` is true; reflection_loop not invoked.

### Diagnosis
Confirm `reflection_loop` Draft → Critique → Rewrite still called from `execute`; check `sponsorship_injection.inject_sponsorship` when `request.sponsorship` is set. Provider-gateway `/v1/complete` errors surface in `raw_provider_text`.

### Mitigation
Restore reflection_loop imports; do not short-circuit to a single completion call in hotfixes.

## visual_asset_agent
Empty asset lists usually mean provider-gateway image adapter failure or budget kill — check `cost_accrued_usd` on durable state.

## fact_verification_agent
Disputed claims should cite research-service evidence IDs; heuristic-only “always/never → disputed” paths were removed — if they reappear, treat as regression.

## Contacts
Creative eng; security-officer for injection incidents; research-service on-call.

## Additional operational checklist
- Verify agent-runtime deploy SHA matches the last green CI run before paging secondary on-call.
- Capture task envelopes, permission decisions, and sandbox limits in the incident ticket.
- After mitigation, re-run the domain pytest path with PYTHONPATH unset and record results in the ticket.
- Update this runbook if a new failure mode is confirmed more than once in thirty days.
