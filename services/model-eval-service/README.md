# Model Evaluation Service

Runs offline evaluation, safety evaluation, quality benchmarks, and drift monitoring for all agents and models.

## Structure

- `src/model_eval_service/main.py` — FastAPI application
- `src/model_eval_service/config.py` — Settings
- `src/model_eval_service/offline_evaluation.py` — Batch eval runner
- `src/model_eval_service/safety_evaluation.py` — Safety/red-team evals
- `src/model_eval_service/quality_benchmark.py` — Quality gate benchmarks
- `src/model_eval_service/drift_monitor.py` — Model drift detection
- `src/model_eval_service/run_offline_eval.py` — CLI entrypoint

## Run

```bash
uvicorn model_eval_service.main:app --reload
```
