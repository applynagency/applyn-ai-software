"""Nexora platform convergence layer (Sprint 62A).

One canonical implementation for each cross-cutting capability:

* :mod:`app.platform.events`       — domain events + Redis-backed event bus
* :mod:`app.platform.execution`    — unified execution engine (jobs/agents/workflows)
* :mod:`app.platform.notifications`— unified notification platform (all channels)
* :mod:`app.platform.search`       — global search platform
* :mod:`app.platform.activity`     — global activity feed (consumes domain events)
* :mod:`app.platform.config`       — configuration platform (global/org/user)
* :mod:`app.platform.plugins`      — plugin framework
"""
