# Operations Domain Runbook

## Scope
crisis_sentiment_anomaly_agent, cost_control_agent, rights_remediation_agent, quality_control_agent, compliance_agent, experimentation_agent, optimization_agent, memory_agent, analytics_agent.

## crisis_sentiment_anomaly_agent false-positive storms
### Symptoms
Pages fire on normal launch spikes; anomaly scores high while human sentiment is neutral; repeated alerts for the same channel_id.

### Diagnosis
1. Inspect anomaly tool outputs: score, baseline window, channel_id.
2. Confirm input metrics are not double-counted from analytics-ingestion backfills.
3. Check whether threshold config was lowered without change-control.

### Mitigation
Raise threshold via config; suppress duplicate channel_id alerts for a cool-down window; page only when score exceeds the production threshold for two consecutive windows.

## rights_remediation_agent missed takedowns
### Symptoms
Known infringing asset ids remain published; remediation jobs stuck; rights-registry returns 404 for asset ids the agent still treats as active.

### Diagnosis
1. Confirm `# REAL_INTEGRATION: rights-registry-service` HTTP calls in `rights_registry_client.py` / tools (not stub empty lists).
2. Inspect durable state errors for registry timeouts vs. permission denials.
3. Verify asset ids in the agent payload match registry identifiers (not content-graph node ids alone).

### Mitigation
Re-sync asset ids from content-graph → rights-registry; re-run remediation with network sandbox enabled; escalate to legal if registry confirms infringement and publish path is still open.

### Prevention
Keep tests that mock registry denial and assert the agent does not mark remediation complete.

## cost_control_agent
Budget kills should reference `cost_accrued_usd` / budget fields on durable agent state across the swarm — if cost stays 0.0 while providers bill, telemetry is broken upstream.

## quality_control / compliance
QC failures must cite policy-engine reason codes; compliance blocks without reason codes are incomplete incidents.

## experimentation / optimization
Experiment assignment skew → check hashing seed stability; optimization agent recommending disabled tools indicates stale capability manifests from agent-registry.

## Contacts
Ops eng; rights-registry on-call; finance for budget threshold changes; security for compliance escalations.

## Additional operational checklist
- Verify agent-runtime deploy SHA matches the last green CI run before paging secondary on-call.
- Capture task envelopes, permission decisions, and sandbox limits in the incident ticket.
- After mitigation, re-run the domain pytest path with PYTHONPATH unset and record results in the ticket.
- Update this runbook if a new failure mode is confirmed more than once in thirty days.
