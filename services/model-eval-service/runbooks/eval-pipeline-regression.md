# Evaluation Pipeline Regression

## Symptoms

Eval scores drop suddenly across multiple agents. CI gates fail.

## Impact

Blocked deployments, false confidence in agent quality, potential production regression.

## Detection

Alert: `eval_score_delta < -0.05` compared to previous version for any agent.

## Mitigation

1. Check if prompt registry was updated recently. 2. Verify provider gateway health — degraded provider can lower scores. 3. Check if eval dataset was corrupted or changed. 4. If provider issue, route to fallback.

## Recovery

Rollback to previous prompt version if regression is confirmed. Re-run evals with pinned provider.

## Post-Incident

Add provider-health gate before eval runs. Version-lock eval datasets.
