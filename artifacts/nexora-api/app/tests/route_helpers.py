"""Helpers for introspecting FastAPI routers in tests."""

from __future__ import annotations

from fastapi.routing import APIRoute


def collect_route_paths(router, *, prefix: str = "") -> list[str]:
    """Collect route paths from a router, including nested included routers."""
    paths: list[str] = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            paths.append(f"{prefix}{route.path}")
            continue

        nested_router = getattr(route, "original_router", route)
        nested_prefix = getattr(route, "path", "") or getattr(nested_router, "prefix", "") or ""
        if hasattr(nested_router, "routes"):
            paths.extend(
                collect_route_paths(nested_router, prefix=f"{prefix}{nested_prefix}")
            )
    return paths
