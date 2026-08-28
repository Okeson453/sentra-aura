{
  "title": "SentraAura Cost Dashboard",
  "tags": ["sentra-aura", "cost"],
  "timezone": "utc",
  "panels": [
    {
      "title": "Cost per Video",
      "type": "graph",
      "targets": [
        {"expr": "sentra_cost_per_video"}
      ]
    },
    {
      "title": "Monthly Spend by Category",
      "type": "piechart",
      "targets": [
        {"expr": "sentra_monthly_spend_by_category"}
      ]
    },
    {
      "title": "Budget vs Actual",
      "type": "graph",
      "targets": [
        {"expr": "sentra_budget_allocated"},
        {"expr": "sentra_budget_spent"}
      ]
    }
  ]
}
