"""AI provider health monitoring + circuit breaker (Sprint 62B).

The :class:`AIGateway` routes through pluggable providers. A single unhealthy
provider (expired key, regional outage, rate-limit storm) must not slow every
request down with repeated timeouts/retries. This module tracks per-provider
health and trips a circuit breaker that *auto-disables* a provider after a burst
of consecutive failures, so routing skips it until a cooldown elapses — at which
point a single half-open probe is allowed to auto-recover.

Process-local (one breaker per worker) and bounded by the small set of provider
names, so it is allocation-free on the hot path and needs no Redis.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class _ProviderState:
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    opened_at: float | None = None  # monotonic time the breaker opened
    last_error: str | None = None
    half_open: bool = False


class ProviderHealthRegistry:
    """Per-provider circuit breaker with auto-disable + half-open recovery."""

    def __init__(self) -> None:
        self._states: dict[str, _ProviderState] = {}
        self._lock = threading.Lock()

    def _state(self, provider: str) -> _ProviderState:
        st = self._states.get(provider)
        if st is None:
            st = _ProviderState()
            self._states[provider] = st
        return st

    def is_available(self, provider: str) -> bool:
        """True when routing may use ``provider`` (closed or half-open probe)."""
        cooldown = max(1.0, float(settings.AI_PROVIDER_CB_COOLDOWN_SECONDS))
        with self._lock:
            st = self._state(provider)
            if st.opened_at is None:
                return True
            if time.monotonic() - st.opened_at >= cooldown:
                # Cooldown elapsed → allow exactly one half-open probe.
                st.half_open = True
                available = True
            else:
                available = False
        if available:
            _set_metric(provider, True)
        return available

    def record_success(self, provider: str) -> None:
        with self._lock:
            st = self._state(provider)
            st.total_successes += 1
            st.consecutive_failures = 0
            st.opened_at = None
            st.half_open = False
            st.last_error = None
        _set_metric(provider, True)

    def record_failure(self, provider: str, error: str | None = None) -> None:
        threshold = max(1, int(settings.AI_PROVIDER_CB_THRESHOLD))
        with self._lock:
            st = self._state(provider)
            st.total_failures += 1
            st.consecutive_failures += 1
            st.last_error = (error or "")[:300] or None
            # A failed half-open probe re-opens the breaker immediately.
            if st.half_open or st.consecutive_failures >= threshold:
                st.opened_at = time.monotonic()
                st.half_open = False
        _record_failure_metric(provider)
        if self.is_open(provider):
            _set_metric(provider, False)

    def is_open(self, provider: str) -> bool:
        with self._lock:
            st = self._states.get(provider)
            return bool(st and st.opened_at is not None)

    def snapshot(self) -> list[dict]:
        cooldown = max(1.0, float(settings.AI_PROVIDER_CB_COOLDOWN_SECONDS))
        now = time.monotonic()
        out: list[dict] = []
        with self._lock:
            for provider, st in sorted(self._states.items()):
                if st.opened_at is None:
                    state = "closed"
                    cooldown_remaining = 0.0
                elif now - st.opened_at >= cooldown:
                    state = "half_open"
                    cooldown_remaining = 0.0
                else:
                    state = "open"
                    cooldown_remaining = round(cooldown - (now - st.opened_at), 2)
                out.append({
                    "provider": provider,
                    "state": state,
                    "available": state != "open",
                    "consecutive_failures": st.consecutive_failures,
                    "total_failures": st.total_failures,
                    "total_successes": st.total_successes,
                    "cooldown_remaining_seconds": cooldown_remaining,
                    "last_error": st.last_error,
                })
        return out

    def reset(self) -> None:  # test helper
        with self._lock:
            self._states.clear()


_REGISTRY = ProviderHealthRegistry()


def get_provider_health() -> ProviderHealthRegistry:
    return _REGISTRY


def _set_metric(provider: str, available: bool) -> None:
    try:
        from app.observability import metrics

        metrics.set_ai_provider_up(provider, available)
    except Exception:  # pragma: no cover
        pass


def _record_failure_metric(provider: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_ai_provider_failure(provider)
    except Exception:  # pragma: no cover
        pass
