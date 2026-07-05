"""Sprint 51C - Screenshot & Demo Asset Manager engine.

Org-scoped CRUD over demo assets (screenshots, images, demo videos) plus a
gallery view grouped by category. Assets are referenced by URL (object storage /
CDN). Everything is tenant-isolated and audited; no secrets stored. Strictly
additive.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.models.demo_asset import DemoAsset, DemoAssetCategory, DemoAssetType
from app.repositories.audit import AuditLogRepository
from app.repositories.demo_asset import DemoAssetRepository
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES = {c.value for c in DemoAssetCategory}
_VALID_TYPES = {t.value for t in DemoAssetType}


class DemoAssetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DemoAssetRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ----------------------------------------------------------- permissions
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    @staticmethod
    def _validate_category(category: str | None) -> str:
        if not category:
            raise NexoraException("A category is required.", status_code=400)
        c = str(category).upper()
        if c not in _VALID_CATEGORIES:
            raise NexoraException(
                f"Invalid category. Use one of: {', '.join(sorted(_VALID_CATEGORIES))}.",
                status_code=400,
            )
        return c

    @staticmethod
    def _validate_type(asset_type: str | None) -> str:
        if not asset_type:
            return DemoAssetType.SCREENSHOT.value
        t = str(asset_type).upper()
        if t not in _VALID_TYPES:
            raise NexoraException(
                f"Invalid asset_type. Use one of: {', '.join(sorted(_VALID_TYPES))}.",
                status_code=400,
            )
        return t

    # --------------------------------------------------------------- assets
    async def create_asset(self, user, org_context, payload) -> DemoAsset:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        category = self._validate_category(payload.category)
        asset_type = self._validate_type(payload.asset_type)
        if not (payload.url or "").strip():
            raise NexoraException("An asset url is required.", status_code=400)

        asset = await self.repo.create(
            organization_id=organization_id,
            title=payload.title,
            description=payload.description,
            category=category,
            asset_type=asset_type,
            module=payload.module,
            url=payload.url,
            thumbnail_url=payload.thumbnail_url,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
            width=payload.width,
            height=payload.height,
            duration_seconds=payload.duration_seconds,
            tags=list(payload.tags or []),
            order_index=payload.order_index or 0,
            created_by=user.id,
        )
        await self.audit_repo.log(
            action="demo_asset_created",
            resource_type="demo_asset",
            resource_id=asset.id,
            user_id=user.id,
            details={"organization_id": organization_id, "category": category, "type": asset_type},
        )
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def list_assets(
        self, user, org_context, *, category=None, asset_type=None, module=None, tag=None, search=None
    ) -> list[DemoAsset]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        cat = self._validate_category(category) if category else None
        atype = self._validate_type(asset_type) if asset_type else None
        return await self.repo.list_for_org(
            organization_id, category=cat, asset_type=atype, module=module, tag=tag, search=search
        )

    async def get_asset(self, user, org_context, asset_id: str) -> DemoAsset:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        asset = await self.repo.get_for_org(asset_id, organization_id)
        if asset is None:
            raise NexoraException("Demo asset not found.", status_code=404)
        return asset

    async def delete_asset(self, user, org_context, asset_id: str) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        asset = await self.repo.get_for_org(asset_id, organization_id)
        if asset is None:
            raise NexoraException("Demo asset not found.", status_code=404)
        await self.repo.hard_delete(asset)
        await self.audit_repo.log(
            action="demo_asset_deleted",
            resource_type="demo_asset",
            resource_id=asset_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # --------------------------------------------------------------- gallery
    async def gallery(self, user, org_context, *, category=None, search=None) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        cat = self._validate_category(category) if category else None
        assets = await self.repo.list_for_org(organization_id, category=cat, search=search)

        sections: dict[str, list] = {}
        for a in assets:
            sections.setdefault(a.category, []).append(
                {
                    "id": a.id,
                    "title": a.title,
                    "asset_type": a.asset_type,
                    "url": a.url,
                    "thumbnail_url": a.thumbnail_url,
                    "module": a.module,
                    "tags": list(a.tags or []),
                }
            )

        # Keep a stable, spec-defined category order.
        ordered = [c.value for c in DemoAssetCategory]
        out_sections = []
        for key in ordered:
            if key in sections:
                out_sections.append(
                    {"category": key, "count": len(sections[key]), "assets": sections[key]}
                )
        return {"sections": out_sections, "total_assets": len(assets)}
