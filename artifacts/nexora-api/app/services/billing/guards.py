"""FastAPI guards for quota + feature enforcement (Sprint 61C).

Use as endpoint dependencies so plan limits/entitlements are validated *before*
the operation runs — no hardcoded checks in business logic.

    @router.post("/things", dependencies=[Depends(require_quota(UsageMetric.API_CALLS))])
    @router.post("/sso", dependencies=[Depends(require_feature("sso"))])

Also exposes ``meter_usage`` for services to record consumption after success.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.core.config import settings
from app.models.billing import UsageMetric
from app.services.billing.feature_flags import FeatureFlagService
from app.services.billing.quota import QuotaExceeded, QuotaService


def require_quota(metric: UsageMetric | str, amount: int = 1) -> Callable:
    async def _dep(ctx: OrgContextDep, session: DBSession) -> None:
        if not settings.BILLING_ENABLED:
            return
        org_id = ctx.organization_id
        if not org_id:
            return  # no org context → nothing org-scoped to enforce
        try:
            await QuotaService(session).enforce(org_id, metric, amount)
        except QuotaExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"error": "quota_exceeded", **exc.decision.as_dict()},
            ) from None

    return _dep


def require_feature(feature: str) -> Callable:
    async def _dep(ctx: OrgContextDep, session: DBSession) -> None:
        if not settings.BILLING_ENABLED:
            return
        org_id = ctx.organization_id
        if not org_id:
            return
        if not await FeatureFlagService(session).is_enabled(org_id, feature):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"error": "feature_not_in_plan", "feature": feature},
            )

    return _dep


async def meter_usage(
    session, organization_id: str | None, metric: UsageMetric | str, amount: int = 1,
    *, enforce: bool = False,
) -> None:
    """Record usage for a metric (best-effort; never breaks the request)."""
    if not settings.BILLING_ENABLED or not organization_id:
        return
    try:
        await QuotaService(session).meter(organization_id, metric, amount, enforce=enforce)
    except QuotaExceeded:
        raise
    except Exception:  # pragma: no cover - metering must not break the request
        pass


# Convenience for unused-import friendliness in routers.
__all__ = ["require_quota", "require_feature", "meter_usage", "OrgContext", "Depends"]
