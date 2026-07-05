"""Commercial platform API (Sprint 61C).

Org-scoped endpoints (subscription, usage, plans catalog, license, feature flags,
webhooks) plus platform-admin (superuser) endpoints for plan management,
plan assignment, suspend/resume, quota overrides, usage reports and licensing.
A Stripe inbound webhook endpoint reconciles provider events.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.auth.dependencies import CurrentSuperuser, DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.core.config import settings
from app.models.billing import BillingProviderType, Invoice, LicenseType, SubscriptionStatus
from app.models.organization import OrganizationRole
from app.schemas.billing import (
    AssignPlanRequest,
    FeatureFlagsResponse,
    InvoiceListResponse,
    InvoiceResponse,
    LicenseIssuedResponse,
    LicenseIssueRequest,
    LicenseResponse,
    LicenseValidateRequest,
    PaymentMethodListResponse,
    PaymentMethodView,
    PlanCloneRequest,
    PlanCreate,
    PlanListResponse,
    PlanResponse,
    PlanUpdate,
    QuotaOverrideRequest,
    StripeCheckoutRequest,
    StripePortalRequest,
    StripeSessionResponse,
    StripeStatusResponse,
    SubscriptionResponse,
    SuspendRequest,
    UsageDashboardResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
)
from app.services.billing.feature_flags import FeatureFlagService
from app.services.billing.licenses import LicenseError, LicenseService
from app.services.billing.plans import PlanError, PlanService
from app.services.billing.providers import StripeProvider, get_provider
from app.services.billing.quota import QuotaService
from app.services.billing.subscriptions import SubscriptionError, SubscriptionService
from app.services.billing.usage_dashboard import UsageDashboardService
from app.services.billing.webhooks import BillingWebhookService

router = APIRouter(prefix="/billing", tags=["Billing"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _require_org(ctx: OrgContext) -> str:
    return ctx.requires_organization


def _require_org_admin(ctx: OrgContext) -> str:
    org_id = ctx.requires_organization
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )
    return org_id


# --- Org-scoped: catalog, subscription, usage, features ----------------------
@router.get("/plans", response_model=PlanListResponse)
async def list_plans(session: DBSession, ctx: OrgContextDep):
    svc = PlanService(session)
    plans = await svc.list(public_only=not ctx.user.is_superuser)
    if not plans and settings.BILLING_SEED_DEFAULT_PLANS:
        await svc.seed_defaults()
        await session.commit()
        plans = await svc.list(public_only=not ctx.user.is_superuser)
    return PlanListResponse(items=[PlanResponse.model_validate(p) for p in plans], total=len(plans))


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org(ctx)
    sub = await SubscriptionService(session).get_or_create(org_id)
    await session.commit()
    return SubscriptionResponse.model_validate(sub)


@router.get("/usage", response_model=UsageDashboardResponse)
async def usage_dashboard(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org(ctx)
    snap = await UsageDashboardService(session).snapshot(org_id)
    await session.commit()
    return UsageDashboardResponse(**snap)


@router.get("/feature-flags", response_model=FeatureFlagsResponse)
async def feature_flags(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org(ctx)
    flags = await FeatureFlagService(session).all_flags(org_id)
    await session.commit()
    return FeatureFlagsResponse(organization_id=org_id, flags=flags)


@router.get("/license")
async def my_license(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org(ctx)
    lic = await LicenseService(session).active_for_org(org_id)
    if lic is None:
        return {"organization_id": org_id, "license": None}
    return {
        "organization_id": org_id,
        "license": {
            "license_type": lic.license_type,
            "status": lic.status,
            "plan_slug": lic.plan_slug,
            "seats": lic.seats,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        },
    }


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    session: DBSession,
    ctx: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
):
    """List organization invoices (read-only). Omits provider IDs and line items."""
    org_id = _require_org_admin(ctx)
    filters = [Invoice.organization_id == org_id]
    if status:
        filters.append(Invoice.status == status.upper())
    if start:
        filters.append(Invoice.created_at >= start)
    if end:
        filters.append(Invoice.created_at <= end)

    total = (
        await session.execute(select(func.count()).select_from(Invoice).where(*filters))
    ).scalar_one()
    rows = (
        await session.execute(
            select(Invoice)
            .where(*filters)
            .order_by(Invoice.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return InvoiceListResponse(
        items=[InvoiceResponse.model_validate(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/payment-methods", response_model=PaymentMethodListResponse)
async def list_payment_methods(session: DBSession, ctx: OrgContextDep):
    """Read-only payment methods — never returns full card numbers or tokens."""
    org_id = _require_org_admin(ctx)
    stripe = StripeProvider(session)
    configured = stripe.configured
    items: list[PaymentMethodView] = []
    if configured:
        sub = await SubscriptionService(session).get_or_create(org_id)
        raw = await stripe.list_payment_methods(org_id, sub)
        items = [PaymentMethodView.model_validate(row) for row in raw]
    return PaymentMethodListResponse(
        items=items,
        stripe_configured=configured,
        self_serve_enabled=configured,
    )


@router.get("/stripe/status", response_model=StripeStatusResponse)
async def stripe_status(session: DBSession, ctx: OrgContextDep):
    _require_org_admin(ctx)
    stripe = StripeProvider(session)
    return StripeStatusResponse(
        configured=stripe.configured,
        self_serve_enabled=stripe.configured,
    )


@router.post("/stripe/checkout", response_model=StripeSessionResponse)
async def stripe_checkout(body: StripeCheckoutRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    stripe = StripeProvider(session)
    sub_svc = SubscriptionService(session)
    sub = await sub_svc.get_or_create(org_id)
    plan_id = body.plan_id or sub.plan_id
    plan = await PlanService(session).get(plan_id) if plan_id else None
    result = await stripe.create_checkout_session(
        organization_id=org_id,
        email=ctx.user.email,
        price_id=getattr(plan, "external_price_id", None) if plan else None,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
        subscription=sub,
    )
    await session.commit()
    return StripeSessionResponse(**result)


@router.post("/stripe/portal", response_model=StripeSessionResponse)
async def stripe_portal(body: StripePortalRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    stripe = StripeProvider(session)
    sub = await SubscriptionService(session).get_or_create(org_id)
    result = await stripe.create_portal_session(
        organization_id=org_id,
        customer_id=sub.external_customer_id,
        return_url=body.return_url,
        subscription=sub,
    )
    await session.commit()
    return StripeSessionResponse(**result)


# --- Org-scoped webhook endpoint management ----------------------------------
@router.get("/webhooks", response_model=list[WebhookEndpointResponse])
async def list_webhooks(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    eps = await BillingWebhookService(session).list_endpoints(org_id)
    return [WebhookEndpointResponse.model_validate(e) for e in eps]


@router.post("/webhooks", response_model=WebhookEndpointResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(body: WebhookEndpointCreate, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    ep = await BillingWebhookService(session).add_endpoint(
        org_id, body.url, secret=body.secret, events=body.events
    )
    await session.commit()
    return WebhookEndpointResponse.model_validate(ep)


# --- Admin (platform superuser): plan management -----------------------------
@router.post("/admin/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(body: PlanCreate, session: DBSession, user: CurrentSuperuser):
    try:
        plan = await PlanService(session).create(body.model_dump(exclude_none=True),
                                                 actor_user_id=user.id)
    except PlanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return PlanResponse.model_validate(plan)


@router.patch("/admin/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(plan_id: str, body: PlanUpdate, session: DBSession, user: CurrentSuperuser):
    try:
        plan = await PlanService(session).update(plan_id, body.model_dump(exclude_none=True),
                                                 actor_user_id=user.id)
    except PlanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return PlanResponse.model_validate(plan)


@router.post("/admin/plans/{plan_id}/clone", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def clone_plan(plan_id: str, body: PlanCloneRequest, session: DBSession, user: CurrentSuperuser):
    try:
        plan = await PlanService(session).clone(plan_id, new_name=body.name,
                                                new_slug=body.slug, actor_user_id=user.id)
    except PlanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return PlanResponse.model_validate(plan)


# --- Admin: org subscription management --------------------------------------
@router.post("/admin/orgs/{org_id}/assign-plan", response_model=SubscriptionResponse)
async def assign_plan(org_id: str, body: AssignPlanRequest, session: DBSession, user: CurrentSuperuser):
    try:
        sub = await SubscriptionService(session).assign_plan(
            org_id, body.plan_id, provider=body.provider, actor_user_id=user.id
        )
    except SubscriptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post("/admin/orgs/{org_id}/suspend", response_model=SubscriptionResponse)
async def suspend_org(org_id: str, body: SuspendRequest, session: DBSession, user: CurrentSuperuser):
    sub = await SubscriptionService(session).suspend(org_id, actor_user_id=user.id, reason=body.reason)
    await session.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post("/admin/orgs/{org_id}/resume", response_model=SubscriptionResponse)
async def resume_org(org_id: str, session: DBSession, user: CurrentSuperuser):
    sub = await SubscriptionService(session).resume(org_id, actor_user_id=user.id)
    await session.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post("/admin/orgs/{org_id}/quota-overrides")
async def set_quota_override(org_id: str, body: QuotaOverrideRequest, session: DBSession,
                            user: CurrentSuperuser):
    ov = await QuotaService(session).set_override(
        org_id, body.metric, body.limit_value, note=body.note, actor_user_id=user.id
    )
    await session.commit()
    return {"id": ov.id, "metric": ov.metric, "limit_value": ov.limit_value}


@router.get("/admin/orgs/{org_id}/usage-report", response_model=UsageDashboardResponse)
async def org_usage_report(org_id: str, session: DBSession, user: CurrentSuperuser):
    snap = await UsageDashboardService(session).snapshot(org_id)
    await session.commit()
    return UsageDashboardResponse(**snap)


# --- Admin: licensing --------------------------------------------------------
@router.post("/admin/licenses", response_model=LicenseIssuedResponse, status_code=status.HTTP_201_CREATED)
async def issue_license(body: LicenseIssueRequest, session: DBSession, user: CurrentSuperuser):
    try:
        lic, token = await LicenseService(session).issue(
            organization_id=body.organization_id,
            license_type=LicenseType(body.license_type),
            plan_slug=body.plan_slug, seats=body.seats,
            features=body.features, limits=body.limits, expires_at=body.expires_at,
            actor_user_id=user.id,
        )
    except (LicenseError, ValueError) as exc:
        detail = getattr(exc, "message", str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 400), detail=detail) from None
    await session.commit()
    resp = LicenseResponse.model_validate(lic).model_dump()
    return LicenseIssuedResponse(**resp, offline_token=token)


@router.post("/licenses/validate")
async def validate_license(body: LicenseValidateRequest, session: DBSession, ctx: OrgContextDep):
    svc = LicenseService(session)
    if body.offline_token:
        return svc.validate_offline(body.offline_token)
    if body.license_key:
        return await svc.validate(body.license_key)
    raise HTTPException(status_code=400, detail="license_key or offline_token required")


# --- Stripe inbound webhook --------------------------------------------------
@router.post("/webhooks/stripe", include_in_schema=True)
async def stripe_webhook(request: Request, session: DBSession):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    if not StripeProvider.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="invalid signature")
    import json

    try:
        event = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid payload") from None
    event_type = event.get("type", "")
    org_id = (event.get("data", {}).get("object", {}).get("metadata", {}) or {}).get("organization_id")
    sub_svc = SubscriptionService(session)
    if org_id:
        if event_type in ("invoice.payment_succeeded", "checkout.session.completed"):
            await sub_svc.transition(org_id, SubscriptionStatus.ACTIVE, reason="stripe_payment")
            await BillingWebhookService(session).emit(org_id, "payment.received",
                                                      {"source": "stripe", "type": event_type})
        elif event_type == "invoice.payment_failed":
            await sub_svc.transition(org_id, SubscriptionStatus.OVERDUE, reason="stripe_payment_failed")
        elif event_type == "customer.subscription.deleted":
            await sub_svc.transition(org_id, SubscriptionStatus.CANCELLED, reason="stripe_cancelled")
    await session.commit()
    return {"received": True, "type": event_type}


# Provider factory re-exported for tests/admin use.
__all__ = ["router", "get_provider", "BillingProviderType"]
