# Service Owners

Human-readable ownership matrix (Backend Spec §23.12). Machine-enforced counterpart: `CODEOWNERS`.

| Service | Owning team | Primary on-call | Slack / channel |
|---|---|---|---|
| control-plane-api | Platform | platform-oncall | #sentra-platform |
| orchestrator | Platform | platform-oncall | #sentra-platform |
| data-ingestion-pipeline | Intelligence | intel-oncall | #sentra-intelligence |
| content-graph-service | Platform | platform-oncall | #sentra-platform |
| policy-engine | Governance | security-oncall | #sentra-security |
| asset-store | Media | media-oncall | #sentra-media |
| agent-runtime | Agents | agents-oncall | #sentra-agents |
| provider-gateway | Platform | platform-oncall | #sentra-platform |
| clipping-engine | Media | media-oncall | #sentra-media |
| media-renderer | Media | media-oncall | #sentra-media |
| research-service | Intelligence | intel-oncall | #sentra-intelligence |
| analytics-ingestion | Analytics | analytics-oncall | #sentra-analytics |
| event-schema-registry | Platform | platform-oncall | #sentra-platform |
| quota-broker | Platform | platform-oncall | #sentra-platform |
| rights-registry-service | Governance | security-oncall | #sentra-security |
| publishing-service | Distribution | dist-oncall | #sentra-distribution |
| notification-service | Platform | platform-oncall | #sentra-platform |
| agent-registry-service | Agents | agents-oncall | #sentra-agents |
| model-eval-service | ML | ml-oncall | #sentra-ml |
| billing-service | Platform (SaaS) | platform-oncall | #sentra-platform |

Escalate Sev-1 via runbooks/incident-response/.
