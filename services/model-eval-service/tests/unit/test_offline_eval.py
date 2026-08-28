"""Unit tests for offline evaluation."""
from __future__ import annotations

import pytest

from model_eval_service.offline_evaluation import OfflineEvaluator, EvalResult


@pytest.mark.asyncio
async def test_evaluate_agent_missing_dataset():
    evaluator = OfflineEvaluator(
        provider_gateway_url="http://localhost:8000",
        dataset_base_path="/nonexistent",
    )
    with pytest.raises(FileNotFoundError):
        await evaluator.evaluate_agent("test-agent", "1.0.0")
    await evaluator.close()


@pytest.mark.asyncio
async def test_evaluate_agent_with_mock_dataset(tmp_path):
    import json
    dataset_dir = tmp_path / "test-agent" / "v1"
    dataset_dir.mkdir(parents=True)
    dataset_file = dataset_dir / "dataset.jsonl"
    cases = [
        {"id": "c1", "input": "test", "expected_output": "ok", "expected_score": 0.90, "estimated_cost_usd": 0.01},
        {"id": "c2", "input": "test2", "expected_output": "ok2", "expected_score": 0.80, "estimated_cost_usd": 0.01},
    ]
    with open(dataset_file, "w") as f:
        for case in cases:
            f.write(json.dumps(case) + "\n")

    evaluator = OfflineEvaluator(
        provider_gateway_url="http://localhost:8000",
        dataset_base_path=str(tmp_path),
    )
    result = await evaluator.evaluate_agent("test-agent", "1.0.0")
    assert isinstance(result, EvalResult)
    assert result.total_cases == 2
    assert result.passed_cases >= 0
    assert result.avg_score > 0
    await evaluator.close()
