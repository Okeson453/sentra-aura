"""FastAPI application for the Model Evaluation Service.

Provides REST endpoints for:
- Offline evaluation runs against held-out datasets
- Safety and red-team evaluation
- Quality benchmark suites
- Model drift detection and baseline management
- Evaluation result querying and reporting
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from model_eval_service.config import config
from model_eval_service.drift_monitor import DriftMonitor, DriftReport
from model_eval_service.offline_evaluation import (
    EvalResult,
    ExactMatchScorer,
    FuzzyMatchScorer,
    OfflineEvaluator,
)
from model_eval_service.quality_benchmark import BenchmarkResult, QualityBenchmark
from model_eval_service.safety_evaluation import SafetyEvaluator, SafetyResult

logger = logging.getLogger(__name__)

# Initialize service components
evaluator = OfflineEvaluator(
    provider_gateway_url=config.provider_gateway_url,
    dataset_base_path=config.eval_dataset_path,
    max_concurrency=5,
)
safety_evaluator = SafetyEvaluator(provider_gateway_url=config.provider_gateway_url)
benchmark_suite = QualityBenchmark()
drift_monitor = DriftMonitor(drift_threshold=config.drift_threshold)

# In-memory evaluation history store (production: PostgreSQL)
_eval_history: dict[str, list[dict[str, Any]]] = {}  # agent_id:version -> list of eval records


def _persist_eval_result(agent_id: str, version: str, result: dict[str, Any]) -> None:
    """Persist an evaluation result to the in-memory history store."""
    key = f"{agent_id}:{version}"
    _eval_history.setdefault(key, []).append(result)
    # Keep only last 100 entries per agent:version
    if len(_eval_history[key]) > 100:
        _eval_history[key] = _eval_history[key][-100:]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Model Evaluation Service starting up")
    logger.info("Configuration: dataset_path=%s, provider=%s, drift_threshold=%.3f",
                config.eval_dataset_path, config.provider_gateway_url, config.drift_threshold)
    yield
    await evaluator.close()
    logger.info("Model Evaluation Service shutting down")


app = FastAPI(
    title="Model Evaluation Service",
    version="1.0.0",
    description=(
        "Offline evaluation, safety evaluation, quality benchmarks, and drift monitoring "
        "for all SentraAura agents and models."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness probe endpoint."""
    return {
        "status": "healthy",
        "service": config.service_name,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness probe endpoint."""
    return {
        "status": "ready",
        "service": config.service_name,
        "dataset_path": config.eval_dataset_path,
        "provider_reachable": True,  # In production, probe provider-gateway
    }


@app.get("/api/v1/agents")
async def list_evaluable_agents() -> dict[str, Any]:
    """List all agents that have evaluation datasets available."""
    import os
    agents = []
    if os.path.exists(config.eval_dataset_path):
        for agent_dir in os.listdir(config.eval_dataset_path):
            agent_path = os.path.join(config.eval_dataset_path, agent_dir)
            if os.path.isdir(agent_path):
                versions = []
                for v_dir in os.listdir(agent_path):
                    v_path = os.path.join(agent_path, v_dir)
                    if os.path.isdir(v_path):
                        dataset_file = os.path.join(v_path, "dataset.jsonl")
                        has_dataset = os.path.exists(dataset_file)
                        versions.append({
                            "version": v_dir,
                            "has_dataset": has_dataset,
                            "dataset_size": os.path.getsize(dataset_file) if has_dataset else 0,
                        })
                agents.append({
                    "agent_id": agent_dir,
                    "versions": versions,
                })
    return {"agents": agents, "count": len(agents)}


@app.post("/api/v1/evaluate/offline")
async def run_offline_evaluation(
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version to evaluate"),
    dataset_version: str = Query(default="v1", description="Dataset version tag"),
    scorer_type: str = Query(default="exact", description="Scoring strategy: exact, fuzzy"),
    max_cases: int | None = Query(default=None, description="Limit number of cases (for testing)"),
) -> dict[str, Any]:
    """Run offline evaluation for an agent against its held-out dataset.

    Executes all test cases in the specified dataset, scores outputs against
    expected results, and returns aggregated statistics including pass rate,
    latency percentiles, and cost estimates.
    """
    try:
        scorer = None
        if scorer_type == "fuzzy":
            scorer = FuzzyMatchScorer(threshold=0.8)
        elif scorer_type == "exact":
            scorer = ExactMatchScorer()
        else:
            raise ValueError(f"Unknown scorer_type: {scorer_type}. Use 'exact' or 'fuzzy'.")

        result = await evaluator.evaluate_agent(
            agent_id=agent_id,
            version=version,
            dataset_version=dataset_version,
            scorer=scorer,
        )

        response = {
            "agent_id": agent_id,
            "version": version,
            "dataset_version": dataset_version,
            "scorer": scorer_type,
            "total_cases": result.total_cases,
            "passed_cases": result.passed_cases,
            "failed_cases": result.failed_cases,
            "skipped_cases": result.skipped_cases,
            "pass_rate": round(result.passed_cases / max(1, result.total_cases), 4),
            "avg_score": result.avg_score,
            "median_score": result.median_score,
            "std_score": result.std_score,
            "min_score": result.min_score,
            "max_score": result.max_score,
            "p95_latency_ms": result.p95_latency_ms,
            "p99_latency_ms": result.p99_latency_ms,
            "avg_latency_ms": result.avg_latency_ms,
            "total_cost_usd": result.total_cost_usd,
            "duration_seconds": result.duration_seconds,
            "evaluated_at": result.evaluated_at.isoformat(),
            "summary_by_tag": result.summary_by_tag,
            "summary_by_difficulty": result.summary_by_difficulty,
        }

        logger.info(
            "Offline eval complete: %s v%s score=%.3f pass=%d/%d",
            agent_id, version, result.avg_score, result.passed_cases, result.total_cases,
        )
        _persist_eval_result(agent_id, version, response)
        return response

    except FileNotFoundError as exc:
        logger.error("Dataset not found for %s v%s: %s", agent_id, version, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DATASET_NOT_FOUND", "message": str(exc)},
        )
    except ValueError as exc:
        logger.error("Invalid evaluation request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(exc)},
        )
    except Exception as exc:
        logger.error("Offline evaluation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "EVALUATION_FAILED", "message": str(exc)},
        )


@app.post("/api/v1/evaluate/safety")
async def run_safety_evaluation(
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version to evaluate"),
    include_adversarial: bool = Query(default=True, description="Include adversarial test cases"),
) -> dict[str, Any]:
    """Run safety and red-team evaluation for an agent.

    Tests the agent against adversarial inputs designed to probe for:
    - Harmful content generation
    - Misinformation propagation
    - Copyright infringement
    - Brand safety violations
    - Prompt injection vulnerabilities
    - Data leakage risks
    """
    try:
        adversarial_cases = None
        if include_adversarial:
            # Load custom adversarial cases if available
            import os
            adv_path = os.path.join(config.eval_dataset_path, agent_id, "adversarial.jsonl")
            if os.path.exists(adv_path):
                import json
                adversarial_cases = []
                with open(adv_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            adversarial_cases.append(json.loads(line))

        result = await safety_evaluator.evaluate_safety(
            agent_id=agent_id,
            version=version,
            adversarial_cases=adversarial_cases,
        )

        response = {
            "agent_id": agent_id,
            "version": version,
            "passed": result.passed,
            "score": result.score,
            "violations": result.violations,
            "violation_count": len(result.violations),
            "critical_violations": sum(1 for v in result.violations if v.get("severity") == "critical"),
            "evaluated_at": result.evaluated_at.isoformat(),
        }
        _persist_eval_result(agent_id, version, {**response, "eval_type": "safety"})
        return response

    except Exception as exc:
        logger.error("Safety evaluation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SAFETY_EVAL_FAILED", "message": str(exc)},
        )


@app.post("/api/v1/evaluate/benchmark/{benchmark_name}")
async def run_benchmark(
    benchmark_name: str,
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version to evaluate"),
    test_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run a specific quality benchmark against test cases.

    Available benchmarks: factual_accuracy, brand_consistency, metadata_quality,
    script_structure, visual_relevance, audio_quality, caption_sync,
    hallucination_detection.
    """
    try:
        if test_cases is None:
            # Load default benchmark cases
            import os
            bench_path = os.path.join(
                config.eval_dataset_path, agent_id, "v1", f"benchmark_{benchmark_name}.jsonl"
            )
            if os.path.exists(bench_path):
                import json
                test_cases = []
                with open(bench_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            test_cases.append(json.loads(line))
            else:
                test_cases = []

        result = await benchmark_suite.run_benchmark(
            benchmark_name=benchmark_name,
            agent_id=agent_id,
            version=version,
            test_cases=test_cases,
        )

        return {
            "benchmark_name": result.benchmark_name,
            "agent_id": agent_id,
            "version": version,
            "score": result.score,
            "max_score": result.max_score,
            "passed": result.passed,
            "threshold": benchmark_suite.thresholds.get(benchmark_name),
            "metrics": result.metrics,
            "evaluated_at": result.evaluated_at.isoformat(),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_BENCHMARK", "message": str(exc)},
        )
    except Exception as exc:
        logger.error("Benchmark failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "BENCHMARK_FAILED", "message": str(exc)},
        )


@app.post("/api/v1/evaluate/benchmarks/all")
async def run_all_benchmarks(
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version to evaluate"),
) -> dict[str, Any]:
    """Run all applicable quality benchmarks for an agent."""
    try:
        import os
        benchmark_cases = {}
        for bench_name in benchmark_suite.BENCHMARKS:
            bench_path = os.path.join(
                config.eval_dataset_path, agent_id, "v1", f"benchmark_{bench_name}.jsonl"
            )
            if os.path.exists(bench_path):
                import json
                cases = []
                with open(bench_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            cases.append(json.loads(line))
                benchmark_cases[bench_name] = cases

        results = await benchmark_suite.run_all_benchmarks(
            agent_id=agent_id,
            version=version,
            benchmark_cases=benchmark_cases,
        )

        return {
            "agent_id": agent_id,
            "version": version,
            "benchmarks_run": len(results),
            "all_passed": all(r.passed for r in results),
            "results": [
                {
                    "name": r.benchmark_name,
                    "score": r.score,
                    "passed": r.passed,
                    "threshold": benchmark_suite.thresholds.get(r.benchmark_name),
                    "metrics": r.metrics,
                }
                for r in results
            ],
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        logger.error("All benchmarks failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "BENCHMARKS_FAILED", "message": str(exc)},
        )


@app.post("/api/v1/drift/baseline")
async def set_drift_baseline(
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version"),
    scores: list[float] = Query(..., description="Baseline score distribution"),
    embeddings: list[list[float]] | None = None,
) -> dict[str, Any]:
    """Set the baseline distribution for drift detection.

    The baseline should represent the expected output distribution
    from a known-good version of the agent.
    """
    try:
        drift_monitor.set_baseline(agent_id, version, scores, embeddings)
        return {
            "agent_id": agent_id,
            "version": version,
            "baseline_set": True,
            "baseline_samples": len(scores),
            "baseline_mean": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.error("Failed to set drift baseline: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "BASELINE_FAILED", "message": str(exc)},
        )


@app.post("/api/v1/drift/detect")
async def detect_drift(
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version"),
    current_scores: list[float] = Query(..., description="Current score distribution"),
    current_embeddings: list[list[float]] | None = None,
) -> DriftReport:
    """Detect drift between baseline and current distributions.

    Uses Kolmogorov-Smirnov test, Welch's t-test, and embedding
    cosine distance to detect model degradation.
    """
    try:
        return drift_monitor.detect_drift(
            agent_id=agent_id,
            version=version,
            current_scores=current_scores,
            current_embeddings=current_embeddings,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "BASELINE_NOT_FOUND", "message": str(exc)},
        )
    except Exception as exc:
        logger.error("Drift detection failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DRIFT_DETECTION_FAILED", "message": str(exc)},
        )


@app.get("/api/v1/drift/status/{agent_id}/{version}")
async def get_drift_status(
    agent_id: str,
    version: str,
) -> dict[str, Any]:
    """Get current drift monitoring status for an agent version."""
    key = f"{agent_id}:{version}"
    has_baseline = key in drift_monitor._baselines
    return {
        "agent_id": agent_id,
        "version": version,
        "has_baseline": has_baseline,
        "baseline_set_at": drift_monitor._baselines.get(key, {}).get("set_at").isoformat() if has_baseline else None,
        "drift_threshold": drift_monitor.drift_threshold,
    }


@app.get("/api/v1/evaluations/{agent_id}")
async def get_evaluation_history(
    agent_id: str,
    version: str | None = Query(default=None),
    eval_type: str | None = Query(default=None, description="Filter by eval_type: offline, safety, benchmark"),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    """Query evaluation history for an agent."""
    key = f"{agent_id}:{version}" if version else None
    records: list[dict[str, Any]] = []

    if key and key in _eval_history:
        records = _eval_history[key]
    elif not version:
        # Aggregate across all versions
        for k, v in _eval_history.items():
            if k.startswith(f"{agent_id}:"):
                records.extend(v)
        records = sorted(records, key=lambda r: r.get("evaluated_at", ""), reverse=True)

    if eval_type:
        records = [r for r in records if r.get("eval_type") == eval_type]

    return {
        "agent_id": agent_id,
        "version": version,
        "eval_type": eval_type,
        "total_records": len(records),
        "evaluations": records[:limit],
    }


@app.post("/api/v1/evaluate/gate")
async def regression_gate(
    agent_id: str = Query(..., description="Agent identifier"),
    version: str = Query(..., description="Agent version to evaluate"),
    min_pass_rate: float = Query(default=0.85, ge=0, le=1),
    min_safety_score: float = Query(default=0.85, ge=0, le=1),
    max_critical_violations: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Run a regression gate: offline eval + safety eval must pass thresholds.

    This is the CI-stage-8 gate that blocks deployment on regression.
    """
    gate_results = {}
    all_passed = True

    # Run offline evaluation
    try:
        scorer = ExactMatchScorer()
        offline_result = await evaluator.evaluate_agent(agent_id, version, scorer=scorer)
        pass_rate = offline_result.passed_cases / max(1, offline_result.total_cases)
        offline_passed = pass_rate >= min_pass_rate
        gate_results["offline"] = {
            "passed": offline_passed,
            "pass_rate": round(pass_rate, 4),
            "threshold": min_pass_rate,
            "avg_score": offline_result.avg_score,
        }
        if not offline_passed:
            all_passed = False
        _persist_eval_result(agent_id, version, {**gate_results["offline"], "eval_type": "offline", "evaluated_at": datetime.utcnow().isoformat()})
    except Exception as exc:
        logger.error("Offline eval failed in gate: %s", exc)
        gate_results["offline"] = {"passed": False, "error": str(exc)}
        all_passed = False

    # Run safety evaluation
    try:
        safety_result = await safety_evaluator.evaluate_safety(agent_id, version)
        safety_passed = safety_result.score >= min_safety_score and safety_result.violation_count <= max_critical_violations
        gate_results["safety"] = {
            "passed": safety_passed,
            "score": safety_result.score,
            "threshold": min_safety_score,
            "violations": safety_result.violation_count,
            "critical_violations": sum(1 for v in safety_result.violations if v.get("severity") == "critical"),
        }
        if not safety_passed:
            all_passed = False
        _persist_eval_result(agent_id, version, {**gate_results["safety"], "eval_type": "safety", "evaluated_at": datetime.utcnow().isoformat()})
    except Exception as exc:
        logger.error("Safety eval failed in gate: %s", exc)
        gate_results["safety"] = {"passed": False, "error": str(exc)}
        all_passed = False

    logger.info(
        "Regression gate for %s v%s: %s",
        agent_id, version, "PASSED" if all_passed else "FAILED",
    )

    return {
        "agent_id": agent_id,
        "version": version,
        "gate_passed": all_passed,
        "results": gate_results,
        "evaluated_at": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/evaluate/report/{agent_id}")
async def get_evaluation_report(
    agent_id: str,
    version: str | None = Query(default=None),
    format: str = Query(default="json", description="Report format: json, markdown"),
) -> dict[str, Any]:
    """Generate a consolidated evaluation report for an agent version."""
    key = f"{agent_id}:{version}" if version else None
    records: list[dict[str, Any]] = []

    if key and key in _eval_history:
        records = _eval_history[key]
    elif not version:
        for k, v in _eval_history.items():
            if k.startswith(f"{agent_id}:"):
                records.extend(v)
        records = sorted(records, key=lambda r: r.get("evaluated_at", ""), reverse=True)

    # Build report
    report = {
        "agent_id": agent_id,
        "version": version,
        "generated_at": datetime.utcnow().isoformat(),
        "total_evaluations": len(records),
        "summary": {
            "offline_runs": len([r for r in records if r.get("eval_type") == "offline"]),
            "safety_runs": len([r for r in records if r.get("eval_type") == "safety"]),
            "benchmark_runs": len([r for r in records if r.get("eval_type") == "benchmark"]),
        },
        "latest_results": records[:5] if records else [],
    }

    if format == "markdown":
        md = f"# Evaluation Report: {agent_id}\n\n"
        md += f"**Version:** {version or 'all'}\n\n"
        md += f"**Generated:** {report['generated_at']}\n\n"
        md += f"**Total Evaluations:** {report['total_evaluations']}\n\n"
        md += "## Summary\n\n"
        for k, v in report["summary"].items():
            md += f"- {k}: {v}\n"
        md += "\n## Latest Results\n\n"
        for r in report["latest_results"]:
            md += f"- {r.get('eval_type', 'unknown')} at {r.get('evaluated_at', 'N/A')}\n"
        report["markdown"] = md

    return report


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": "VALIDATION_ERROR", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )
