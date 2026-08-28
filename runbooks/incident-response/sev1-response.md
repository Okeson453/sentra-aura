# SentraAura — SEV-1 Incident Response Runbook

## Classification

| Field | Value |
|-------|-------|
| Severity | SEV-1 (Critical) |
| Response Time | < 15 minutes |
| Escalation | Immediate paging |
| DRI (Directly Responsible Individual) | On-call SRE |

## Trigger Conditions

- Complete service outage (all endpoints returning 5xx)
- Data loss or corruption detected
- Security breach or unauthorized access confirmed
- RCE or prompt injection affecting production
- Cost spike > 10x baseline sustained for > 5 minutes
- Autonomous agent executing harmful actions

## Response Steps

### 1. Acknowledge (0-5 min)

1. Acknowledge the page in PagerDuty/Opsgenie
2. Join the incident Slack channel: `#incidents-sev1`
3. Declare the incident in the incident management system
4. Post initial status update: "SEV-1 declared for [service]. Investigating."

### 2. Assess (5-10 min)

1. Check the service health dashboard: https://grafana.sentra-aura.io/d/health
2. Review recent deployments: `kubectl get deployments --all-namespaces -l sentra.io/part-of=sentra-aura`
3. Check error rates in Prometheus:
   ```
   rate(http_requests_total{status=~"5.."}[5m])
   ```
4. Review logs in Loki:
   ```
   {app="sentra-aura"} |= "ERROR" | json
   ```
5. Check infrastructure status in AWS Console
6. Determine scope: single service, multiple services, or full platform

### 3. Mitigate (10-15 min)

**If single service failure:**
1. Attempt pod restart: `kubectl rollout restart deployment/<service> -n <namespace>`
2. If restart fails, scale to zero and back: `kubectl scale deployment/<service> --replicas=0 && kubectl scale deployment/<service> --replicas=3`
3. Check if recent deployment caused issue: `kubectl rollout history deployment/<service>`
4. If needed, rollback: `kubectl rollout undo deployment/<service>`

**If database issue:**
1. Check RDS dashboard for connection limits, CPU, memory
2. Run `SHOW pg_stat_activity;` to identify blocking queries
3. If primary is failing, initiate failover (see postgresql-failover.md)
4. Enable read-only mode on control-plane-api if writes are failing

**If security incident:**
1. Isolate affected services: apply deny-all network policies
2. Rotate all potentially compromised secrets
3. Preserve logs for forensic analysis
4. Engage security team immediately

**If cost spike:**
1. Identify the source service via cost attribution tags
2. Apply emergency rate limiting via quota-broker
3. Scale down non-critical services
4. Contact cloud provider support if needed

### 4. Communicate (Ongoing)

- Every 15 minutes post status update in `#incidents-sev1`
- Update status page if customer-facing impact
- Notify stakeholders via email for sustained > 30 min incidents
- Prepare post-mortem document within 24 hours

### 5. Resolve

1. Confirm all health checks passing
2. Monitor for 30 minutes after fix
3. Update incident status to "Resolved"
4. Schedule post-mortem within 24 hours
5. Create follow-up tickets for preventive measures

## Escalation Path

```
On-call SRE (15 min) → Engineering Manager (30 min) → CTO (1 hour) → CEO (2 hours)
```

## Key Commands

```bash
# Get all service statuses
kubectl get pods --all-namespaces -l sentra.io/part-of=sentra-aura

# Check recent events
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | tail -50

# Check logs for a specific service
kubectl logs -l app.kubernetes.io/name=<service> --tail=100 -n <namespace>

# Check HPA status
kubectl get hpa --all-namespaces

# Check node status
kubectl get nodes -o wide

# Check resource usage
kubectl top pods --all-namespaces
```

## Contacts

| Role | Contact |
|------|---------|
| On-call SRE | PagerDuty rotation |
| Engineering Manager | #eng-management |
| Security Team | #security-oncall |
| Platform Lead | #platform-team |
| CTO | Direct Slack |
