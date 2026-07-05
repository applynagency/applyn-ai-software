# Enterprise SSO (OIDC / OAuth2 / SAML)

Nexora supports enterprise single sign-on against any standards-compliant
identity provider. Two protocols are implemented:

- **OIDC / OAuth2 (Authorization Code + PKCE)** — Microsoft Entra ID (Azure AD),
  Okta, Google Workspace, Ping (PingOne / PingFederate) and any generic OIDC
  provider. One engine drives all of them; only configuration differs.
- **SAML 2.0** (SP-initiated, HTTP-POST ACS) — any SAML IdP, with XML-DSIG
  signature verification of the assertion.

Both protocols share one provisioning pipeline: **role mapping**, **automatic
(JIT) provisioning**, and **organization mapping**, then issue standard Nexora
access/refresh tokens (identical to password login, including server-side
session registration and the JWT denylist).

---

## Architecture

```
                       ┌─────────────────────────────┐
  /auth/sso/{slug}/    │  app/api/v1/sso.py          │
  login  callback  acs │  (routes + admin CRUD)      │
                       └───────────────┬─────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                               ▼                              ▼
  services/sso/oidc.py          services/sso/saml.py          services/sso/state.py
  discovery / authz URL /       SP metadata / AuthnRequest /  OIDC state+nonce+PKCE
  code exchange / JWKS verify   ACS signature + conditions    (cache-backed, single use)
        └──────────────┬───────────────┘
                       ▼
            services/sso/provisioning.py   ──►  SSOClaims (subject/email/name/groups)
            role mapping · JIT provisioning · org mapping · issue_tokens()
                       │
        ┌──────────────┴───────────────┐
        ▼                               ▼
   models/sso.py                  app/auth/token_service.py
   SSOConnection / SSOIdentity    access+refresh (organization_id + role claims)
```

### Data model (`app/models/sso.py`)

- **`SSOConnection`** — a configured IdP connection (OIDC or SAML). Scoped to one
  organization (`organization_id`) or **tenant-wide** (`organization_id = NULL`,
  with org chosen by claim mapping). Stores protocol/provider, claim mappings,
  role/org mappings, and protocol endpoints/secrets. The OIDC `client_secret` is
  stored **AES-256-GCM encrypted** (`app.security.secrets.get_cipher`) and is
  never returned by the API.
- **`SSOIdentity`** — links an external IdP subject (OIDC `sub` / SAML `NameID`)
  to a local `users.id`, so repeat logins resolve to the same account.

`users.hashed_password` is **nullable**: SSO-only users have no local password
and cannot log in via `/auth/login` (the password path rejects null-password
accounts).

---

## Configuration (`app/core/config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `SSO_ENABLED` | `true` | Master switch for all SSO routes. |
| `SSO_PUBLIC_BASE_URL` | `None` | Absolute public origin (`https://app.example.com`) used to build IdP-facing redirect/callback/ACS/metadata URLs. When unset, the incoming request's base URL is used. **Set this behind a proxy/load balancer.** |
| `SSO_STATE_TTL_SECONDS` | `600` | TTL of the OIDC state/nonce/PKCE record. |
| `SSO_DEFAULT_ROLE` | `VIEWER` | Fallback org role when no role mapping matches. |
| `SSO_ALLOW_UNSIGNED_SAML` | `false` | **DEV ONLY.** Skip SAML signature verification. Never enable in production. |

> **Note:** the OIDC state store uses the unified cache layer
> (`app.redis.cache`), so `CACHE_ENABLED` must be `true` (the default). With a
> configured `REDIS_URL`, state survives across API replicas; otherwise it falls
> back to per-process memory (single-replica only).

The IdP secret encryption requires `MASTER_ENCRYPTION_KEY` to be set.

---

## API

All routes are under `{BASE_PATH}/v1/auth/sso`.

### Public (login)

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/sso/providers` | List enabled providers (slug, display name, protocol, `login_url`) for the login page. |
| `GET` | `/auth/sso/{slug}/login` | Begin login. Redirects (307) to the IdP (OIDC authorization request or SAML AuthnRequest). |
| `GET` | `/auth/sso/{slug}/callback` | OIDC authorization-code callback. Returns a `TokenResponse`. |
| `POST` | `/auth/sso/{slug}/acs` | SAML Assertion Consumer Service (form field `SAMLResponse`). Returns a `TokenResponse`. |
| `GET` | `/auth/sso/{slug}/metadata` | SAML SP metadata (XML) for IdP onboarding. |

### Admin (superuser only)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/sso/connections` | Create a connection. `client_secret` is write-only. |
| `GET` | `/auth/sso/connections` | List all connections (secrets hidden). |
| `GET` | `/auth/sso/connections/{id}` | Get one connection. |
| `PATCH` | `/auth/sso/connections/{id}` | Update fields (pass `client_secret` to rotate, `null` to clear). |
| `DELETE` | `/auth/sso/connections/{id}` | Delete a connection. |

Connection responses expose `has_client_secret` / `has_idp_certificate` flags
instead of the secret/cert material.

---

## Provisioning pipeline (`SSOProvisioningService`)

On every successful SSO authentication:

1. **Domain restriction** — if `allowed_email_domains` is set, the claim email's
   domain must be in the list (else `403`).
2. **User resolution** —
   - link by `SSOIdentity (connection, external_subject)`, else
   - match an existing user by email, else
   - **JIT-provision** a new user (if `auto_provision`), with a unique username
     derived from the email and `hashed_password = NULL`.
   - The external subject is linked to the user for future logins.
3. **Role mapping** — each IdP group/role is looked up in `role_mappings`
   (`{idp_group: OrganizationRole}`, case-insensitive). The **highest-privilege**
   match wins (`OWNER > ADMIN > PROJECT_MANAGER > DEVELOPER > VIEWER`). With no
   match, the connection `default_role` (then `SSO_DEFAULT_ROLE`) is used.
4. **Organization mapping** —
   - connection-scoped: use `organization_id`;
   - tenant-wide: match a group or email domain against `organization_mappings`
     (`{group_or_domain: organization_slug}`); else
   - fall back to the user's primary organization (creating a default if none).
5. **Membership** — create or update the `OrganizationMember` row so the org role
   stays in sync with the IdP on every login.
6. **Tokens** — `issue_tokens()` mints access/refresh tokens with
   `organization_id` + `role` claims, registers the session, and writes a
   `sso.login` audit log.

---

## Provider setup

### OIDC (Entra / Okta / Google / Ping / generic)

Minimum fields: `protocol=OIDC`, `provider`, `client_id`, `client_secret`, and
**either** `issuer` (discovery is derived as `{issuer}/.well-known/openid-configuration`)
**or** the explicit `authorization_endpoint` + `token_endpoint` + `jwks_uri`.

Register this redirect URI at the IdP:

```
{SSO_PUBLIC_BASE_URL}{BASE_PATH}/v1/auth/sso/{slug}/callback
```

- **Microsoft Entra ID** — `issuer = https://login.microsoftonline.com/<tenant-id>/v2.0`.
  To receive groups, configure the app registration's token "groups" claim and
  set `groups_claim` accordingly.
- **Okta** — `issuer = https://<org>.okta.com/oauth2/default` (or a custom auth
  server). Add a `groups` claim to the ID token; default `groups_claim=groups`.
- **Google Workspace** — `issuer = https://accounts.google.com`. Google does not
  emit group claims by default; use `organization_mappings`/`role_mappings` keyed
  on the email domain, or sync groups via a custom claim.
- **Ping** — set `issuer` to the PingOne/PingFederate issuer; group claim is
  often `group` (`groups_claim=group`).

PKCE (S256) is enabled by default (`use_pkce`). The ID token signature is
verified against the provider JWKS (by `kid`), and `iss`, `aud` (client id),
`exp` and `nonce` are validated.

Example (create an Okta connection):

```bash
curl -X POST "$BASE/v1/auth/sso/connections" \
  -H "Authorization: Bearer $SUPERUSER_TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "slug": "acme-okta", "display_name": "Acme (Okta)",
    "protocol": "OIDC", "provider": "OKTA",
    "issuer": "https://acme.okta.com/oauth2/default",
    "client_id": "0oa...", "client_secret": "...",
    "groups_claim": "groups",
    "role_mappings": {"platform-admins": "ADMIN", "engineers": "DEVELOPER"},
    "default_role": "VIEWER",
    "allowed_email_domains": ["acme.com"]
  }'
```

### SAML 2.0

Minimum fields: `protocol=SAML`, `idp_entity_id`, `idp_sso_url`, `idp_x509_cert`
(PEM or bare base64 DER), and `sp_entity_id`. Configure the IdP with:

- **ACS URL**: `{SSO_PUBLIC_BASE_URL}{BASE_PATH}/v1/auth/sso/{slug}/acs` (HTTP-POST)
- **SP Entity ID**: your `sp_entity_id`
- **SP metadata**: `GET /auth/sso/{slug}/metadata`

The ACS:

1. base64-decodes `SAMLResponse` and parses it with a **hardened lxml parser**
   (no DTD, no network, no entity expansion → XXE-safe);
2. verifies the XML-DSIG signature with `signxml` against `idp_x509_cert`
   (required unless `SSO_ALLOW_UNSIGNED_SAML`);
3. validates `Conditions` (NotBefore/NotOnOrAfter with 5-min skew), the
   `AudienceRestriction` against `sp_entity_id`, and subject confirmation expiry;
4. extracts `NameID` + attributes (`email_claim`, `name_claim`, `groups_claim`)
   and runs the shared provisioning pipeline.

Tampering with a signed assertion (or an unsigned assertion) is rejected with
`401`.

---

## Security properties

- **CSRF / replay**: single-use `state` (cache, short TTL) + `nonce` checked on
  the ID token.
- **PKCE**: S256 code challenge by default.
- **Token verification**: ID tokens verified by JWKS (`kid`), with `iss`/`aud`/
  `exp`/`nonce` checks; SAML assertions verified by XML-DSIG.
- **SSRF-safe egress**: all discovery/JWKS/token/userinfo calls go through
  `app.security.ssrf.safe_http_client` (public IdPs work out of the box; on-prem
  IdPs require `SSRF_ALLOW_PRIVATE_NETWORKS=true`).
- **Secret hygiene**: client secrets AES-256-GCM encrypted at rest, never
  returned by the API; XML parsing hardened against XXE/entity-expansion.
- **No-password accounts**: SSO-only users cannot authenticate via the password
  endpoint.

---

## Tests

`app/tests/test_sso.py` (17 tests) covers, with **no live IdP**:

- role mapping (highest-privilege + default fallback);
- admin CRUD (secret hidden, superuser-only, duplicate-slug conflict);
- provider discovery + OIDC login redirect (PKCE/nonce/state present);
- OIDC callback end-to-end with a locally **RS256-signed ID token** verified
  against a JWKS built from the public key (provisioning + role mapping);
- security: bad/expired state, nonce mismatch, domain restriction, auto-provision
  disabled;
- organization mapping (tenant-wide → mapped org);
- SAML SP metadata, SAML ACS end-to-end with a **signxml-signed** response, and
  rejection of a tampered assertion.

Run them:

```bash
python -m pytest app/tests/test_sso.py -q
```
