# Quota Broker

Go service that manages YouTube API quota allocation and rate governance.

## Structure

- `cmd/broker/main.go` — Service entrypoint
- `internal/youtube/quota_tracker.go` — Quota consumption tracking
- `internal/youtube/unit_costs.go` — Per-operation cost definitions
- `internal/queue/priority_queue.go` — Priority-ordered request queue
- `internal/api/handlers.go` — HTTP API handlers

## API

- `POST /allocate` — Allocate quota for a batch of operations
- `GET /status` — Current quota usage and remaining budget
- `POST /release` — Release unused quota allocation

## Run

```bash
go run cmd/broker/main.go
```
