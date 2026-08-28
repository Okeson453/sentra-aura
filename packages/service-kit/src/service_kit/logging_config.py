"""Structured logging configuration for SentraAura services.

Matches Architecture §10.1 and Backend Spec §10.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any


def configure_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    service_name: str = "sentraura",
) -> None:
    """Configure structured logging for a service."""
    if json_format:
        formatter = logging.Formatter(
            fmt=json.dumps({"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "service": service_name}),
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Get a structured logger instance."""
    return logging.getLogger(name)
