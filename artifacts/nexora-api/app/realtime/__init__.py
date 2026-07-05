"""Real-time transport for collaborative features.

* ``broker``  — Redis pub/sub with an in-process fallback (multi-worker fan-out)
* ``manager`` — per-room WebSocket connection registry with presence + broadcast

When Redis is unavailable (single worker / tests) broadcast is purely in-process;
when Redis is configured, messages also fan out to connections on other workers.
"""

from app.realtime.manager import ConnectionManager, manager

__all__ = ["ConnectionManager", "manager"]
