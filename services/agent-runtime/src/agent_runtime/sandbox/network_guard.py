"""In-process network egress guard for SandboxRunner (Arch. §41.3).

Execution context is in-process Python (async tool coroutines / thread-pool
sync tools). OS-level isolation (network namespace, seccomp) is not available
without a subprocess/container redesign — that gap is intentional and flagged.

This module installs a process-wide socket.connect wrapper once; enforcement is
enabled only while a ContextVar is set for the current sandbox execution, so
test harness and non-sandbox code are unaffected.
"""
from __future__ import annotations

import logging
import socket
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_network_blocked: ContextVar[bool] = ContextVar("sandbox_network_blocked", default=False)
_installed = False
_original_connect = socket.socket.connect


class NetworkAccessDeniedError(RuntimeError):
    """Raised when sandboxed code attempts network egress with allow_network=False."""

    def __init__(self, message: str = "Network egress denied by sandbox (allow_network=False)") -> None:
        super().__init__(message)


def _guarded_connect(self: socket.socket, address: Any) -> None:  # type: ignore[no-untyped-def]
    if _network_blocked.get():
        logger.warning("Blocked sandbox network connect to %s", address)
        raise NetworkAccessDeniedError(
            f"Network egress denied by sandbox (allow_network=False); attempted connect to {address!r}"
        )
    return _original_connect(self, address)


def install_network_guard() -> None:
    """Idempotently install the process-wide guarded connect (enforcement via ContextVar)."""
    global _installed
    if _installed:
        return
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign, assignment]
    _installed = True
    logger.debug("Sandbox network guard installed on socket.socket.connect")


@contextmanager
def network_restriction(enabled: bool) -> Iterator[None]:
    """If enabled=True, block outbound socket.connect in this context only."""
    if not enabled:
        yield
        return
    install_network_guard()
    token = _network_blocked.set(True)
    try:
        yield
    finally:
        _network_blocked.reset(token)


def is_network_blocked() -> bool:
    return bool(_network_blocked.get())
