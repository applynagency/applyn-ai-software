"""Default plan catalog (Sprint 61C).

These are *seed defaults* only — every value lives in the ``plans`` table and is
fully editable via the admin API afterwards (no hardcoded limits at runtime).
``-1`` means unlimited.
"""

from __future__ import annotations

from app.models.billing import PlanTier, UsageMetric

M = UsageMetric


def _limits(**kw: int) -> dict:
    return {metric.value: kw.get(metric.name.lower(), -1) for metric in M}


# Default quota policy applied per plan (configurable per plan afterwards).
_DEFAULT_POLICY = {
    "soft_ratio": 0.8,       # warn at 80%
    "warning_ratio": 0.9,    # stronger warning at 90%
    "grace_days": 7,         # grace window after hard limit on paid plans
    "enforcement": "hard",   # hard | soft
}


def default_plans() -> list[dict]:
    """The built-in plan catalog seeded on first run."""
    return [
        {
            "slug": "free",
            "name": "Free",
            "tier": PlanTier.FREE.value,
            "description": "Get started at no cost.",
            "price_cents": 0,
            "trial_days": 0,
            "support_tier": "community",
            "limits": _limits(
                users=3, api_keys=2, service_accounts=1, ai_tokens=100_000,
                storage_bytes=1_000_000_000, integrations=2, workflow_executions=50,
                discovery_scans=10, incidents=25, alerts_processed=500,
                copilot_requests=200, api_calls=50_000, background_jobs=200,
            ),
            "features": {
                "sso": "disabled", "saml": "disabled", "scim": "disabled",
                "copilot": "limited", "war_room": "enabled", "discovery": "enabled",
                "advanced_analytics": "disabled", "audit_export": "disabled",
                "custom_retention": "disabled", "priority_support": "disabled",
            },
            "quota_policy": {**_DEFAULT_POLICY, "enforcement": "hard", "grace_days": 0,
                             "retention_days": 30},
        },
        {
            "slug": "starter",
            "name": "Starter",
            "tier": PlanTier.STARTER.value,
            "description": "For small teams.",
            "price_cents": 4900,
            "trial_days": 14,
            "support_tier": "email",
            "limits": _limits(
                users=10, api_keys=10, service_accounts=3, ai_tokens=1_000_000,
                storage_bytes=10_000_000_000, integrations=5, workflow_executions=500,
                discovery_scans=50, incidents=200, alerts_processed=5_000,
                copilot_requests=2_000, api_calls=500_000, background_jobs=2_000,
            ),
            "features": {
                "sso": "disabled", "saml": "disabled", "scim": "disabled",
                "copilot": "enabled", "war_room": "enabled", "discovery": "enabled",
                "advanced_analytics": "disabled", "audit_export": "enabled",
                "custom_retention": "disabled", "priority_support": "disabled",
            },
            "quota_policy": {**_DEFAULT_POLICY, "retention_days": 90},
        },
        {
            "slug": "professional",
            "name": "Professional",
            "tier": PlanTier.PROFESSIONAL.value,
            "description": "For growing engineering organizations.",
            "price_cents": 19900,
            "trial_days": 14,
            "support_tier": "business_hours",
            "limits": _limits(
                users=50, api_keys=50, service_accounts=15, ai_tokens=10_000_000,
                storage_bytes=100_000_000_000, integrations=20, workflow_executions=5_000,
                discovery_scans=500, incidents=2_000, alerts_processed=50_000,
                copilot_requests=20_000, api_calls=5_000_000, background_jobs=20_000,
            ),
            "features": {
                "sso": "enabled", "saml": "enabled", "scim": "disabled",
                "copilot": "enabled", "war_room": "enabled", "discovery": "enabled",
                "advanced_analytics": "enabled", "audit_export": "enabled",
                "custom_retention": "enabled", "priority_support": "disabled",
            },
            "quota_policy": {**_DEFAULT_POLICY, "retention_days": 180},
        },
        {
            "slug": "business",
            "name": "Business",
            "tier": PlanTier.BUSINESS.value,
            "description": "For large organizations with compliance needs.",
            "price_cents": 49900,
            "trial_days": 14,
            "support_tier": "priority",
            "limits": _limits(
                users=200, api_keys=200, service_accounts=50, ai_tokens=50_000_000,
                storage_bytes=500_000_000_000, integrations=50, workflow_executions=25_000,
                discovery_scans=2_000, incidents=10_000, alerts_processed=250_000,
                copilot_requests=100_000, api_calls=25_000_000, background_jobs=100_000,
            ),
            "features": {
                "sso": "enabled", "saml": "enabled", "scim": "enabled",
                "copilot": "enabled", "war_room": "enabled", "discovery": "enabled",
                "advanced_analytics": "enabled", "audit_export": "enabled",
                "custom_retention": "enabled", "priority_support": "enabled",
            },
            "quota_policy": {**_DEFAULT_POLICY, "grace_days": 14, "retention_days": 365},
        },
        {
            "slug": "enterprise",
            "name": "Enterprise",
            "tier": PlanTier.ENTERPRISE.value,
            "description": "Unlimited scale with enterprise licensing.",
            "price_cents": 0,  # custom-negotiated
            "trial_days": 0,
            "support_tier": "dedicated",
            "is_public": False,
            "limits": _limits(),  # all unlimited
            "features": {
                "sso": "enabled", "saml": "enabled", "scim": "enabled",
                "copilot": "enabled", "war_room": "enabled", "discovery": "enabled",
                "advanced_analytics": "enabled", "audit_export": "enabled",
                "custom_retention": "enabled", "priority_support": "enabled",
            },
            "quota_policy": {**_DEFAULT_POLICY, "enforcement": "soft", "grace_days": 30,
                             "retention_days": -1},
        },
    ]
