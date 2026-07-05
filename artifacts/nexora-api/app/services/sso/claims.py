"""Normalized identity claims extracted from an IdP (OIDC or SAML)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SSOClaims:
    """Provider-agnostic identity resolved from an SSO response.

    ``subject`` is the stable external identifier (OIDC ``sub`` / SAML
    ``NameID``). ``groups`` are the raw IdP group/role names used for role and
    organization mapping. ``raw`` keeps the full claim/attribute set for audit.
    """

    subject: str
    email: str
    full_name: str | None = None
    groups: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def email_domain(self) -> str:
        return self.email.split("@", 1)[1].lower() if "@" in self.email else ""
