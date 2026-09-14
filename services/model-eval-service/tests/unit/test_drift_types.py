"""Regression tests for drift-report bool typing and JSON serialisation.

Guards a defect where ``DriftReport.drift_detected`` was assigned the result of
a comparison over numpy scalars, producing ``np.bool_`` instead of ``bool``.
Two production consequences:

* ``jsonable_encoder`` cannot serialise ``np.bool_`` (TypeError), so the drift
  detect endpoint returned HTTP 500.
* The field is part of an API contract that promises ``true``/``false``; a
  non-identical numpy type breaks strict consumers and ``is True`` assertions.

These tests fail against the pre-fix code.
"""
from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
from fastapi.testclient import TestClient

from model_eval_service.drift_monitor import DriftMonitor
from model_eval_service.main import app

BASELINE = [0.8, 0.85, 0.82, 0.88, 0.81]
DRIFTED = [0.3, 0.35, 0.32, 0.38, 0.31]

client = TestClient(app)


def test_drift_detected_is_builtin_bool() -> None:
    monitor = DriftMonitor(drift_threshold=0.05)
    monitor.set_baseline("agent-1", "1.0.0", BASELINE)

    report = monitor.detect_drift("agent-1", "1.0.0", DRIFTED)

    assert report.drift_detected is True
    assert type(report.drift_detected) is bool
    assert not isinstance(report.drift_detected, np.bool_)


def test_no_drift_is_builtin_bool() -> None:
    monitor = DriftMonitor(drift_threshold=0.05)
    monitor.set_baseline("agent-1", "1.0.0", BASELINE)

    report = monitor.detect_drift("agent-1", "1.0.0", BASELINE)

    assert report.drift_detected is False
    assert type(report.drift_detected) is bool


def test_drift_report_is_json_serialisable() -> None:
    monitor = DriftMonitor(drift_threshold=0.05)
    monitor.set_baseline("agent-1", "1.0.0", BASELINE)
    report = monitor.detect_drift("agent-1", "1.0.0", DRIFTED)

    payload = asdict(report)
    payload["reported_at"] = report.reported_at.isoformat()

    encoded = json.dumps(payload)  # TypeError before the fix
    assert '"drift_detected": true' in encoded


def test_drift_detect_endpoint_returns_serialisable_json() -> None:
    params = {"agent_id": "svc-agent", "version": "2.0.0"}
    baseline = client.post("/api/v1/drift/baseline", params=params, json=BASELINE)
    assert baseline.status_code == 200

    response = client.post("/api/v1/drift/detect", params=params, json=DRIFTED)

    assert response.status_code == 200
    body = response.json()
    assert body["drift_detected"] is True
    assert json.dumps(body)  # must survive a round-trip
