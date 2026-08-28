"""Metrics instrumentation for SentraAura.

Prometheus-compatible metric types.
"""
from __future__ import annotations

from typing import Any


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None) -> None:
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: dict[tuple[str, ...], float] = {}

    def inc(self, amount: float = 1.0, **label_values: str) -> None:
        key = tuple(label_values.get(l, "") for l in self.labels)
        self._values[key] = self._values.get(key, 0.0) + amount

    def get(self, **label_values: str) -> float:
        key = tuple(label_values.get(l, "") for l in self.labels)
        return self._values.get(key, 0.0)


class Histogram:
    """Distribution of values into buckets."""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: list[float] | None = None,
        labels: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self.labels = labels or []
        self._observations: list[tuple[dict[str, str], float]] = []

    def observe(self, value: float, **label_values: str) -> None:
        self._observations.append((label_values, value))

    def get_count(self, **label_values: str) -> int:
        return sum(1 for lv, _ in self._observations if lv == label_values)

    def get_sum(self, **label_values: str) -> float:
        return sum(v for lv, v in self._observations if lv == label_values)


class Gauge:
    """Arbitrary value that can go up or down."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None) -> None:
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: dict[tuple[str, ...], float] = {}

    def set(self, value: float, **label_values: str) -> None:
        key = tuple(label_values.get(l, "") for l in self.labels)
        self._values[key] = value

    def get(self, **label_values: str) -> float:
        key = tuple(label_values.get(l, "") for l in self.labels)
        return self._values.get(key, 0.0)


class MetricsRegistry:
    """Registry of all metrics for a service."""

    def __init__(self) -> None:
        self._metrics: dict[str, Any] = {}

    def counter(self, name: str, description: str, labels: list[str] | None = None) -> Counter:
        c = Counter(name, description, labels)
        self._metrics[name] = c
        return c

    def histogram(self, name: str, description: str, buckets: list[float] | None = None, labels: list[str] | None = None) -> Histogram:
        h = Histogram(name, description, buckets, labels)
        self._metrics[name] = h
        return h

    def gauge(self, name: str, description: str, labels: list[str] | None = None) -> Gauge:
        g = Gauge(name, description, labels)
        self._metrics[name] = g
        return g


def get_metrics() -> MetricsRegistry:
    """Get the global metrics registry."""
    return _registry


_registry = MetricsRegistry()
