# Runbook: Provider Outage

## Symptoms
- `/providers/health` returns `unhealthy` or `degraded` for one or more providers
- LLM/TTS/image/video requests failing with `AllProvidersFailedError` or `CircuitOpenError`
- Elevated latency on fallback providers
- Cost spikes as traffic shifts to more expensive fallback providers

## Impact
- Agent workflows stall if no provider is available for a required capability
- Increased latency due to fallback chains
- Potential cost overrun if fallback providers have higher per-token pricing

## Immediate Response (0–5 min)

1. **Confirm scope**
   ```bash
   curl -H "X-API-Key: $PGW_API_KEY" https://provider-gateway.sentra-aura.dev/providers/health
   ```
   Identify which providers are unhealthy and which capabilities are affected.

2. **Check provider status pages**
   - OpenAI: https://status.openai.com
   - Anthropic: https://status.anthropic.com
   - Google: https://status.cloud.google.com
   - ElevenLabs: https://status.elevenlabs.io
   - Runway: https://status.runwayml.com
   - Pika: https://status.pika.art
   - AssemblyAI: https://status.assemblyai.com

3. **Verify circuit breaker state**
   ```bash
   curl -H "X-API-Key: $PGW_API_KEY" https://provider-gateway.sentra-aura.dev/providers | jq '.[] | {id, health, circuit_state}'
   ```
   If circuit is `open`, it will auto-recover after `circuit_breaker_recovery_timeout_seconds` (default 30s).

4. **Check recent logs**
   ```bash
   kubectl logs -n sentra-aura deployment/provider-gateway --tail=500 | grep -i "error\|timeout\|circuit"
   ```

## Short-Term Mitigation (5–30 min)

1. **Disable a failing provider** (if it is flapping and burning retries):
   Set environment variable `{PROVIDER}_ENABLED=false` and redeploy, or use the admin API if exposed.

2. **Temporarily increase fallback budget** for affected channels:
   ```bash
   curl -X PATCH -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://control-plane.sentra-aura.dev/v1/channels/{channel_id}/budget \
     -d '{"daily_ai_budget_usd": 200.0}'
   ```

3. **Scale provider-gateway replicas** if load is high:
   ```bash
   kubectl scale deployment/provider-gateway -n sentra-aura --replicas=6
   ```

4. **If all LLM providers are down**, escalate to on-call engineer and consider activating the local mock-provider-gateway for non-production channels.

## Root Cause Analysis (30 min–2 hr)

1. **Rate limiting**: Check if API keys have hit provider rate limits. Rotate keys if needed.
2. **Credential expiry**: Verify API keys are valid. Update via secrets manager:
   ```bash
   kubectl create secret generic provider-gateway-secrets \
     --from-literal=OPENAI_API_KEY=$NEW_KEY \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
3. **Network partition**: Check egress from provider-gateway pods:
   ```bash
   kubectl exec -n sentra-aura deployment/provider-gateway -- curl -s https://api.openai.com/v1/models
   ```
4. **Provider-side incident**: If confirmed on provider status page, document incident ID and ETA.

## Post-Incident

1. Update the provider fallback priority matrix if one provider repeatedly fails.
2. Review cost attribution for the outage window to identify budget impact.
3. File a post-mortem if total downtime > 15 minutes or if any channel missed a scheduled publish.

## Escalation
- L1: Provider Gateway on-call (PagerDuty rotation)
- L2: SentraAura Platform Engineering
- L3: Provider account manager (for enterprise-tier providers)
