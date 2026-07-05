"""Unified Redis integration layer.

A single shared async Redis client (``app.redis.client``) backs every feature:

* ``cache``         — TTL'd key/value cache (`get_or_set`, `incr`, …)
* ``sessions``      — server-side session store (list / revoke)
* ``denylist``      — JWT access-token revocation (real logout)
* ``locks``         — distributed + scheduler locks
* ``notifications`` — buffered outbound notification queue

Rate limiting (``app.security.rate_limit``) and the Arq background job queue
(``app.jobs``) are the other two Redis-backed subsystems.

Every feature degrades to an in-process fallback when Redis is not configured,
so the application boots and the test suite runs without Redis installed.
"""
