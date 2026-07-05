"""Permission scope catalog for API keys and service accounts.

Scopes are coarse-grained capability strings of the form ``<resource>:<action>``
(``read`` / ``write``). The wildcard ``*`` grants everything. Scopes refine —
they never widen — the role attached to the principal.
"""

from __future__ import annotations

WILDCARD = "*"

# Canonical catalog. Keep additions backwards-compatible.
SCOPE_CATALOG: dict[str, str] = {
    "*": "Full access to everything the principal's role allows",
    "incidents:read": "Read incidents, war rooms and timelines",
    "incidents:write": "Create/update incidents and war rooms",
    "discovery:read": "Read inventory and the knowledge graph",
    "discovery:write": "Trigger discovery scans and edit the graph",
    "deployments:read": "Read deployments and pipelines",
    "deployments:write": "Trigger and manage deployments",
    "observability:read": "Read monitoring, SLOs and dashboards",
    "observability:write": "Manage monitoring, SLOs and alerts",
    "reports:read": "Read executive/leadership reports",
    "audit:read": "Read the organization audit log",
    "identity:read": "Read identity resources (keys, sessions, policy)",
    "identity:write": "Manage identity resources",
    "copilot:invoke": "Invoke the Copilot",
}


def is_valid_scope(scope: str) -> bool:
    return scope in SCOPE_CATALOG


def validate_scopes(scopes: list[str] | None) -> list[str]:
    """Normalize/validate a scope list; raise ValueError on unknown scopes."""
    if not scopes:
        return [WILDCARD]
    cleaned: list[str] = []
    for raw in scopes:
        scope = (raw or "").strip().lower()
        if not scope:
            continue
        if not is_valid_scope(scope):
            raise ValueError(f"Unknown scope: {raw!r}")
        if scope not in cleaned:
            cleaned.append(scope)
    return cleaned or [WILDCARD]


def has_scope(granted: list[str] | None, required: str) -> bool:
    """True when ``required`` is satisfied by ``granted``.

    ``*`` grants everything; a ``<resource>:write`` grant also implies
    ``<resource>:read``.
    """
    if not granted:
        return False
    if WILDCARD in granted or required in granted:
        return True
    if required.endswith(":read"):
        resource = required.rsplit(":", 1)[0]
        return f"{resource}:write" in granted
    return False
