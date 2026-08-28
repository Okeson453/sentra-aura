{
  "title": "SentraAura Agent Dashboard",
  "tags": ["sentra-aura", "agent"],
  "timezone": "utc",
  "panels": [
    {
      "title": "Agent Execution Time",
      "type": "graph",
      "targets": [
        {"expr": "histogram_quantile(0.95, rate(agent_execution_duration_seconds_bucket[5m]))"}
      ]
    },
    {
      "title": "Agent Success/Failure Rate",
      "type": "graph",
      "targets": [
        {"expr": "rate(agent_invocations_total{status="success"}[5m])"},
        {"expr": "rate(agent_invocations_total{status="failure"}[5m])"}
      ]
    },
    {
      "title": "Output Quality Scores",
      "type": "graph",
      "targets": [
        {"expr": "agent_output_quality_score"}
      ]
    },
    {
      "title": "Decision Confidence",
      "type": "graph",
      "targets": [
        {"expr": "agent_decision_confidence"}
      ]
    },
    {
      "title": "Token Usage",
      "type": "graph",
      "targets": [
        {"expr": "agent_token_usage_total"}
      ]
    }
  ]
}
