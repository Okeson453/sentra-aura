# SentraAura — Prompt Injection Response Runbook

## Overview

This runbook defines the response procedures for detected prompt injection attacks against SentraAura's autonomous AI agents.

## Detection Signals

- Agent output contains unexpected system instructions
- Agent attempts to access unauthorized resources
- Agent behavior deviates from configured guardrails
- Security monitoring detects anomalous prompt patterns
- User reports suspicious agent behavior

## Severity Classification

| Level | Criteria | Response |
|-------|----------|----------|
| Low | Single isolated attempt, blocked by guardrails | Log and monitor |
| Medium | Multiple attempts from same source, some bypassed | Isolate agent, investigate |
| High | Successful injection affecting production | Full incident response |
| Critical | Injection leading to data exfiltration or system compromise | SEV-1, full lockdown |

## Immediate Response (0-15 min)

### 1. Isolate Affected Agent

```bash
# Scale affected agent to zero
kubectl scale deployment agent-runtime --replicas=0 -n agent-runtime

# Apply emergency network policy
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-runtime-lockdown
  namespace: agent-runtime
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
EOF
```

### 2. Preserve Evidence

```bash
# Export agent logs
kubectl logs -l app.kubernetes.io/name=agent-runtime --all-containers -n agent-runtime > /tmp/agent-logs-$(date +%s).log

# Export prompt history from Redis
redis-cli -h $REDIS_HOST LRANGE agent:prompts 0 -1 > /tmp/prompt-history-$(date +%s).json

# Export event stream from NATS
nats sub 'agent.>' --all > /tmp/nats-events-$(date +%s).json
```

### 3. Assess Impact

1. Check agent action log for unauthorized operations
2. Review audit trail for data access
3. Check if other agents were affected
4. Determine if user data was accessed or modified

## Containment (15-30 min)

### If Single Agent Affected

1. Rotate agent API keys
2. Reset agent state to last known good checkpoint
3. Update prompt guardrails with new detection patterns
4. Redeploy with enhanced monitoring

### If Multiple Agents Affected

1. Scale all agents to zero
2. Rotate all provider API keys
3. Reset all agent states
4. Deploy updated policy-engine with new rules
5. Gradually restart agents with monitoring

### If Data Exfiltration Suspected

1. Enable audit-only mode on all agents
2. Revoke all active sessions
3. Force password reset for affected users
4. Engage security team for forensic analysis

## Recovery (30-60 min)

1. Deploy updated guardrails
2. Restart agents in monitoring-only mode
3. Validate agent behavior against test suite
4. Gradually restore full autonomy
5. Monitor for 2 hours before declaring resolved

## Post-Incident Actions

1. **Forensic Analysis**
   - Analyze injection technique
   - Identify vulnerability in guardrails
   - Determine if new attack vector

2. **Guardrail Updates**
   - Add new detection patterns to policy-engine
   - Update prompt sanitization rules
   - Enhance output validation

3. **Model Updates**
   - If provider model was exploited, evaluate alternative
   - Update model-eval-service test suite
   - Run regression tests

4. **Documentation**
   - Update threat model
   - Share IOCs with security community
   - Update agent READMEs with new risks

## Prevention

- Regular red-team exercises against agents
- Automated prompt injection testing in CI
- Multi-layer validation (input, processing, output)
- Principle of least privilege for agent capabilities
- Continuous monitoring of agent behavior drift
