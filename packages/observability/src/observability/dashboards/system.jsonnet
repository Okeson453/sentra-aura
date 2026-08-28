{
  "title": "SentraAura System Dashboard",
  "tags": ["sentra-aura", "system"],
  "timezone": "utc",
  "panels": [
    {
      "title": "API Latency (p50/p90/p99)",
      "type": "graph",
      "targets": [
        {"expr": "histogram_quantile(0.5, rate(api_request_duration_seconds_bucket[5m]))"},
        {"expr": "histogram_quantile(0.9, rate(api_request_duration_seconds_bucket[5m]))"},
        {"expr": "histogram_quantile(0.99, rate(api_request_duration_seconds_bucket[5m]))"}
      ]
    },
    {
      "title": "Queue Depth per Channel",
      "type": "graph",
      "targets": [
        {"expr": "sentra_queue_depth"}
      ]
    },
    {
      "title": "Active Workflows",
      "type": "stat",
      "targets": [
        {"expr": "sentra_active_workflows"}
      ]
    },
    {
      "title": "Worker Utilization",
      "type": "graph",
      "targets": [
        {"expr": "sentra_worker_utilization"}
      ]
    },
    {
      "title": "DB Connections",
      "type": "stat",
      "targets": [
        {"expr": "sentra_db_connections_active"}
      ]
    },
    {
      "title": "Cache Hit Ratio",
      "type": "gauge",
      "targets": [
        {"expr": "sentra_cache_hit_ratio"}
      ]
    }
  ]
}
