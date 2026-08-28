# Billing Service

SaaS-mode billing: metering, invoicing, and cost attribution per channel/tenant.

## Structure

- `src/billing_service/main.py` — FastAPI application
- `src/billing_service/config.py` — Settings
- `src/billing_service/metering.py` — Usage metering
- `src/billing_service/invoicing.py` — Invoice generation

## Run

```bash
uvicorn billing_service.main:app --reload
```
