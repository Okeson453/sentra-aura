# API Clients

Generated, typed inter-service HTTP clients for every SentraAura service.

## Generation

```bash
python packages/api-clients/generate.py
```

This wraps `openapi-generator-cli` and produces typed Python clients from each service's OpenAPI spec in `contracts/openapi/`.
