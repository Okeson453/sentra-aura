"""Graceful shutdown utilities for SentraAura services.

Handles SIGTERM/SIGINT, drains in-flight requests, flushes buffers,
and closes connections cleanly. Matches Architecture §10.4.
"""
from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

ShutdownHook = Callable[[], Coroutine[Any, Any, None]]


class GracefulShutdownManager:
    """Manages graceful shutdown for a service."""

    def __init__(self, shutdown_timeout_seconds: float = 30.0) -> None:
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self._hooks: list[ShutdownHook] = []
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False

    def add_hook(self, hook: ShutdownHook) -> None:
        """Register a shutdown hook."""
        self._hooks.append(hook)

    def remove_hook(self, hook: ShutdownHook) -> None:
        """Unregister a shutdown hook."""
        if hook in self._hooks:
            self._hooks.remove(hook)

    def install_signal_handlers(self) -> None:
        """Install SIGTERM and SIGINT handlers."""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_signal(s)))

    async def _handle_signal(self, sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")
        await self.shutdown()

    async def shutdown(self) -> None:
        """Execute all shutdown hooks with timeout."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        self._shutdown_event.set()

        logger.info(f"Executing {len(self._hooks)} shutdown hooks...")
        for hook in self._hooks:
            try:
                await asyncio.wait_for(hook(), timeout=self.shutdown_timeout_seconds)
                logger.info(f"Shutdown hook completed: {hook.__name__}")
            except asyncio.TimeoutError:
                logger.error(f"Shutdown hook timed out: {hook.__name__}")
            except Exception as exc:
                logger.error(f"Shutdown hook failed: {hook.__name__}: {exc}")

        logger.info("Graceful shutdown complete")

    def is_shutting_down(self) -> bool:
        return self._is_shutting_down

    async def wait_for_shutdown(self) -> None:
        """Block until shutdown is initiated."""
        await self._shutdown_event.wait()


class FastAPIShutdownHandler:
    """FastAPI lifespan-compatible shutdown handler."""

    def __init__(self, manager: GracefulShutdownManager | None = None) -> None:
        self.manager = manager or GracefulShutdownManager()

    async def startup(self) -> None:
        """Called on application startup."""
        self.manager.install_signal_handlers()
        logger.info("Graceful shutdown handler installed")

    async def shutdown(self) -> None:
        """Called on application shutdown."""
        await self.manager.shutdown()
