# Notification Storm

## Symptoms

PagerDuty and Slack channels flooded with duplicate alerts. On-call engineer overwhelmed.

## Impact

Alert fatigue, missed critical pages, degraded incident response time.

## Detection

Alert: `notification_rate > 100/min` or `duplicate_alert_ratio > 30%`.

## Mitigation

1. Enable circuit breaker on notification channels. 2. Deduplicate alerts by fingerprint within 5-minute window. 3. Escalate to secondary channel only if primary channel is throttled.

## Recovery

Gradually re-enable channels once root cause (e.g., flapping service) is resolved.

## Post-Incident

Review alert thresholds. Tighten deduplication window. Add rate-limiting per-channel.
