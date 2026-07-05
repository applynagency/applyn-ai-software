"""Multi-region readiness primitives (Sprint 62B).

Prepares Nexora for global deployment *without* introducing active-active write
logic. It provides the abstractions a multi-region rollout needs:

* region identity + region-aware configuration / routing abstraction
* UTC-only storage verification (catch naive/local datetimes early)
* clock-skew tolerance for accepting cross-region/replicated timestamps
* idempotent replication events (dedupe by a stable key so a replayed event from
  another region is applied at most once)
* CDN asset URL helper

All read-only helpers; no global write coordination.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings


def current_region() -> str:
    return settings.REGION or "default"


def region_config(key: str, default=None):
    """Resolve a region-scoped setting ``<KEY>__<REGION>`` falling back to ``<KEY>``.

    Lets a single config define per-region overrides, e.g. ``CDN_BASE_URL__eu``.
    """
    region = current_region()
    scoped = f"{key}__{region}"
    if hasattr(settings, scoped):
        val = getattr(settings, scoped)
        if val is not None:
            return val
    return getattr(settings, key, default)


def route_for_region(region: str | None = None) -> str:
    """Region-aware routing abstraction: base URL to address a given region.

    Returns the configured public base URL (per-region override aware). Callers
    that need to fan a request to another region resolve the target here rather
    than hardcoding hosts.
    """
    region = region or current_region()
    base = getattr(settings, f"SSO_PUBLIC_BASE_URL__{region}", None)
    return base or settings.SSO_PUBLIC_BASE_URL or ""


# --------------------------------------------------------------------------- #
# Clock skew + UTC verification
# --------------------------------------------------------------------------- #
def now_utc() -> datetime:
    return datetime.now(UTC)


def is_utc(dt: datetime) -> bool:
    """True when ``dt`` is timezone-aware and at UTC offset."""
    if dt.tzinfo is None:
        return False
    return dt.utcoffset() == UTC.utcoffset(None)


def clock_skew_ok(timestamp: datetime, *, tolerance_seconds: int | None = None) -> bool:
    """Whether ``timestamp`` is within the accepted skew of now (both directions).

    Used to accept/reject replicated events whose origin clock may differ from
    ours, without rejecting legitimately-delayed messages.
    """
    tol = tolerance_seconds if tolerance_seconds is not None else (
        settings.CLOCK_SKEW_TOLERANCE_SECONDS)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    delta = abs((now_utc() - timestamp).total_seconds())
    return delta <= tol


def verify_utc_storage(*models: type) -> list[str]:
    """Lint datetime columns for non-UTC server defaults (best-effort check).

    Returns a list of ``Model.column`` strings whose default could persist a
    naive/local timestamp. Empty list ⇒ all good. Used by a startup/test guard.
    """
    issues: list[str] = []
    for model in models:
        table = getattr(model, "__table__", None)
        if table is None:
            continue
        for col in table.columns:
            type_name = type(col.type).__name__.lower()
            if "datetime" not in type_name:
                continue
            # A timezone-aware column is the safe choice; warn on naive ones that
            # also carry a python-side default (most likely to store local time).
            tz = getattr(col.type, "timezone", True)
            if not tz and col.default is not None:
                issues.append(f"{model.__name__}.{col.name}")
    return issues


# --------------------------------------------------------------------------- #
# Idempotent replication
# --------------------------------------------------------------------------- #
def replication_key(source_region: str, event_type: str, aggregate_id: str | None,
                    revision: str | int) -> str:
    """Stable key so the same logical change replicated from a region applies once."""
    return f"repl:{source_region}:{event_type}:{aggregate_id or '-'}:{revision}"


async def apply_replicated_event(
    session, *, source_region: str, event_type: str, payload: dict,
    aggregate_id: str | None = None, revision: str | int = "0",
    organization_id: str | None = None, origin_timestamp: datetime | None = None,
) -> dict:
    """Idempotently ingest an event replicated from another region.

    Rejects messages outside the clock-skew tolerance and dedupes by a stable
    replication key (via the event bus idempotency key), so a re-sent replication
    message is applied at most once.
    """
    if origin_timestamp is not None and not clock_skew_ok(origin_timestamp):
        return {"accepted": False, "reason": "clock_skew_exceeded"}

    from app.platform.events import emit_event

    key = replication_key(source_region, event_type, aggregate_id, revision)
    event = await emit_event(
        session, event_type, organization_id=organization_id, payload=payload,
        aggregate_type="replicated", aggregate_id=aggregate_id,
        source=f"region:{source_region}", idempotency_key=key)
    duplicate = event is not None and getattr(event, "idempotency_key", None) == key \
        and event.source != f"region:{source_region}"
    return {"accepted": True, "event_id": getattr(event, "id", None),
            "idempotency_key": key, "duplicate": duplicate}


# --------------------------------------------------------------------------- #
# CDN
# --------------------------------------------------------------------------- #
def asset_url(path: str) -> str:
    """Resolve a static asset to its CDN URL when a CDN is configured."""
    base = region_config("CDN_BASE_URL")
    if not base:
        return path
    return f"{base.rstrip('/')}/{path.lstrip('/')}"
