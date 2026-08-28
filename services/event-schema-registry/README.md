# Event Schema Registry

Go service that validates event payloads against canonical schemas in `contracts/events/`.

## Structure

- `cmd/registry/main.go` — Service entrypoint
- `internal/schema/validator.go` — JSON Schema validation
- `internal/schema/versioning.go` — Schema version management
- `internal/api/handlers.go` — HTTP API handlers

## API

- `POST /validate` — Validate an event payload against a schema
- `GET /schemas` — List available schemas
- `GET /schemas/{name}/{version}` — Retrieve a specific schema

## Run

```bash
go run cmd/registry/main.go
```
