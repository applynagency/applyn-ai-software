"""Commercial platform tests (Sprint 61C).

Covers subscription plans, usage metering, quota enforcement (hard/soft/grace/
warning + overrides), feature flags, subscription lifecycle, the license engine
(online + offline signature), the replaceable billing-provider abstraction,
webhook emission (outbox), the usage dashboard, scheduled maintenance, the
org-scoped + admin APIs, and tamper-evident audit events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.database.session import AsyncSessionLocal
from app.models.billing import (
    BillingProviderType,
    Invoice,
    LicenseType,
    SubscriptionStatus,
    UsageMetric,
)
from app.models.organization import Organization, OrganizationRole
from app.services.billing.feature_flags import FeatureFlagService
from app.services.billing.licenses import LicenseService, decode_offline_token
from app.services.billing.lifecycle import BillingMaintenance
from app.services.billing.metering import MeteringService
from app.services.billing.plans import PlanService
from app.services.billing.providers import StripeProvider, get_provider
from app.services.billing.quota import QuotaExceeded, QuotaService
from app.services.billing.subscriptions import SubscriptionService
from app.services.billing.usage_dashboard import UsageDashboardService
from app.services.billing.webhooks import BillingWebhookService

from .conftest import auth_headers, create_authenticated_user


def _now() -> datetime:
    return datetime.now(UTC)


async def _make_org(session, slug: str) -> str:
    org = Organization(name=slug, slug=slug)
    session.add(org)
    await session.flush()
    return org.id


async def _seed_and_org(session, slug: str) -> str:
    await PlanService(session).seed_defaults()
    return await _make_org(session, slug)


async def _assign_custom_plan(session, org_id: str, limits: dict, *, features: dict | None = None,
                              policy: dict | None = None):
    plan = await PlanService(session).create({
        "name": f"custom-{org_id[:6]}", "tier": "CUSTOM",
        "limits": limits, "features": features or {},
        "quota_policy": policy or {"enforcement": "hard", "soft_ratio": 0.8,
                                   "warning_ratio": 0.9, "grace_days": 7},
    })
    await SubscriptionService(session).assign_plan(org_id, plan.id)
    return plan


# --- Plans -------------------------------------------------------------------
async def test_seed_default_plans_idempotent(setup_db):
    async with AsyncSessionLocal() as session:
        created = await PlanService(session).seed_defaults()
        await session.commit()
        assert created == 5
    async with AsyncSessionLocal() as session:
        again = await PlanService(session).seed_defaults()
        await session.commit()
        assert again == 0
        plans = await PlanService(session).list()
        slugs = {p.slug for p in plans}
        assert {"free", "starter", "professional", "business", "enterprise"} <= slugs


async def test_plan_create_update_clone(setup_db):
    async with AsyncSessionLocal() as session:
        svc = PlanService(session)
        plan = await svc.create({"name": "Team", "limits": {"users": 5},
                                 "features": {"sso": "disabled"}})
        await session.commit()
        assert plan.slug == "team"

        updated = await svc.update(plan.id, {"features": {"sso": "enabled"}})
        await session.commit()
        assert updated.features["sso"] == "enabled"

        clone = await svc.clone(plan.id, new_name="Team Plus")
        await session.commit()
        assert clone.slug == "team-plus"
        assert clone.tier == "CUSTOM"
        assert clone.limits["users"] == 5


# --- Subscriptions & lifecycle ----------------------------------------------
async def test_subscription_get_or_create_and_assign(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "sub-org")
        svc = SubscriptionService(session)
        sub = await svc.get_or_create(org_id)
        await session.commit()
        assert sub.organization_id == org_id
        assert sub.status in (SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value)

        pro = await PlanService(session).get_by_slug("professional")
        sub2 = await svc.assign_plan(org_id, pro.id)
        await session.commit()
        assert sub2.plan_id == pro.id


async def test_subscription_suspend_resume(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "suspend-org")
        svc = SubscriptionService(session)
        await svc.get_or_create(org_id)
        await svc.suspend(org_id, reason="nonpayment")
        await session.commit()
        sub = await svc.get(org_id)
        assert sub.status == SubscriptionStatus.SUSPENDED.value
        assert svc.is_operational(sub) is False

        await svc.resume(org_id)
        await session.commit()
        sub = await svc.get(org_id)
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert svc.is_operational(sub) is True


async def test_lifecycle_trial_and_grace_transitions(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "lifecycle-org")
        svc = SubscriptionService(session)
        sub = await svc.get_or_create(org_id)
        # Force an expired trial.
        sub.status = SubscriptionStatus.TRIAL.value
        sub.trial_ends_at = _now() - timedelta(days=1)
        session.add(sub)
        await session.flush()

        counts = await svc.run_lifecycle_tick()
        await session.commit()
        assert counts["trial_expired"] == 1
        assert (await svc.get(org_id)).status == SubscriptionStatus.OVERDUE.value

        # Expired grace -> suspended.
        sub = await svc.get(org_id)
        sub.status = SubscriptionStatus.GRACE.value
        sub.grace_until = _now() - timedelta(hours=1)
        session.add(sub)
        await session.flush()
        counts = await svc.run_lifecycle_tick()
        await session.commit()
        assert counts["grace_expired"] == 1
        assert (await svc.get(org_id)).status == SubscriptionStatus.SUSPENDED.value


# --- Metering ----------------------------------------------------------------
async def test_metering_records_daily_aggregate(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "meter-org")
        meter = MeteringService(session)
        await meter.record(org_id, UsageMetric.API_CALLS, 3)
        v = await meter.record(org_id, UsageMetric.API_CALLS, 2)
        await session.commit()
        assert v == 5
        usage = await meter.current_usage(org_id)
        assert usage[UsageMetric.API_CALLS.value] == 5
        series = await meter.daily_series(org_id, UsageMetric.API_CALLS)
        assert series[-1]["value"] == 5


# --- Quota enforcement -------------------------------------------------------
async def test_quota_hard_limit_blocks(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "quota-hard")
        await _assign_custom_plan(session, org_id, {UsageMetric.API_CALLS.value: 2})
        await session.commit()
        q = QuotaService(session)
        await q.meter(org_id, UsageMetric.API_CALLS)
        await q.meter(org_id, UsageMetric.API_CALLS)
        await session.commit()
        with pytest.raises(QuotaExceeded):
            await q.meter(org_id, UsageMetric.API_CALLS)


async def test_quota_warning_and_soft_thresholds(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "quota-soft")
        await _assign_custom_plan(session, org_id, {UsageMetric.API_CALLS.value: 10})
        await session.commit()
        meter = MeteringService(session)
        await meter.record(org_id, UsageMetric.API_CALLS, 8)
        await session.commit()
        decision = await QuotaService(session).check(org_id, UsageMetric.API_CALLS, 1)
        assert decision.warning is True
        assert decision.soft is True
        assert decision.over_hard is False
        assert decision.remaining == 2


async def test_quota_override_takes_precedence(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "quota-override")
        await _assign_custom_plan(session, org_id, {UsageMetric.API_CALLS.value: 2})
        q = QuotaService(session)
        await q.set_override(org_id, UsageMetric.API_CALLS, 100)
        await session.commit()
        assert await q.effective_limit(org_id, UsageMetric.API_CALLS) == 100
        # Now well within the override; no raise.
        for _ in range(5):
            await q.meter(org_id, UsageMetric.API_CALLS)
        await session.commit()


async def test_quota_grace_allows_over_limit(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "quota-grace")
        await _assign_custom_plan(session, org_id, {UsageMetric.API_CALLS.value: 1})
        sub = await SubscriptionService(session).get_or_create(org_id)
        sub.status = SubscriptionStatus.GRACE.value
        session.add(sub)
        await session.flush()
        await session.commit()
        meter = MeteringService(session)
        await meter.record(org_id, UsageMetric.API_CALLS, 5)
        await session.commit()
        decision = await QuotaService(session).check(org_id, UsageMetric.API_CALLS, 1)
        assert decision.over_hard is True
        assert decision.allowed is True
        assert decision.reason == "grace"


# --- Feature flags -----------------------------------------------------------
async def test_feature_flags_resolution(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "flags-org")
        await _assign_custom_plan(
            session, org_id, {}, features={"sso": "enabled", "copilot": "limited",
                                           "scim": "disabled"})
        await session.commit()
        ff = FeatureFlagService(session)
        assert await ff.is_enabled(org_id, "sso") is True
        assert await ff.is_fully_enabled(org_id, "copilot") is False
        assert await ff.is_enabled(org_id, "copilot") is True  # limited == available
        assert await ff.is_enabled(org_id, "scim") is False
        with pytest.raises(QuotaExceeded):
            await ff.require(org_id, "scim")


# --- License engine ----------------------------------------------------------
async def test_license_issue_validate_and_offline(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "license-org")
        svc = LicenseService(session)
        lic, token = await svc.issue(
            organization_id=org_id, license_type=LicenseType.ENTERPRISE_CONTRACT,
            plan_slug="enterprise", seats=100,
            features={"sso": "enabled"}, expires_at=_now() + timedelta(days=365),
        )
        await session.commit()
        result = await svc.validate(lic.license_key)
        assert result["valid"] is True
        assert result["seats"] == 100

        # Offline token verifies without DB / Stripe.
        offline = svc.validate_offline(token)
        assert offline["valid"] is True
        assert offline["plan_slug"] == "enterprise"
        # Tampering breaks the signature.
        assert decode_offline_token(token + "x") is None


async def test_license_expiry(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "license-exp")
        svc = LicenseService(session)
        lic, _ = await svc.issue(
            organization_id=org_id, license_type=LicenseType.OFFLINE,
            expires_at=_now() - timedelta(days=1),
        )
        await session.commit()
        expired = await svc.expire_due()
        await session.commit()
        assert expired == 1
        assert (await svc.validate(lic.license_key))["valid"] is False


# --- Billing providers -------------------------------------------------------
@pytest.mark.parametrize("provider", [
    BillingProviderType.MANUAL, BillingProviderType.ENTERPRISE, BillingProviderType.STRIPE,
])
async def test_billing_provider_abstraction(setup_db, provider):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, f"prov-{provider.value.lower()}")
        prov = get_provider(provider, session)
        cust = await prov.create_customer(org_id, email="ops@example.com")
        assert cust
        inv = await prov.create_invoice(org_id, 4900, currency="USD",
                                        line_items=[{"desc": "Plan", "amount": 4900}])
        await session.commit()
        assert inv.amount_cents == 4900
        assert inv.provider == provider.value
        paid = await prov.mark_paid(inv, external_id="ext_1")
        await session.commit()
        assert paid.status == "PAID"
        assert paid.paid_at is not None


def test_stripe_stub_signature_accepts_without_secret():
    # In stub mode (no STRIPE_WEBHOOK_SECRET) signatures are accepted.
    assert StripeProvider.verify_webhook_signature(b"{}", "") is True


@pytest.mark.asyncio
async def test_stripe_status_and_self_serve_stub(client):
    from app.tests.conftest import auth_headers, create_authenticated_user, create_organization

    _, tokens = await create_authenticated_user(client, email="stripe-st@e.com", username="stripe_st")
    await create_organization(client, tokens["access_token"], name="Stripe ST Org", slug="stripe-st-org")
    r = await client.get("/v1/billing/stripe/status", headers=auth_headers(tokens["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["self_serve_enabled"] is False

    checkout = await client.post(
        "/v1/billing/stripe/checkout",
        headers=auth_headers(tokens["access_token"]),
        json={"success_url": "http://localhost/billing", "cancel_url": "http://localhost/billing"},
    )
    assert checkout.status_code == 200
    assert checkout.json().get("stub") is True

    portal = await client.post(
        "/v1/billing/stripe/portal",
        headers=auth_headers(tokens["access_token"]),
        json={"return_url": "http://localhost/billing"},
    )
    assert portal.status_code == 200
    assert portal.json().get("stub") is True

    pm = await client.get("/v1/billing/payment-methods", headers=auth_headers(tokens["access_token"]))
    assert pm.status_code == 200
    assert pm.json()["stripe_configured"] is False


# --- Webhooks ----------------------------------------------------------------
async def test_webhook_outbox_records_event(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "wh-org")
        svc = BillingWebhookService(session)
        # No subscribers -> still recorded in the outbox.
        ev = await svc.emit(org_id, "quota.exceeded", {"metric": "api_calls"})
        await session.commit()
        assert ev.event_type == "quota.exceeded"
        assert ev.delivery_status == "no_subscribers"

        # With an endpoint (unreachable) the event is recorded as failed but kept.
        await svc.add_endpoint(org_id, "http://127.0.0.1:9/none")
        await session.commit()
        ev2 = await svc.emit(org_id, "subscription.changed", {"status": "ACTIVE"})
        await session.commit()
        assert ev2.delivery_status in ("failed", "delivered")
        assert ev2.attempts == 1


# --- Usage dashboard ---------------------------------------------------------
async def test_usage_dashboard_snapshot(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "dash-org")
        await _assign_custom_plan(session, org_id, {UsageMetric.API_CALLS.value: 10})
        meter = MeteringService(session)
        await meter.record(org_id, UsageMetric.API_CALLS, 12)  # over limit
        await session.commit()
        snap = await UsageDashboardService(session).snapshot(org_id)
        await session.commit()
        api = next(m for m in snap["metrics"] if m["metric"] == "api_calls")
        assert api["used"] == 12
        assert api["limit"] == 10
        assert api["over_limit"] is True
        assert any(o["metric"] == "api_calls" for o in snap["overages"])


# --- Scheduled maintenance ---------------------------------------------------
async def test_maintenance_period_reset(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "reset-org")
        sub = await SubscriptionService(session).get_or_create(org_id)
        sub.current_period_end = _now() - timedelta(days=1)
        session.add(sub)
        await session.flush()
        await session.commit()
        result = await BillingMaintenance(session).reset_period_quotas()
        await session.commit()
        assert result["periods_rolled"] == 1


# --- Audit -------------------------------------------------------------------
async def test_billing_actions_emit_audit(setup_db):
    from sqlalchemy import select

    from app.models.audit import AuditLog

    async with AsyncSessionLocal() as session:
        org_id = await _seed_and_org(session, "audit-org")
        await _assign_custom_plan(session, org_id, {UsageMetric.API_CALLS.value: 5})
        await QuotaService(session).set_override(org_id, UsageMetric.API_CALLS, 50)
        await SubscriptionService(session).suspend(org_id, reason="test")
        await session.commit()
        rows = (await session.execute(
            select(AuditLog).where(AuditLog.organization_id == org_id)
        )).scalars().all()
        actions = {r.action for r in rows}
        assert "subscription.plan_assigned" in actions
        assert "quota.override_set" in actions
        assert "subscription.suspended" in actions
        # Hash chain is contiguous and linked.
        ordered = sorted(rows, key=lambda r: r.sequence)
        for i, row in enumerate(ordered):
            assert row.sequence == i
            if i > 0:
                assert row.prev_hash == ordered[i - 1].entry_hash


# --- API surface -------------------------------------------------------------
async def test_billing_api_org_scoped(client):
    _, tokens = await create_authenticated_user(
        client, email="bill@example.com", username="billuser")
    h = auth_headers(tokens["access_token"])

    plans = await client.get("/v1/billing/plans", headers=h)
    assert plans.status_code == 200, plans.text
    # Non-superusers see public plans only (enterprise is non-public).
    assert plans.json()["total"] >= 4

    sub = await client.get("/v1/billing/subscription", headers=h)
    assert sub.status_code == 200, sub.text
    assert sub.json()["status"] in ("ACTIVE", "TRIAL")

    usage = await client.get("/v1/billing/usage", headers=h)
    assert usage.status_code == 200, usage.text
    body = usage.json()
    assert "metrics" in body and "overages" in body

    flags = await client.get("/v1/billing/feature-flags", headers=h)
    assert flags.status_code == 200
    assert "flags" in flags.json()


async def test_billing_admin_api_requires_superuser(client):
    _, tokens = await create_authenticated_user(
        client, email="nonadmin@example.com", username="nonadmin")
    h = auth_headers(tokens["access_token"])
    resp = await client.post("/v1/billing/admin/plans",
                             json={"name": "Hacker"}, headers=h)
    assert resp.status_code == 403


async def test_billing_admin_api_superuser_flow(client):
    from sqlalchemy import select

    from app.models.user import User

    me, tokens = await create_authenticated_user(
        client, email="admin@example.com", username="adminuser")
    h = auth_headers(tokens["access_token"])

    # Promote to superuser directly (no API to self-promote).
    async with AsyncSessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.email == "admin@example.com")
        )).scalar_one()
        user.is_superuser = True
        session.add(user)
        await session.commit()

    created = await client.post("/v1/billing/admin/plans",
                                json={"name": "Premier", "limits": {"users": 99},
                                      "features": {"sso": "enabled"}}, headers=h)
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]

    cloned = await client.post(f"/v1/billing/admin/plans/{plan_id}/clone",
                               json={"name": "Premier Copy"}, headers=h)
    assert cloned.status_code == 201, cloned.text

    # Issue a license (platform-level).
    lic = await client.post("/v1/billing/admin/licenses",
                            json={"license_type": "OFFLINE", "seats": 10}, headers=h)
    assert lic.status_code == 201, lic.text
    assert lic.json()["offline_token"]

    validated = await client.post("/v1/billing/licenses/validate",
                                  json={"offline_token": lic.json()["offline_token"]},
                                  headers=h)
    assert validated.status_code == 200
    assert validated.json()["valid"] is True


async def test_billing_license_does_not_expose_key(client):
    _, tokens = await create_authenticated_user(
        client, email="lic@example.com", username="licuser"
    )
    h = auth_headers(tokens["access_token"])
    resp = await client.get("/v1/billing/license", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    if body.get("license"):
        assert "license_key" not in body["license"]


async def test_billing_invoices_org_admin_only(client):
    from sqlalchemy import select

    from app.models.organization import OrganizationMember
    from app.models.user import User

    _, tokens = await create_authenticated_user(
        client, email="invviewer@example.com", username="invviewer"
    )
    async with AsyncSessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.email == "invviewer@example.com")
        )).scalar_one()
        members = (
            await session.execute(
                select(OrganizationMember).where(OrganizationMember.user_id == user.id)
            )
        ).scalars().all()
        for member in members:
            member.role = OrganizationRole.VIEWER
            session.add(member)
        await session.commit()

    resp = await client.get(
        "/v1/billing/invoices", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403


async def test_billing_invoices_org_isolation(client):
    from app.core.security import decode_token

    _, tokens_a = await create_authenticated_user(
        client, email="inva@example.com", username="inva"
    )
    org_a = decode_token(tokens_a["access_token"])["organization_id"]

    _, tokens_b = await create_authenticated_user(
        client, email="invb@example.com", username="invb"
    )
    org_b = decode_token(tokens_b["access_token"])["organization_id"]

    async with AsyncSessionLocal() as session:
        session.add(Invoice(
            organization_id=org_a,
            provider="MANUAL",
            status="PAID",
            amount_cents=4900,
            currency="USD",
        ))
        session.add(Invoice(
            organization_id=org_b,
            provider="MANUAL",
            status="OPEN",
            amount_cents=9900,
            currency="USD",
        ))
        await session.commit()

    list_a = await client.get(
        "/v1/billing/invoices", headers=auth_headers(tokens_a["access_token"])
    )
    assert list_a.status_code == 200
    assert list_a.json()["total"] == 1
    assert list_a.json()["items"][0]["organization_id"] == org_a
    assert list_a.json()["items"][0]["amount_cents"] == 4900
    assert "external_id" not in list_a.json()["items"][0]

    list_b = await client.get(
        "/v1/billing/invoices", headers=auth_headers(tokens_b["access_token"])
    )
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 1
    assert list_b.json()["items"][0]["organization_id"] == org_b


async def test_billing_subscription_org_isolation(client):
    from app.core.security import decode_token

    _, tokens_a = await create_authenticated_user(
        client, email="suba@example.com", username="suba"
    )
    org_a = decode_token(tokens_a["access_token"])["organization_id"]

    _, tokens_b = await create_authenticated_user(
        client, email="subb@example.com", username="subb"
    )
    org_b = decode_token(tokens_b["access_token"])["organization_id"]

    sub_a = await client.get(
        "/v1/billing/subscription", headers=auth_headers(tokens_a["access_token"])
    )
    sub_b = await client.get(
        "/v1/billing/subscription", headers=auth_headers(tokens_b["access_token"])
    )
    assert sub_a.status_code == 200 and sub_b.status_code == 200
    assert sub_a.json()["organization_id"] == org_a
    assert sub_b.json()["organization_id"] == org_b
    assert sub_a.json()["organization_id"] != sub_b.json()["organization_id"]
