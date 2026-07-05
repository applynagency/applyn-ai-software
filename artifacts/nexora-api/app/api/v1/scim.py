"""SCIM 2.0 API (RFC 7644).

Resource endpoints (per-organization bearer token):
* ``/scim/v2/Users``   GET(list) POST ; ``/Users/{id}`` GET PUT PATCH DELETE
* ``/scim/v2/Groups``  GET(list) POST ; ``/Groups/{id}`` GET PUT PATCH DELETE
* ``/scim/v2/Bulk``    POST
* ``/scim/v2/ServiceProviderConfig`` ``/ResourceTypes`` ``/Schemas`` (discovery)

Admin endpoints (superuser, normal app auth):
* ``/scim/v2/admin/tokens`` POST GET ; ``/admin/tokens/{id}`` DELETE
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import CurrentSuperuser, DBSession
from app.schemas.scim import (
    ScimTokenCreate,
    ScimTokenCreatedResponse,
    ScimTokenListResponse,
    ScimTokenResponse,
)
from app.services.scim import auth as scim_auth
from app.services.scim.auth import ScimContext
from app.services.scim.errors import ScimError
from app.services.scim.serializers import (
    list_response,
    scim_group_to_dict,
    scim_user_to_dict,
)
from app.services.scim.service import ScimService

router = APIRouter(prefix="/scim/v2", tags=["SCIM"])

SCIM_MEDIA_TYPE = "application/scim+json"


async def get_scim_context(request: Request, session: DBSession) -> ScimContext:
    return await scim_auth.authenticate(request, session)


ScimCtx = Annotated[ScimContext, Depends(get_scim_context)]


def _json(body: dict, *, status_code: int = 200, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        content=body, status_code=status_code, media_type=SCIM_MEDIA_TYPE, headers=headers
    )


async def _read_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScimError(400, "Request body is not valid JSON", "invalidSyntax") from exc
    if not isinstance(data, dict):
        raise ScimError(400, "Request body must be a JSON object", "invalidSyntax")
    return data


def _user_location(request: Request, scim_id: str) -> str:
    return str(request.url_for("scim_get_user", scim_id=scim_id))


def _group_location(request: Request, scim_id: str) -> str:
    return str(request.url_for("scim_get_group", scim_id=scim_id))


async def _serialize_group(service: ScimService, request: Request, group) -> dict:
    members = [
        (uid, name, _user_location(request, uid))
        for uid, name in await service.members_of(group)
    ]
    return scim_group_to_dict(group, members, location=_group_location(request, group.id))


def _pagination(request: Request) -> tuple[int, int]:
    params = request.query_params
    try:
        start_index = max(int(params.get("startIndex", 1)), 1)
    except ValueError:
        start_index = 1
    try:
        count = int(params.get("count", 100))
    except ValueError:
        count = 100
    count = max(0, min(count, 500))
    return start_index, count


# --- Users ------------------------------------------------------------------


@router.get("/Users")
async def list_users(ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    start_index, count = _pagination(request)
    items, total = await service.list_users(
        filter_str=request.query_params.get("filter"),
        start_index=start_index,
        count=count,
    )
    resources = [scim_user_to_dict(u, location=_user_location(request, u.id)) for u in items]
    return _json(list_response(resources, total=total, start_index=start_index, items_per_page=len(resources)))


@router.post("/Users")
async def create_user(ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    scim_user = await service.create_user(await _read_body(request))
    location = _user_location(request, scim_user.id)
    return _json(
        scim_user_to_dict(scim_user, location=location),
        status_code=status.HTTP_201_CREATED,
        headers={"Location": location},
    )


@router.get("/Users/{scim_id}", name="scim_get_user")
async def get_user(scim_id: str, ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    scim_user = await service.get_user(scim_id)
    return _json(scim_user_to_dict(scim_user, location=_user_location(request, scim_user.id)))


@router.put("/Users/{scim_id}")
async def replace_user(scim_id: str, ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    scim_user = await service.replace_user(scim_id, await _read_body(request))
    return _json(scim_user_to_dict(scim_user, location=_user_location(request, scim_user.id)))


@router.patch("/Users/{scim_id}")
async def patch_user(scim_id: str, ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    body = await _read_body(request)
    operations = body.get("Operations") or body.get("operations") or []
    scim_user = await service.patch_user(scim_id, operations)
    return _json(scim_user_to_dict(scim_user, location=_user_location(request, scim_user.id)))


@router.delete("/Users/{scim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(scim_id: str, ctx: ScimCtx):
    service = ScimService(ctx)
    await service.delete_user(scim_id)
    return JSONResponse(content=None, status_code=status.HTTP_204_NO_CONTENT)


# --- Groups -----------------------------------------------------------------


@router.get("/Groups")
async def list_groups(ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    start_index, count = _pagination(request)
    items, total = await service.list_groups(
        filter_str=request.query_params.get("filter"),
        start_index=start_index,
        count=count,
    )
    resources = [await _serialize_group(service, request, g) for g in items]
    return _json(list_response(resources, total=total, start_index=start_index, items_per_page=len(resources)))


@router.post("/Groups")
async def create_group(ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    group = await service.create_group(await _read_body(request))
    location = _group_location(request, group.id)
    return _json(
        await _serialize_group(service, request, group),
        status_code=status.HTTP_201_CREATED,
        headers={"Location": location},
    )


@router.get("/Groups/{scim_id}", name="scim_get_group")
async def get_group(scim_id: str, ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    group = await service.get_group(scim_id)
    return _json(await _serialize_group(service, request, group))


@router.put("/Groups/{scim_id}")
async def replace_group(scim_id: str, ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    group = await service.replace_group(scim_id, await _read_body(request))
    return _json(await _serialize_group(service, request, group))


@router.patch("/Groups/{scim_id}")
async def patch_group(scim_id: str, ctx: ScimCtx, request: Request):
    service = ScimService(ctx)
    body = await _read_body(request)
    operations = body.get("Operations") or body.get("operations") or []
    group = await service.patch_group(scim_id, operations)
    return _json(await _serialize_group(service, request, group))


@router.delete("/Groups/{scim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(scim_id: str, ctx: ScimCtx):
    service = ScimService(ctx)
    await service.delete_group(scim_id)
    return JSONResponse(content=None, status_code=status.HTTP_204_NO_CONTENT)


# --- Bulk -------------------------------------------------------------------


@router.post("/Bulk")
async def bulk(ctx: ScimCtx, request: Request):
    from app.core.config import settings
    from app.services.scim.serializers import BULK_RESPONSE_SCHEMA

    service = ScimService(ctx)
    body = await _read_body(request)
    operations = body.get("Operations") or []
    if len(operations) > settings.SCIM_BULK_MAX_OPERATIONS:
        raise ScimError(413, "Bulk operation count exceeds the configured maximum", "tooLarge")
    fail_on_errors = body.get("failOnErrors")

    raw_results = await service.process_bulk(operations, fail_on_errors=fail_on_errors)
    results = []
    for r in raw_results:
        entry = {"method": r["method"], "status": r["status"]}
        if r.get("bulkId"):
            entry["bulkId"] = r["bulkId"]
        rtype = r.pop("_resource_type", None)
        rid = r.pop("_resource_id", None)
        if rtype and rid:
            entry["location"] = (
                _user_location(request, rid)
                if rtype == "User"
                else _group_location(request, rid)
            )
        if r.get("response"):
            entry["response"] = r["response"]
        results.append(entry)
    return _json({"schemas": [BULK_RESPONSE_SCHEMA], "Operations": results})


# --- Discovery --------------------------------------------------------------


@router.get("/ServiceProviderConfig")
async def service_provider_config(ctx: ScimCtx, request: Request):
    return _json(
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "documentationUri": "",
            "patch": {"supported": True},
            "bulk": {"supported": True, "maxOperations": 1000, "maxPayloadSize": 1048576},
            "filter": {"supported": True, "maxResults": 200},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": False},
            "authenticationSchemes": [
                {
                    "type": "oauthbearertoken",
                    "name": "OAuth Bearer Token",
                    "description": "Authentication via the SCIM bearer token.",
                    "primary": True,
                }
            ],
            "meta": {"resourceType": "ServiceProviderConfig"},
        }
    )


@router.get("/ResourceTypes")
async def resource_types(ctx: ScimCtx, request: Request):
    base = str(request.url_for("list_users")).rsplit("/Users", 1)[0]
    types = [
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
            "id": "User",
            "name": "User",
            "endpoint": "/Users",
            "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
            "meta": {"resourceType": "ResourceType", "location": f"{base}/ResourceTypes/User"},
        },
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
            "id": "Group",
            "name": "Group",
            "endpoint": "/Groups",
            "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
            "meta": {"resourceType": "ResourceType", "location": f"{base}/ResourceTypes/Group"},
        },
    ]
    return _json(list_response(types, total=len(types), start_index=1, items_per_page=len(types)))


@router.get("/Schemas")
async def schemas(ctx: ScimCtx):
    core = [
        {"id": "urn:ietf:params:scim:schemas:core:2.0:User", "name": "User"},
        {"id": "urn:ietf:params:scim:schemas:core:2.0:Group", "name": "Group"},
    ]
    return _json(list_response(core, total=len(core), start_index=1, items_per_page=len(core)))


# --- Admin: token management (superuser) ------------------------------------


@router.post(
    "/admin/tokens",
    response_model=ScimTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scim_token(
    payload: ScimTokenCreate, current_user: CurrentSuperuser, session: DBSession
):
    from app.repositories.organization import OrganizationRepository

    org = await OrganizationRepository(session).get_by_id(payload.organization_id)
    if org is None:
        raise ScimError(404, "Organization not found")
    token, plaintext = await scim_auth.create_token(
        session,
        organization_id=payload.organization_id,
        name=payload.name,
        created_by=current_user.id,
    )
    return ScimTokenCreatedResponse(
        id=token.id,
        organization_id=token.organization_id,
        name=token.name,
        token_prefix=token.token_prefix,
        active=token.active,
        token=plaintext,
    )


@router.get("/admin/tokens", response_model=ScimTokenListResponse)
async def list_scim_tokens(
    organization_id: str, current_user: CurrentSuperuser, session: DBSession
):
    tokens = await scim_auth.list_tokens(session, organization_id)
    return ScimTokenListResponse(
        tokens=[ScimTokenResponse.model_validate(t) for t in tokens], total=len(tokens)
    )


@router.delete("/admin/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_scim_token(
    token_id: str, current_user: CurrentSuperuser, session: DBSession
):
    revoked = await scim_auth.revoke_token(session, token_id)
    if not revoked:
        raise ScimError(404, "SCIM token not found")
