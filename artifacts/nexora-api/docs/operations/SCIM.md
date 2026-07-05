# SCIM 2.0 Provisioning (RFC 7643 / 7644)

Nexora exposes a SCIM 2.0 endpoint so identity providers (Okta, Microsoft Entra
ID, OneLogin, JumpCloud, …) can **automatically provision and deprovision users
and groups**. It complements interactive SSO (see `SSO.md`): SSO authenticates a
user at login; SCIM keeps the directory of users/groups and their lifecycle in
sync ahead of time.

Supported: **Users**, **Groups**, **PATCH**, **Bulk**, **Deactivate /
Reactivate**, equality **filtering**, **pagination**, and the discovery
endpoints (`ServiceProviderConfig`, `ResourceTypes`, `Schemas`).

---

## Base URL & authentication

```
{SSO_PUBLIC_BASE_URL or origin}{BASE_PATH}/v1/scim/v2
```

e.g. `https://app.example.com/nexora-api/v1/scim/v2`

Every SCIM request authenticates with a **per-organization bearer token**:

```
Authorization: Bearer scim_xxxxxxxx…
```

The token resolves to exactly one organization, so **all operations are scoped
to that tenant** (multi-tenant safe). Tokens are stored only as SHA-256 hashes;
the plaintext is shown once at creation.

### Minting a token (superuser)

```bash
curl -X POST "$BASE/v1/scim/v2/admin/tokens" \
  -H "Authorization: Bearer $SUPERUSER_JWT" -H 'Content-Type: application/json' \
  -d '{"organization_id": "<org-id>", "name": "Okta production"}'
# → { "id": "...", "token_prefix": "scim_abc123", "token": "scim_abc123...", ... }
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/scim/v2/admin/tokens` | Create a token for an org (returns plaintext once). |
| `GET` | `/scim/v2/admin/tokens?organization_id=…` | List tokens (no plaintext). |
| `DELETE` | `/scim/v2/admin/tokens/{id}` | Revoke a token. |

Configure the SCIM connector at the IdP with the base URL above and the token.

---

## Resources

### Users (`/scim/v2/Users`)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/Users` | List; supports `filter=userName eq "x"` / `externalId eq "x"`, `startIndex`, `count`. |
| `POST` | `/Users` | Create; `userName` (email) required. Returns `201` + `Location`. |
| `GET` | `/Users/{id}` | Fetch one. |
| `PUT` | `/Users/{id}` | Full replace of mutable attributes. |
| `PATCH` | `/Users/{id}` | Partial update (see below). |
| `DELETE` | `/Users/{id}` | Deprovision (removes the SCIM resource + org membership). |

Attribute mapping:

| SCIM | Nexora |
|---|---|
| `userName` | `User.email` (canonical, lower-cased) |
| `name.givenName` / `name.familyName` / `displayName` | name fields; `User.full_name` on create |
| `active` | mirrored to `User.is_active` |
| `externalId` | stored on the SCIM resource |

On create, the user is added to the token's organization with the default role
(`SCIM_DEFAULT_ROLE`, default `VIEWER`); the global `User` is created
passwordless if it does not yet exist (SSO/SCIM-only account).

### Groups (`/scim/v2/Groups`)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/Groups` | List; supports `filter=displayName eq "x"`, pagination. |
| `POST` | `/Groups` | Create; `displayName` required; optional `members`. |
| `GET` | `/Groups/{id}` | Fetch one (with members). |
| `PUT` | `/Groups/{id}` | Replace displayName + members. |
| `PATCH` | `/Groups/{id}` | Add/remove/replace `members`, rename `displayName`. |
| `DELETE` | `/Groups/{id}` | Delete the group. |

**Group → role mapping.** A SCIM group's organization role is resolved from the
organization's SSO **role mappings** (`SSOConnection.role_mappings`) by matching
the group's `displayName` (case-insensitive). When a member is added to a
role-bearing group, their `OrganizationMember.role` is set to the **strongest**
role across all groups they belong to (`OWNER > ADMIN > PROJECT_MANAGER >
DEVELOPER > VIEWER`). Roles are only ever upgraded by group membership; removing
a user from a group does not automatically downgrade their role (avoids
clobbering roles set elsewhere). To grant roles via SCIM groups, define the
matching entries in an org-scoped SSO connection's `role_mappings`.

---

## PATCH

`PATCH` bodies use the SCIM PatchOp schema. Both common IdP shapes are accepted:

**Okta-style** (explicit `path`):

```json
{ "Operations": [ { "op": "replace", "path": "active", "value": false } ] }
```

**Microsoft Entra-style** (no `path`, value is an attribute bag):

```json
{ "Operations": [ { "op": "replace", "value": { "active": false } } ] }
```

Supported user paths: `active`, `userName`, `externalId`, `name.givenName`,
`name.familyName`, `displayName`. Supported group paths: `displayName`,
`members` (`add` / `replace` / `remove`, including the Okta filtered form
`members[value eq "<id>"]`). Unknown attributes are ignored (allowed by SCIM).

## Deactivate / Reactivate

Deprovisioning uses the standard `active` attribute via `PATCH` (or `PUT`).
Setting `active=false` mirrors to `User.is_active=false`, which **blocks sign-in
across the platform**; `active=true` reactivates. `DELETE /Users/{id}` removes
the org membership and deactivates the global account when it is no longer
SCIM-managed in any organization.

> **Tenancy note:** because `active` mirrors to the global user, SCIM should be
> treated as the authoritative source for the accounts it manages. In typical
> single-corporate-IdP deployments this is exactly the desired behavior.

## Bulk (`/scim/v2/Bulk`)

```json
{
  "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkRequest"],
  "Operations": [
    { "method": "POST", "path": "/Users",  "bulkId": "u1", "data": { "userName": "a@x.com" } },
    { "method": "PATCH","path": "/Users/<id>", "data": { "Operations": [ { "op":"replace","value":{"active":false} } ] } }
  ]
}
```

Operations are applied sequentially; each result carries its `method`, `status`,
`bulkId` and (for creates) a `location`. Failed operations return a per-op SCIM
error `response` and processing continues unless `failOnErrors` is reached. The
request size is capped by `SCIM_BULK_MAX_OPERATIONS` (default `1000`).

---

## Discovery

`GET /ServiceProviderConfig`, `GET /ResourceTypes`, `GET /Schemas` advertise
capabilities (patch + bulk + filter supported; `oauthbearertoken` auth) so IdP
connectors can self-configure. All discovery endpoints require the bearer token.

## Errors

Errors use the SCIM error envelope (`application/scim+json`):

```json
{ "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"], "status": "409", "scimType": "uniqueness", "detail": "User already exists" }
```

Common: `401` (missing/invalid token), `404` (unknown resource), `409`
(`uniqueness` — duplicate userName/displayName), `400` (`invalidValue` /
`invalidSyntax`), `413` (`tooLarge` — bulk too big).

---

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `SCIM_ENABLED` | `true` | Master switch for all SCIM routes. |
| `SCIM_DEFAULT_ROLE` | `VIEWER` | Org role for provisioned members without a role-bearing group. |
| `SCIM_BULK_MAX_OPERATIONS` | `1000` | Max operations per `/Bulk` request. |

---

## Data model (`app/models/scim.py`)

- **`ScimToken`** — per-org bearer token (SHA-256 hash + display prefix).
- **`ScimUser`** — org-scoped SCIM User resource → global `users` row +
  `organization_members` row.
- **`ScimGroup`** — org-scoped SCIM Group, with a `mapped_role` resolved from SSO
  role mappings.
- **`ScimGroupMember`** — group ↔ SCIM user membership.

Tables are created by migration `0004_scim` (idempotent, `checkfirst=True`).

---

## Tests

`app/tests/test_scim.py` (16 tests) covers: bearer-token auth (missing/invalid),
superuser-only token minting, user create/get/list (filter + pagination)/replace/
delete-deprovision, deactivate & reactivate (Okta and Entra PATCH shapes),
group create with member role mapping, group PATCH add/remove members, group
list/delete, Bulk (success + per-op error reporting), and ServiceProviderConfig.

```bash
python -m pytest app/tests/test_scim.py -q
```
