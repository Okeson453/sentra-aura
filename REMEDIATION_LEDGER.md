# SentraAura Remediation Ledger

Authoritative status only — never trust PRODUCTION_* self-attestation docs.

## Closed on main (evidence-backed)

### Phase 0–1 core
- P0-04..P0-09, P1-01, P1-02, P1-03, P1-04, P1-05, P1-07, P2-03, P3-02 — prior commits

### This cycle (design-gap remediation)
- **SERVICE_OWNERS.md** — Backend §23.12 ownership matrix (`095eb36`)
- **Argo Rollouts + KEDA** — `infra/helm/charts/sentra-service/templates/rollout.yaml` + `scaledobject.yaml` gated by values (`095eb36`)
- **Bitemporal ContentEdge** — `valid_from` / `valid_to` / `superseded_by` (Architecture §57) (`c754139`)
- **Media encode path** — worker runs `process_job` when `source_path` + EDL present; still fail-closed without inputs (`4b5386b`)
- **ClipScore policy weights** — `CLIP_SCORE_WEIGHTS_JSON` / `clip_score_weights_json` on detect (`5a51f0c`, `c3e7465`)

## Explicitly open / deferred

| ID | Status |
|----|--------|
| **P1-08** Human Control Plane UI | **REQUIRES MANUAL ACTION** — frontend/product |
| Part III §53–§56, §58–§63 | Deferred (streaming, feature store, multimodal, synthetic sim, …) |
| Full Sentence-BERT ClipScore | Deferred — heuristic scores + weight override in place |
| Asset-store signed URL after encode | Next: upload `file://` artifacts to asset-store |

## Regression evidence

```
pytest publishing + media-renderer + clipping-engine + event-bus → 24 passed
```
