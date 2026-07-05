"""Per-plan feature entitlements (Sprint 61C).

Resolves whether a feature is ``enabled`` / ``disabled`` / ``limited`` for an
organization from its plan's ``features`` map (plus an active license override).
This is the single resolver — callers must use it instead of hardcoded checks.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.billing.subscriptions import SubscriptionService

ENABLED = "enabled"
DISABLED = "disabled"
LIMITED = "limited"


class FeatureFlagService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subscriptions = SubscriptionService(session)

    async def all_flags(self, organization_id: str) -> dict[str, str]:
        plan = await self.subscriptions.plan_for(organization_id)
        flags = dict(plan.features or {})
        # An active license may grant additional features (on-prem/enterprise).
        license_features = await self._license_features(organization_id)
        flags.update(license_features)
        return flags

    async def state(self, organization_id: str, feature: str) -> str:
        flags = await self.all_flags(organization_id)
        return flags.get(feature, DISABLED)

    async def is_enabled(self, organization_id: str, feature: str) -> bool:
        """True when the feature is enabled OR limited (i.e. available at all)."""
        return (await self.state(organization_id, feature)) in (ENABLED, LIMITED)

    async def is_fully_enabled(self, organization_id: str, feature: str) -> bool:
        return (await self.state(organization_id, feature)) == ENABLED

    async def require(self, organization_id: str, feature: str) -> None:
        from app.services.billing.quota import QuotaDecision, QuotaExceeded

        if not await self.is_enabled(organization_id, feature):
            decision = QuotaDecision(
                metric=f"feature:{feature}", limit=0, used=0, requested=1,
                allowed=False, warning=False, soft=False, over_hard=True,
                enforcement="hard", remaining=0, reason="feature_not_in_plan",
            )
            raise QuotaExceeded(decision)

    async def _license_features(self, organization_id: str) -> dict[str, str]:
        from app.services.billing.licenses import LicenseService

        lic = await LicenseService(self.session).active_for_org(organization_id)
        if lic and lic.features:
            return {k: str(v) for k, v in lic.features.items()}
        return {}
