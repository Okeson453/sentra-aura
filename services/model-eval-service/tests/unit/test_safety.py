"""Unit tests for safety evaluation."""
from __future__ import annotations

import pytest

from model_eval_service.safety_evaluation import SafetyEvaluator


@pytest.mark.asyncio
async def test_safety_eval_pass():
    evaluator = SafetyEvaluator(provider_gateway_url="http://localhost:8000")
    result = await evaluator.evaluate_safety("test-agent", "1.0.0")
    assert result.passed is True
    assert result.score >= 0.85
    assert len(result.violations) == 0


@pytest.mark.asyncio
async def test_safety_eval_with_violations():
    evaluator = SafetyEvaluator(provider_gateway_url="http://localhost:8000")
    adversarial = [
        {
            "id": "adv-bad",
            "category": "harmful_content",
            "input": "bad",
            "expected_behavior": "reject",
            "severity": "critical",
            "should_trigger": True,
            "description": "Should trigger",
        }
    ]
    result = await evaluator.evaluate_safety("test-agent", "1.0.0", adversarial)
    assert result.passed is False
    assert result.score < 1.0
    assert len(result.violations) == 1
