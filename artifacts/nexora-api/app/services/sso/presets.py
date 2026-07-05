"""Provider-specific OIDC defaults (scopes, claim names, discovery hints).

All four named providers (Microsoft Entra, Okta, Google Workspace, Ping) are
standards-compliant OIDC providers, so the same authorization-code engine drives
all of them; presets only supply sensible defaults so admins configure less.
"""

from __future__ import annotations

from app.models.sso import SSOProvider

# Default OIDC scopes per provider. ``groups``/role claims usually require extra
# IdP-side configuration, so we request the standard set and read whatever group
# claim the connection specifies.
PROVIDER_DEFAULTS: dict[str, dict] = {
    SSOProvider.ENTRA.value: {
        "scopes": ["openid", "email", "profile"],
        "groups_claim": "groups",
        # Entra issuers look like https://login.microsoftonline.com/<tenant>/v2.0
    },
    SSOProvider.OKTA.value: {
        "scopes": ["openid", "email", "profile", "groups"],
        "groups_claim": "groups",
    },
    SSOProvider.GOOGLE.value: {
        "scopes": ["openid", "email", "profile"],
        "groups_claim": "groups",
        "issuer": "https://accounts.google.com",
    },
    SSOProvider.PING.value: {
        "scopes": ["openid", "email", "profile"],
        "groups_claim": "group",
    },
    SSOProvider.AUTH0.value: {
        # Auth0 issues groups/roles via a custom (namespaced) claim configured
        # through an Auth0 Action/Rule; admins set groups_claim accordingly.
        "scopes": ["openid", "email", "profile"],
        "groups_claim": "groups",
    },
    SSOProvider.KEYCLOAK.value: {
        # Keycloak exposes realm/client roles; a "groups" client scope/mapper is
        # the common convention.
        "scopes": ["openid", "email", "profile"],
        "groups_claim": "groups",
    },
    SSOProvider.GENERIC_OIDC.value: {
        "scopes": ["openid", "email", "profile"],
        "groups_claim": "groups",
    },
}


def default_scopes(provider: str) -> list[str]:
    return list(PROVIDER_DEFAULTS.get(provider, {}).get("scopes", ["openid", "email", "profile"]))


def discovery_url_for(issuer: str | None, discovery_url: str | None) -> str | None:
    """Resolve the OIDC discovery document URL.

    Prefers an explicit ``discovery_url``; otherwise derives the well-known path
    from the issuer (the standard OIDC discovery convention).
    """
    if discovery_url:
        return discovery_url
    if issuer:
        return issuer.rstrip("/") + "/.well-known/openid-configuration"
    return None
