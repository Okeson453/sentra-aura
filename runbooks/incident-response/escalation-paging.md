# SentraAura — Escalation & Paging Runbook

## Overview

This runbook defines the escalation procedures for incidents that exceed the primary on-call responder's ability to resolve within defined time windows.

## Paging Tiers

### Tier 1: On-call SRE
- **Trigger**: Any SEV-1 or SEV-2 alert
- **Response SLA**: 15 minutes (SEV-1), 30 minutes (SEV-2)
- **Escalation**: Auto-escalate to Tier 2 if not acknowledged

### Tier 2: Engineering Manager + Domain Expert
- **Trigger**: Tier 1 not acknowledged within SLA, or incident > 30 minutes
- **Response SLA**: 30 minutes
- **Escalation**: Auto-escalate to Tier 3 if not acknowledged

### Tier 3: CTO + Security Lead
- **Trigger**: Tier 2 not acknowledged, or incident > 1 hour, or security breach
- **Response SLA**: 1 hour
- **Escalation**: Auto-escalate to Tier 4 if not acknowledged

### Tier 4: Executive Team
- **Trigger**: Tier 3 not acknowledged, or incident > 2 hours, or data breach
- **Response SLA**: 2 hours

## Escalation Matrix

| Incident Type | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|--------------|--------|--------|--------|--------|
| Service Outage | SRE | Eng Mgr | CTO | CEO |
| Data Loss | SRE + DBA | Eng Mgr + Data Eng | CTO | CEO |
| Security Breach | SRE + Security | Security Lead + Eng Mgr | CTO + Legal | CEO + Legal |
| Cost Spike | SRE + FinOps | Eng Mgr + Platform | CTO | CEO |
| Agent Misbehavior | SRE + ML Eng | Eng Mgr + AI Lead | CTO | CEO |

## PagerDuty Configuration

```
Escalation Policy: SentraAura-Critical
- Level 1: On-call SRE (15 min timeout)
- Level 2: Engineering Manager + Domain On-call (30 min timeout)
- Level 3: CTO (1 hour timeout)
- Level 4: CEO (2 hour timeout)

Notification Rules:
- Push notification: Immediate
- SMS: 5 minutes if not acknowledged
- Phone call: 10 minutes if not acknowledged
```

## Manual Escalation Procedure

1. **Assess need**: Determine if current responder needs additional expertise
2. **Identify expert**: Use the escalation matrix to find the right person
3. **Page directly**: Use PagerDuty override or direct phone call
4. **Document**: Record escalation reason and time in incident channel
5. **Handoff**: Brief incoming responder on current state and actions taken

## Communication During Escalation

- Post in `#incidents-sev1` with `@here` for Tier 2+
- Update status page if customer impact
- Prepare executive summary for Tier 3+ escalations
- Maintain incident timeline in real-time

## Post-Escalation Review

Within 48 hours of resolution:
1. Review if escalation was appropriate
2. Identify why initial responder could not resolve
3. Update runbooks or automation to prevent future escalations
4. Adjust paging thresholds if needed
