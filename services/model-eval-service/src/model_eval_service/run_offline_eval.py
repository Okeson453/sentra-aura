"""CLI entrypoint for running offline evaluations."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

from model_eval_service.config import config
from model_eval_service.drift_monitor import DriftMonitor
from model_eval_service.offline_evaluation import OfflineEvaluator
from model_eval_service.quality_benchmark import QualityBenchmark
from model_eval_service.safety_evaluation import SafetyEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def run_eval(
    agent_id: str,
    version: str,
    dataset_version: str = "v1",
    output_path: str | None = None,
) -> dict:
    """Run the full evaluation suite for an agent."""
    logger.info("Starting evaluation for %s v%s (dataset %s)", agent_id, version, dataset_version)

    evaluator = OfflineEvaluator(
        provider_gateway_url=config.provider_gateway_url,
        dataset_base_path=config.eval_dataset_path,
    )
    safety = SafetyEvaluator(provider_gateway_url=config.provider_gateway_url)
    benchmark = QualityBenchmark()
    drift = DriftMonitor(drift_threshold=config.drift_threshold)

    try:
        # 1. Offline evaluation
        offline_result = await evaluator.evaluate_agent(agent_id, version, dataset_version)

        # 2. Safety evaluation
        safety_result = await safety.evaluate_safety(agent_id, version)

        # 3. Quality benchmarks (placeholder cases)
        benchmark_results = await benchmark.run_all_benchmarks(agent_id, version, {})

        # 4. Drift detection (if baseline exists)
        drift_report = None
        try:
            scores = [d["score"] for d in offline_result.details if "score" in d]
            if scores:
                drift.set_baseline(agent_id, version, scores)
                drift_report = drift.detect_drift(agent_id, version, scores)
        except Exception as exc:
            logger.warning("Drift detection skipped: %s", exc)

        result = {
            "agent_id": agent_id,
            "version": version,
            "dataset_version": dataset_version,
            "evaluated_at": datetime.utcnow().isoformat(),
            "offline": {
                "total_cases": offline_result.total_cases,
                "passed_cases": offline_result.passed_cases,
                "failed_cases": offline_result.failed_cases,
                "avg_score": offline_result.avg_score,
                "median_score": offline_result.median_score,
                "p95_latency_ms": offline_result.p95_latency_ms,
                "cost_usd": offline_result.cost_usd,
            },
            "safety": {
                "passed": safety_result.passed,
                "score": safety_result.score,
                "violations": [v for v in safety_result.violations],
            },
            "benchmarks": [
                {
                    "name": b.benchmark_name,
                    "score": b.score,
                    "passed": b.passed,
                    "metrics": b.metrics,
                }
                for b in benchmark_results
            ],
            "drift": {
                "detected": drift_report.drift_detected if drift_report else None,
                "score": drift_report.drift_score if drift_report else None,
                "recommended_action": drift_report.recommended_action if drift_report else None,
            } if drift_report else None,
        }

        if output_path:
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            logger.info("Results written to %s", output_path)

        return result
    finally:
        await evaluator.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline evaluation for a SentraAura agent")
    parser.add_argument("--agent-id", required=True, help="Agent identifier")
    parser.add_argument("--version", required=True, help="Agent version")
    parser.add_argument("--dataset-version", default="v1", help="Dataset version tag")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    result = asyncio.run(run_eval(args.agent_id, args.version, args.dataset_version, args.output))
    print(json.dumps(result, indent=2))
    return 0 if result["offline"]["avg_score"] >= config.min_eval_score_threshold else 1


if __name__ == "__main__":
    sys.exit(main())
