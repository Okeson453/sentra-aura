# Agent Lifecycle Stuck

## Symptoms

Agent remains in DRAFT or CANARY state indefinitely. New agent version not promoted.

## Impact

Stale agent behavior, missing bug fixes, blocked feature rollout.

## Detection

Alert: `agent_lifecycle_age > 48h` for non-PRODUCTION agent with active traffic.

## Mitigation

1. Check evaluation results in model-eval-service. 2. If evals are pending, trigger manual eval run. 3. If evals failed, review failure reasons and fix agent. 4. If human approval is pending, notify approvers.

## Recovery

Force state transition via admin API if emergency fix is required. Document override.

## Post-Incident

Review approval SLA. Automate more eval gates to reduce human bottleneck.
