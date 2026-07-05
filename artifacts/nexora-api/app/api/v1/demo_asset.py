"""Sprint 51C - Screenshot & Demo Asset Manager API.

* POST   /v1/demo-assets         - register a screenshot / image / demo video
* GET    /v1/demo-assets         - list/search assets (filters: category/type/module/tag)
* GET    /v1/demo-assets/gallery - demo gallery grouped by category (additive)
* GET    /v1/demo-assets/{id}    - fetch an asset
* DELETE /v1/demo-assets/{id}    - delete an asset

Org-scoped, audited, read/write gated by role. Strictly additive.
"""

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.demo_asset import AssetCreate, AssetView, GalleryResponse
from app.services.demo_asset import DemoAssetService

router = APIRouter(prefix="/demo-assets", tags=["Demo Assets"])


@router.post("", response_model=AssetView, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    asset = await DemoAssetService(session).create_asset(current_user, org_context, payload)
    return AssetView.model_validate(asset)


@router.get("", response_model=list[AssetView])
async def list_assets(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    category: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    module: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    assets = await DemoAssetService(session).list_assets(
        current_user, org_context,
        category=category, asset_type=asset_type, module=module, tag=tag, search=search,
    )
    return [AssetView.model_validate(a) for a in assets]


@router.get("/gallery", response_model=GalleryResponse)
async def get_gallery(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    return await DemoAssetService(session).gallery(
        current_user, org_context, category=category, search=search
    )


@router.get("/{asset_id}", response_model=AssetView)
async def get_asset(
    asset_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    asset = await DemoAssetService(session).get_asset(current_user, org_context, asset_id)
    return AssetView.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    await DemoAssetService(session).delete_asset(current_user, org_context, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
