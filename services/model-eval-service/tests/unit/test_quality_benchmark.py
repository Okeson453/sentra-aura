"""Unit tests for quality benchmark suite."""
from __future__ import annotations

import pytest

from model_eval_service.quality_benchmark import QualityBenchmark, BenchmarkResult


def test_benchmark_initialization():
    bench = QualityBenchmark()
    assert "factual_accuracy" in bench.BENCHMARKS
    assert "hallucination_detection" in bench.BENCHMARKS
    assert bench.thresholds["factual_accuracy"] == 0.90


@pytest.mark.asyncio
async def test_run_benchmark():
    bench = QualityBenchmark()
    cases = [
        {"expected_score": 0.95},
        {"expected_score": 0.88},
        {"expected_score": 0.92},
    ]
    result = await bench.run_benchmark("factual_accuracy", "test-agent", "1.0.0", cases)
    assert isinstance(result, BenchmarkResult)
    assert result.benchmark_name == "factual_accuracy"
    assert result.passed is True
    assert result.score > 0.90


@pytest.mark.asyncio
async def test_run_benchmark_failure():
    bench = QualityBenchmark()
    cases = [
        {"expected_score": 0.50},
        {"expected_score": 0.60},
    ]
    result = await bench.run_benchmark("factual_accuracy", "test-agent", "1.0.0", cases)
    assert result.passed is False
    assert result.score < 0.90


@pytest.mark.asyncio
async def test_run_all_benchmarks():
    bench = QualityBenchmark()
    benchmark_cases = {
        "factual_accuracy": [{"expected_score": 0.95}],
        "brand_consistency": [{"expected_score": 0.90}],
    }
    results = await bench.run_all_benchmarks("test-agent", "1.0.0", benchmark_cases)
    assert len(results) == 2


def test_unknown_benchmark():
    bench = QualityBenchmark()
    with pytest.raises(ValueError, match="Unknown benchmark"):
        import asyncio
        asyncio.run(bench.run_benchmark("unknown", "test", "1.0", []))
