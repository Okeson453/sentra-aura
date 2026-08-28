"""Unit tests for drift detection."""
from __future__ import annotations

import pytest
import numpy as np

from model_eval_service.drift_monitor import DriftMonitor


def test_set_baseline():
    monitor = DriftMonitor()
    scores = [0.8, 0.85, 0.82, 0.88, 0.81]
    monitor.set_baseline("agent-1", "1.0.0", scores)
    # Should not raise


def test_no_drift():
    monitor = DriftMonitor(drift_threshold=0.05)
    scores = [0.8, 0.85, 0.82, 0.88, 0.81]
    monitor.set_baseline("agent-1", "1.0.0", scores)
    report = monitor.detect_drift("agent-1", "1.0.0", scores)
    assert report.drift_detected is False
    assert report.drift_score < 0.05


def test_drift_detected():
    monitor = DriftMonitor(drift_threshold=0.05)
    baseline = [0.8, 0.85, 0.82, 0.88, 0.81]
    current = [0.3, 0.35, 0.32, 0.38, 0.31]  # Much lower
    monitor.set_baseline("agent-1", "1.0.0", baseline)
    report = monitor.detect_drift("agent-1", "1.0.0", current)
    assert report.drift_detected is True
    assert report.recommended_action in ["rollback", "retrain", "investigate"]


def test_missing_baseline():
    monitor = DriftMonitor()
    with pytest.raises(ValueError, match="No baseline"):
        monitor.detect_drift("agent-1", "1.0.0", [0.5])
