"""Circuit breaker to prevent cascading failures.

States:
* CLOSED   — calls pass through; consecutive failures are counted.
* OPEN     — calls fail fast (``CircuitBreakerOpen``) until ``reset_timeout``.
* HALF_OPEN — a limited number of trial calls probe recovery; a success closes
  the breaker, a failure re-opens it.

Breakers are process-local (each replica protects its own outbound calls), keyed
by name via :func:`get_circuit_breaker`.
"""

from __future__ import annotations

import asyncio
import enum
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the breaker is open."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Circuit breaker '{name}' is open")
        self.name = name


def _record_state(name: str, state: CircuitState) -> None:
    try:
        from app.observability import metrics

        metrics.record_circuit_state(name, state.value)
    except Exception:  # pragma: no cover - metrics optional
        pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exceptions = expected_exceptions
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def _transition(self, state: CircuitState) -> None:
        if state != self._state:
            self._state = state
            _record_state(self.name, state)

    async def _before_call(self) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.reset_timeout:
                    self._transition(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpen(self.name)
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpen(self.name)
                self._half_open_calls += 1

    async def _on_success(self) -> None:
        async with self._lock:
            self._failures = 0
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                self._transition(CircuitState.CLOSED)
            self._half_open_calls = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._state == CircuitState.HALF_OPEN:
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)
            elif self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        await self._before_call()
        try:
            result = await func(*args, **kwargs)
        except self.expected_exceptions:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
            "failure_threshold": self.failure_threshold,
        }


_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    *,
    failure_threshold: int = 5,
    reset_timeout: float = 30.0,
    half_open_max_calls: int = 1,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> CircuitBreaker:
    """Return the named breaker, creating it on first use (process-local)."""
    breaker = _breakers.get(name)
    if breaker is None:
        breaker = CircuitBreaker(
            name,
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            half_open_max_calls=half_open_max_calls,
            expected_exceptions=expected_exceptions,
        )
        _breakers[name] = breaker
    return breaker


def all_breakers() -> list[CircuitBreaker]:
    return list(_breakers.values())


def reset_all() -> None:
    """Test hook: forget all breakers."""
    _breakers.clear()
