# Intelligence Domain Runbook

## Scope
Covers executive_orchestrator_agent, portfolio_strategy_agent, market_audience_intelligence_agent, and research_agent failure modes in production.

## executive_orchestrator_agent escalation misfires
### Symptoms
- Escalations fire when workflows are healthy, or fail to fire when stuck >2h, resource utilization >80% for 1h, budget overrun >10%, or ≥5 consecutive failures.
- Downstream swarms idle while orchestrator reports COMPLETED without escalation notes.

### Diagnosis
1. Inspect StrategyResponse.escalations and coordination_notes in the latest task payload.
2. Confirm workflow_state.active_workflows includes last_progress_at timestamps in ISO-8601 UTC.
3. Confirm resource_metrics.exhaustion_window_hours is populated (not only instantaneous CPU).
4. Confirm failure_history is ordered and does not interleave success records that reset the consecutive-failure streak.

### Mitigation
- Backfill telemetry from the workflow engine before re-invoking the agent.
- If escalations are noisy, raise thresholds only via config change with change-control; do not patch agent code in production hotfixes.
- Page the on-call owner when budget_overrun and consecutive_failures both fire within the same hour.

### Prevention
Contract tests must pass for all four escalation conditions plus a healthy negative case. Reject deploys that remove evaluate_escalations from execute().

## portfolio_strategy_agent / market_audience_intelligence_agent
### Symptoms
Empty portfolio_plan handoff; MAI returns no trends despite data-ingestion-pipeline health.

### Diagnosis
Verify data_ingestion_client still calls DataIngestionPipelineClient over HTTP. Check permission matrix ALLOW for fetch_trends. Inspect sandbox NetworkAccessDeniedError if allow_network is false.

### Mitigation
Restore network sandbox flag for MAI; replay last successful ingestion job IDs into the agent payload.

## research_agent
See creative runbook for injection-defense; intelligence on-call still owns cross-swarm research budget caps.

## Escalation contacts
Control-plane operators grant approvals. Security-officer for boundary incidents. Channel-owner for budget overrides.

## Additional operational checklist
- Verify agent-runtime deploy SHA matches the last green CI run before paging secondary on-call.
- Capture task envelopes, permission decisions, and sandbox limits in the incident ticket.
- After mitigation, re-run the domain pytest path with PYTHONPATH unset and record results in the ticket.
- Update this runbook if a new failure mode is confirmed more than once in thirty days.
