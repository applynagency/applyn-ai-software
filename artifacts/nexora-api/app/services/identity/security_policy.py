"""Per-organization security policy: storage, retrieval and enforcement helpers."""

from __future__ import annotations

import ipaddress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.identity import OrganizationSecurityPolicy
from app.redis import cache
from app.repositories.audit import AuditLogRepository

_POLICY_FIELDS = (
    "password_min_length",
    "password_require_uppercase",
    "password_require_lowercase",
    "password_require_number",
    "password_require_symbol",
    "mfa_required",
    "session_timeout_minutes",
    "max_concurrent_sessions",
    "allowed_email_domains",
    "ip_allowlist",
    "api_keys_enabled",
    "api_key_max_age_days",
)


def org_settings_namespace(organization_id: str) -> str:
    return f"org-settings:{organization_id}"


class PolicyViolation(Exception):
    """Raised when an action violates the organization security policy."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SecurityPolicyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def get(self, organization_id: str) -> OrganizationSecurityPolicy | None:
        return await self.session.scalar(
            select(OrganizationSecurityPolicy).where(
                OrganizationSecurityPolicy.organization_id == organization_id
            )
        )

    async def get_or_create(self, organization_id: str) -> OrganizationSecurityPolicy:
        policy = await self.get(organization_id)
        if policy is None:
            policy = OrganizationSecurityPolicy(organization_id=organization_id)
            self.session.add(policy)
            await self.session.flush()
        return policy

    async def get_settings(self, organization_id: str) -> dict | None:
        """Distributed, versioned-cached read of an org's policy as a plain dict.

        Use on hot read paths (login concurrency, API-key policy checks) to avoid
        a DB round trip per request. Invalidated automatically on ``update``.
        """
        ns = org_settings_namespace(organization_id)
        cached = await cache.versioned_get(ns, "policy")
        if cached is not None:
            return cached if cached else None
        policy = await self.get(organization_id)
        data = _serialize_policy(policy) if policy is not None else {}
        try:
            await cache.versioned_set(
                ns, "policy", value=data, ttl=settings.ORG_SETTINGS_CACHE_TTL_SECONDS
            )
        except Exception:  # pragma: no cover - cache must not break reads
            pass
        return data or None

    async def update(
        self,
        organization_id: str,
        changes: dict,
        *,
        actor_user_id: str | None = None,
    ) -> OrganizationSecurityPolicy:
        policy = await self.get_or_create(organization_id)
        allowed = {
            "password_min_length",
            "password_require_uppercase",
            "password_require_lowercase",
            "password_require_number",
            "password_require_symbol",
            "mfa_required",
            "session_timeout_minutes",
            "max_concurrent_sessions",
            "allowed_email_domains",
            "ip_allowlist",
            "api_keys_enabled",
            "api_key_max_age_days",
        }
        for field, value in changes.items():
            if field in allowed and value is not None:
                if field == "ip_allowlist" and value:
                    _validate_cidrs(value)
                setattr(policy, field, value)
        policy.updated_by = actor_user_id
        self.session.add(policy)
        await self.session.flush()
        try:
            await cache.invalidate(org_settings_namespace(organization_id))
        except Exception:  # pragma: no cover - cache must not break writes
            pass
        await self.audit.log(
            action="security_policy.updated",
            resource_type="security_policy",
            resource_id=policy.id,
            user_id=actor_user_id,
            organization_id=organization_id,
            details={k: changes[k] for k in changes if k in allowed},
        )
        return policy

    # --- enforcement helpers -------------------------------------------------

    def validate_password(
        self, password: str, policy: OrganizationSecurityPolicy | None
    ) -> None:
        if policy is None:
            return
        errors: list[str] = []
        if len(password) < policy.password_min_length:
            errors.append(f"at least {policy.password_min_length} characters")
        if policy.password_require_uppercase and not any(c.isupper() for c in password):
            errors.append("an uppercase letter")
        if policy.password_require_lowercase and not any(c.islower() for c in password):
            errors.append("a lowercase letter")
        if policy.password_require_number and not any(c.isdigit() for c in password):
            errors.append("a number")
        if policy.password_require_symbol and password.isalnum():
            errors.append("a symbol")
        if errors:
            raise PolicyViolation("Password must contain " + ", ".join(errors))

    def check_email_domain(
        self, email: str, policy: OrganizationSecurityPolicy | None
    ) -> bool:
        if policy is None or not policy.allowed_email_domains:
            return True
        domain = email.rsplit("@", 1)[-1].lower()
        return domain in {d.lower() for d in policy.allowed_email_domains}

    def check_ip_allowed(
        self, ip: str | None, policy: OrganizationSecurityPolicy | None
    ) -> bool:
        if policy is None or not policy.ip_allowlist:
            return True
        if not ip:
            return False
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for cidr in policy.ip_allowlist:
            try:
                if addr in ipaddress.ip_network(cidr, strict=False):
                    return True
            except ValueError:
                continue
        return False


def _serialize_policy(policy: OrganizationSecurityPolicy) -> dict:
    return {field: getattr(policy, field) for field in _POLICY_FIELDS}


def _validate_cidrs(values: list[str]) -> None:
    for cidr in values:
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise PolicyViolation(f"Invalid CIDR/IP in allow list: {cidr}") from exc
