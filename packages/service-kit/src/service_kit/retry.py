"""Retry logic with exponential backoff for SentraAura services.

Matches Architecture §10.3 and Backend Spec §10.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


async def with_retry(
    coro: Callable[[], Coroutine[Any, Any, T]],
    config: RetryConfig | None = None,
    operation_name: str = "operation",
) -> T:
    """Execute a coroutine with retry and exponential backoff."""
    cfg = config or RetryConfig()
    last_exception: Exception | None = None

    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await coro()
        except cfg.retryable_exceptions as exc:
            last_exception = exc
            if attempt == cfg.max_attempts:
                logger.error(f"{operation_name} failed after {cfg.max_attempts} attempts: {exc}")
                raise RetryExhaustedError(f"{operation_name} failed after {cfg.max_attempts} attempts") from exc

            delay = min(
                cfg.base_delay_seconds * (cfg.exponential_base ** (attempt - 1)),
                cfg.max_delay_seconds,
            )
            if cfg.jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(f"{operation_name} attempt {attempt} failed: {exc}. Retrying in {delay:.2f}s")
            await asyncio.sleep(delay)

    raise RetryExhaustedError(f"{operation_name} failed unexpectedly")


def retry(
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """Decorator for retry logic on async functions."""
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await with_retry(
                lambda: func(*args, **kwargs),
                config=config,
                operation_name=func.__name__,
            )
        return wrapper
    return decorator
