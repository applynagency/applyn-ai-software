"""Resilience primitives for production HA (Sprint 61B).

* ``circuit_breaker`` — per-dependency circuit breakers (closed/open/half-open)
  that stop cascading failures by failing fast when a dependency is unhealthy.
* ``bulkhead`` — bounded-concurrency isolation so one slow dependency cannot
  exhaust the whole process.
* ``timeouts`` — a single ``with_timeout`` helper enforcing deadline policies.

All primitives degrade safely and emit Prometheus metrics when available.
"""

from app.resilience.bulkhead import Bulkhead, BulkheadFull, get_bulkhead
from app.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    get_circuit_breaker,
)
from app.resilience.timeouts import TimeoutPolicy, with_timeout

__all__ = [
    "Bulkhead",
    "BulkheadFull",
    "get_bulkhead",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "get_circuit_breaker",
    "TimeoutPolicy",
    "with_timeout",
]
