# SentraAura Remediation Ledger

Authoritative status only — never trust PRODUCTION_* self-attestation docs.

## Closed on main (evidence-backed)

### Phase 0–1 core
- P0-04..P0-09, P1-01, P1-02, P1-03, P1-04, P1-05, P1-07, P2-03, P3-02 — prior commits

### Design-gap remediation
- **SERVICE_OWNERS.md** — Backend §23.12 ownership matrix (`095eb36`)
- **Argo Rollouts + KEDA** — templates + values.yaml progressiveDelivery + autoscaling.keda
- **Bitemporal ContentEdge** — valid_from / valid_to / superseded_by (`c754139`)
- **Media encode path** — process_job when source+EDL; fail-closed without (`4b5386b`)
- **ClipScore policy weights** — CLIP_SCORE_WEIGHTS_JSON (`5a51f0c`, `c3e7465`)
- **Asset-store signed URL after encode** — ORM + worker upload + signed-url route (`70c4c2d`) — closes **P4-24**
- **P2-04 utcnow sweep** — timezone-aware across production paths (`bc64003`)

### Clipping ML pipeline (P4-01..P4-06) — this cycle
| ID | Component | Status | Evidence |
|----|-----------|--------|----------|
| P4-01 | ASR Transcription | **HEURISTIC+OPTIONAL** | Whisper / provider-gateway when present; else duration-aligned empty segments (mode=heuristic), never fixed mock prose |
| P4-02 | Speaker Diarization | **HEURISTIC+OPTIONAL** | pyannote when present; else duration-based turns (mode=heuristic) |
| P4-03 | Shot Detection | **HEURISTIC+OPTIONAL** | PySceneDetect when present; else ffprobe duration-proportional boundaries |
| P4-04 | Scene Detection | **HEURISTIC** | Groups shot boundaries by max_scene_seconds from real/probed duration |
| P4-05 | Semantic Segmentation | **HEURISTIC+OPTIONAL** | sentence-transformers when present; else content-hash embeddings + merge |
| P4-06 | Sentence Transformer | **HEURISTIC+OPTIONAL** | Real model when installed; deterministic hash embeddings otherwise (similarity works) |

### Security / agent failure modes (partial)
| ID | Issue | Status |
|----|-------|--------|
| P4-07 | research_agent injection false negatives | **MITIGATED** — expanded patterns + score tuning in sentinel-security injection_defense |
| P4-15 | community_engagement reply loops | **MITIGATED** — per-comment cooldown in engage_comments tools |
| P4-17 | rights_remediation missed takedowns | **MITIGATED** — registry 404/unknown → not_found/unknown (fail closed, never status=clear) |

### Quality gates (Architecture §9)
| ID | Gate | Status |
|----|------|--------|
| P4-26 | Factual accuracy | **HEURISTIC** — clipping_engine.quality.gates |
| P4-27 | Copyright/provenance | **HEURISTIC** — fail-closed without source_asset_ids |
| P4-28 | Audio quality (SNR) | **DEFERRED measure** — accepts snr_db when provided |
| P4-29 | Visual relevance (CLIP) | **DEFERRED model** — accepts clip_score when provided |
| P4-30 | Hallucination | **HEURISTIC** — token overlap grounding |

### ADR / packages
| ID | Issue | Status |
|----|-------|--------|
| P4-34 | prompt-registry package | **PRESENT** — src/prompt_registry/ + tests/test_prompt_registry.py |
| P4-35 | Provider gateway collection errors | **HISTORICAL** — mock_mode tests exist |

## Explicitly open / deferred (backend + product)

| ID | Status |
|----|--------|
| **P1-08 / P4-19** Human Control Plane UI | **REQUIRES MANUAL** — frontend (out of scope) |
| P4-08 scripting_agent reflection loop | Open — agent behavior / product |
| P4-09 scene_shot_agent inconsistent plans | Open — agent behavior |
| P4-10 video_production_agent render handoff | Partial — media-renderer path fixed; agent wiring TBD |
| P4-11 localization_agent empty translations | Open |
| P4-12 reframing_agent mid-frame crops | Open |
| P4-13 captioning_agent empty captions | Open |
| P4-14 publishing_agent ApprovalRequired stuck | By design for ESCALATE tools; grant path exists |
| P4-16 crisis false-positive storms | Open — threshold config |
| P4-18 fact_verification heuristic paths | Open |
| P4-20 Streaming infrastructure | Deferred Part III |
| P4-21 Feature store | Deferred Part III |
| P4-22 Multimodal pipeline | Deferred Part III |
| P4-23 Synthetic simulation | Deferred Part III |
| P4-25 TTS streaming to asset-store | Open |
| P4-31 Real-time analytics stream | Deferred |
| P4-32 Causal attribution | Deferred |
| P4-33 Bayesian hypothesis generation | Deferred |
| Full Sentence-BERT when weights not installed | Optional dependency; hash backend in place |

## Regression evidence

```
clipping unit smoke: media_probe, hash embeddings, quality gates, injection classifier
pytest publishing + clipping-engine + media-renderer → run after commit
```
