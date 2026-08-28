"""Metrics collection for SentraAura services.

Supports Prometheus-compatible metrics with counters, histograms, and gauges.
Matches Architecture §10.2 and Backend Spec §10.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MetricValue:
    """A single metric value with labels."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """In-memory metrics collector for SentraAura services."""

    def __init__(self, service_name: str = "sentraura") -> None:
        self.service_name = service_name
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._labels: dict[str, dict[str, str]] = {}

    def counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        key = self._key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value
        if labels:
            self._labels[key] = labels

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        key = self._key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a histogram observation."""
        key = self._key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels

    def timer(self, name: str, labels: dict[str, str] | None = None) -> Callable[[], None]:
        """Context manager / decorator for timing operations."""
        start = time.time()
        def stop() -> None:
            self.histogram(name, time.time() - start, labels)
        return stop

    def get_metrics(self) -> dict[str, Any]:
        """Get all collected metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: {"count": len(v), "sum": sum(v), "avg": sum(v)/len(v) if v else 0, "min": min(v) if v else 0, "max": max(v) if v else 0} for k, v in self._histograms.items()},
            "labels": dict(self._labels),
        }

    def _key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f'{name}{{{label_str}}}'


# Global collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector(service_name: str = "sentraura") -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(service_name)
    return _metrics_collector
