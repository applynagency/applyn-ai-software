"""Enterprise identity & access platform (Sprint 61A).

Net-new identity primitives layered on top of the existing SSO / SCIM / audit
stack:

* ``api_keys`` — organization / personal / service-account API keys.
* ``service_accounts`` — non-human organization principals.
* ``sessions`` — database-backed sessions with refresh-token rotation.
* ``security_policy`` — per-organization configurable security controls.
* ``mfa`` — TOTP enrollment + single-use recovery codes.
* ``totp`` — dependency-free RFC 6238 TOTP implementation.
* ``scopes`` — the permission scope catalog shared by API keys & service
  accounts.
"""
