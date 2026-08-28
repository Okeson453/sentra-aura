# Notification Service

Routes alerts and operational notifications to the correct channel based on severity and escalation policy.

## Structure

- `src/notification_service/main.py` — FastAPI application
- `src/notification_service/config.py` — Settings
- `src/notification_service/routing/severity_router.py` — Severity-to-channel mapping
- `src/notification_service/routing/escalation_policy.py` — Escalation logic
- `src/notification_service/channels/pagerduty.py` — PagerDuty integration
- `src/notification_service/channels/slack.py` — Slack webhook integration
- `src/notification_service/channels/email.py` — SMTP email integration

## Run

```bash
uvicorn notification_service.main:app --reload
```
