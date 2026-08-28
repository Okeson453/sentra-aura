# Runbook: Research Service Outage

## Symptoms
- `/health` returns unhealthy or degraded
- Research jobs stuck in `running` state for > 5 minutes
- Fact-check requests timing out
- Claim extraction returning 500 errors
- PII filter blocking all content (false positives)
- Provider Gateway unreachable from Research Service

## Impact
- Agents cannot perform research, fact-checking, or claim extraction
- Content strategy and scripting workflows stall
- Risk of unverified claims entering production content
- Potential PII leakage if filter is bypassed or disabled

## Immediate Response (0–5 min)

1. **Check service health**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" https://research-service.sentra-aura.dev/health
   curl -H "Authorization: Bearer $TOKEN" https://research-service.sentra-aura.dev/ready
   ```

2. **Check Provider Gateway connectivity**
   ```bash
   kubectl exec -n sentra-aura deployment/research-service -- \
     curl -s http://provider-gateway:8000/health
   ```
   If Provider Gateway is down, follow the Provider Gateway outage runbook first.

3. **Check job queue depth**
   ```bash
   kubectl logs -n sentra-aura deployment/research-service --tail=200 | grep -i "job\|timeout\|error"
   ```

4. **Check PII filter status**
   ```bash
   kubectl logs -n sentra-aura deployment/research-service --tail=100 | grep -i "pii\|blocked\|redacted"
   ```
   If PII filter is blocking legitimate content, check `PII_FILTER_STRICTNESS` env var.

## Short-Term Mitigation (5–30 min)

1. **Restart stuck jobs**
   If jobs are stuck due to Provider Gateway timeouts, restart the Research Service pods:
   ```bash
   kubectl rollout restart deployment/research-service -n sentra-aura
   ```

2. **Temporarily reduce research depth**
   Set `DEFAULT_RESEARCH_DEPTH=quick` to reduce search scope and load:
   ```bash
   kubectl set env deployment/research-service DEFAULT_RESEARCH_DEPTH=quick -n sentra-aura
   ```

3. **If PII filter is causing false positives**
   - DO NOT disable PII filtering in production
   - Instead, lower strictness to `medium`:
     ```bash
     kubectl set env deployment/research-service PII_FILTER_STRICTNESS=medium -n sentra-aura
     ```
   - Monitor audit logs for any missed PII

4. **Scale horizontally if under load**
   ```bash
   kubectl scale deployment/research-service -n sentra-aura --replicas=4
   ```

5. **If claim extraction is failing**
   - Check if the LLM provider (via Provider Gateway) is responding
   - Fall back to pattern-only extraction by setting `CLAIM_EXTRACTION_LLM_ENABLED=false`

## Root Cause Analysis (30 min–2 hr)

1. **Provider Gateway failure**
   - Research Service depends on Provider Gateway for search (SerpAPI, Tavily)
   - Check Provider Gateway health and circuit breaker states

2. **Database/Redis connectivity**
   - If using persistent job storage, check connection strings
   - Verify network policies allow egress to database and Redis

3. **Memory exhaustion**
   - Large research queries with many sources can OOM the service
   - Check pod memory usage:
     ```bash
     kubectl top pods -n sentra-aura -l app=research-service
     ```

4. **Rate limiting**
   - SerpAPI and Tavily have strict rate limits
   - Check if `RATE_LIMIT_RPM` is being exceeded
   - Review Provider Gateway cost tracker for search spend spikes

5. **PII filter regression**
   - Check if a recent deployment changed filter patterns
   - Review audit log for unexpected blocking rates

## Post-Incident

1. Review all blocked content during the outage to ensure no PII leaked
2. Update fallback research depth defaults if quick mode proved sufficient
3. File post-mortem if any unverified claims entered production content
4. Review and tune PII filter strictness based on false positive rate

## Escalation
- L1: Research Service on-call
- L2: SentraAura Platform Engineering
- L3: Security team (if PII leakage suspected)
