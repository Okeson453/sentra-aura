# SentraAura Remediation Ledger

Authoritative status only — never trust PRODUCTION_* self-attestation docs.

## Closed on main (evidence-backed)

### Phase 0–1 core
- P0-04..P0-09, P1-01, P1-02, P1-03, P1-04, P1-05, P1-07, P2-03, P3-02 — prior commits

### Design-gap remediation
- **SERVICE_OWNERS.md** — Backend §23.12 ownership matrix (`095eb36`)
- **Argo Rollouts + KEDA** — templates + **values.yaml progressiveDelivery + autoscaling.keda defaults**
- **Bitemporal ContentEdge** — `valid_from` / `valid_to` / `superseded_by` (Architecture §57) (`c754139`)
- **Media encode path** — worker runs `process_job` when `source_path` + EDL present; fail-closed without inputs (`4b5386b`)
- **ClipScore policy weights** — `CLIP_SCORE_WEIGHTS_JSON` on detect (`5a51f0c`, `c3e7465`)
- **Asset-store signed URL after encode** — ORM + Alembic 0002; worker upload; `GET /{asset_id}/signed-url`; clipping forwards inputs (`70c4c2d`)
- **P2-04 utcnow sweep** — production paths use `datetime.now(timezone.utc)` / lambda Column defaults across services + agent-contracts + asset-store base models

## Explicitly open / deferred

| ID | Status |
|----|--------|
| **P1-08** Human Control Plane UI | **REQUIRES MANUAL ACTION** — frontend/product (**out of scope**) |
| Part III §53–§56, §58–§63 | Deferred (streaming, feature store, multimodal, synthetic sim, …) |
| Full Sentence-BERT ClipScore | Deferred — heuristic scores + weight override in place |

## Regression evidence

```
pytest publishing + clipping-engine + media-renderer → 20 passed
```
