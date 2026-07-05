"""ORM ⇄ SCIM JSON serialization (RFC 7643)."""

from __future__ import annotations

from datetime import datetime

from app.models.scim import ScimGroup, ScimUser

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
PATCH_OP_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
BULK_REQUEST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:BulkRequest"
BULK_RESPONSE_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:BulkResponse"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.isoformat()


def _meta(resource_type: str, resource, location: str) -> dict:
    return {
        "resourceType": resource_type,
        "created": _iso(getattr(resource, "created_at", None)),
        "lastModified": _iso(getattr(resource, "updated_at", None)),
        "location": location,
    }


def scim_user_to_dict(user: ScimUser, *, location: str) -> dict:
    formatted = " ".join(p for p in [user.given_name, user.family_name] if p) or None
    body: dict = {
        "schemas": [USER_SCHEMA],
        "id": user.id,
        "userName": user.user_name,
        "active": user.active,
        "name": {
            "givenName": user.given_name,
            "familyName": user.family_name,
            "formatted": user.display_name or formatted,
        },
        "displayName": user.display_name or formatted or user.user_name,
        "emails": [{"value": user.user_name, "primary": True}],
        "meta": _meta("User", user, location),
    }
    if user.external_id:
        body["externalId"] = user.external_id
    return body


def scim_group_to_dict(
    group: ScimGroup, members: list[tuple[str, str, str]], *, location: str
) -> dict:
    """``members`` is a list of ``(scim_user_id, user_name, member_location)``."""
    body: dict = {
        "schemas": [GROUP_SCHEMA],
        "id": group.id,
        "displayName": group.display_name,
        "members": [
            {"value": uid, "display": name, "$ref": ref}
            for uid, name, ref in members
        ],
        "meta": _meta("Group", group, location),
    }
    if group.external_id:
        body["externalId"] = group.external_id
    return body


def list_response(
    resources: list[dict], *, total: int, start_index: int, items_per_page: int
) -> dict:
    return {
        "schemas": [LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": items_per_page,
        "Resources": resources,
    }
