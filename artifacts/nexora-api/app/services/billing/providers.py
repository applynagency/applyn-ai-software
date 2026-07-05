"""Billing provider abstraction (Sprint 61C).

A single interface (:class:`BillingProvider`) with interchangeable backends:
* :class:`StripeProvider`     — real Stripe when configured, stub otherwise
* :class:`ManualInvoiceProvider` — operator-issued invoices
* :class:`EnterpriseContractProvider` — offline/negotiated contracts

The provider is replaceable via :func:`get_provider`; no caller depends on a
concrete backend. License validation never goes through here.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import BillingProviderType, Invoice, InvoiceStatus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class BillingProvider(ABC):
    """Common interface every billing backend implements."""

    type: BillingProviderType

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @abstractmethod
    async def create_customer(self, organization_id: str, email: str | None = None) -> str:
        ...

    @abstractmethod
    async def create_invoice(
        self, organization_id: str, amount_cents: int, *, currency: str = "USD",
        line_items: list | None = None,
    ) -> Invoice:
        ...

    @abstractmethod
    async def mark_paid(self, invoice: Invoice, *, external_id: str | None = None) -> Invoice:
        ...

    async def _persist_invoice(
        self, organization_id: str, amount_cents: int, currency: str,
        line_items: list | None, external_id: str | None = None,
        status: str = InvoiceStatus.OPEN.value,
    ) -> Invoice:
        inv = Invoice(
            organization_id=organization_id, provider=self.type.value,
            status=status, amount_cents=amount_cents, currency=currency,
            line_items=line_items, external_id=external_id,
        )
        self.session.add(inv)
        await self.session.flush()
        return inv


class ManualInvoiceProvider(BillingProvider):
    type = BillingProviderType.MANUAL

    async def create_customer(self, organization_id: str, email: str | None = None) -> str:
        return f"manual_{organization_id}"

    async def create_invoice(self, organization_id, amount_cents, *, currency="USD", line_items=None) -> Invoice:
        return await self._persist_invoice(organization_id, amount_cents, currency, line_items)

    async def mark_paid(self, invoice: Invoice, *, external_id: str | None = None) -> Invoice:
        invoice.status = InvoiceStatus.PAID.value
        invoice.paid_at = _now()
        if external_id:
            invoice.external_id = external_id
        self.session.add(invoice)
        await self.session.flush()
        return invoice


class EnterpriseContractProvider(ManualInvoiceProvider):
    """Enterprise contracts behave like manual invoicing with a contract marker."""

    type = BillingProviderType.ENTERPRISE

    async def create_customer(self, organization_id: str, email: str | None = None) -> str:
        return f"contract_{organization_id}"


class StripeProvider(BillingProvider):
    type = BillingProviderType.STRIPE

    @property
    def configured(self) -> bool:
        return bool(settings.STRIPE_API_KEY)

    async def create_customer(self, organization_id: str, email: str | None = None) -> str:
        if not self.configured:
            logger.info("stripe_stub_create_customer", extra={"org": organization_id})
            return f"cus_stub_{organization_id[:8]}"
        # Real Stripe call would go here (stripe SDK / httpx). Kept abstracted so
        # the rest of the platform is provider-agnostic.
        return await self._stripe_create_customer(organization_id, email)

    async def create_invoice(self, organization_id, amount_cents, *, currency="USD", line_items=None) -> Invoice:
        external_id = None if not self.configured else f"in_{organization_id[:8]}"
        return await self._persist_invoice(
            organization_id, amount_cents, currency, line_items, external_id=external_id
        )

    async def mark_paid(self, invoice: Invoice, *, external_id: str | None = None) -> Invoice:
        invoice.status = InvoiceStatus.PAID.value
        invoice.paid_at = _now()
        if external_id:
            invoice.external_id = external_id
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def _stripe_create_customer(self, organization_id: str, email: str | None) -> str:  # pragma: no cover - network
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.stripe.com/v1/customers",
                headers={"Authorization": f"Bearer {settings.STRIPE_API_KEY}"},
                data={"metadata[organization_id]": organization_id, "email": email or ""},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """Verify a Stripe webhook signature (HMAC-SHA256 of the payload).

        Simplified scheme using STRIPE_WEBHOOK_SECRET. In stub mode (no secret)
        it accepts the event so local/dev flows work.
        """
        secret = settings.STRIPE_WEBHOOK_SECRET
        if not secret:
            return True
        import hashlib
        import hmac

        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, (signature or "").split(",")[-1].strip())


_PROVIDERS = {
    BillingProviderType.STRIPE: StripeProvider,
    BillingProviderType.MANUAL: ManualInvoiceProvider,
    BillingProviderType.ENTERPRISE: EnterpriseContractProvider,
}


def get_provider(provider: BillingProviderType | str, session: AsyncSession) -> BillingProvider:
    if isinstance(provider, str):
        provider = BillingProviderType(provider)
    cls = _PROVIDERS.get(provider, ManualInvoiceProvider)
    return cls(session)
