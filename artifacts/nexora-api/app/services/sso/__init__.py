"""Enterprise SSO subsystem.

* ``claims``       — normalized identity (subject/email/name/groups) from any IdP
* ``provisioning`` — role mapping, JIT user provisioning, org mapping, token issue
* ``oidc``         — OIDC/OAuth2 authorization-code flow (Entra/Okta/Google/Ping)
* ``saml``         — SAML 2.0 SP (metadata, AuthnRequest, signed-assertion ACS)
* ``state``        — short-lived OIDC state/nonce/PKCE store (CSRF protection)
* ``presets``      — provider-specific endpoint/scope defaults
"""

from app.services.sso.claims import SSOClaims

__all__ = ["SSOClaims"]
