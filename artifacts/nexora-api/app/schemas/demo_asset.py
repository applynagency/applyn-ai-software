"""Sprint 51C - Screenshot & Demo Asset Manager schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AssetCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: str
    url: str = Field(..., min_length=1)
    asset_type: str = "SCREENSHOT"
    description: str | None = None
    module: str | None = None
    thumbnail_url: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None
    tags: list[str] = []
    order_index: int = 0


class AssetView(BaseModel):
    id: str
    organization_id: str
    title: str
    description: str | None = None
    category: str
    asset_type: str
    module: str | None = None
    url: str
    thumbnail_url: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None
    tags: list[str] = []
    order_index: int = 0
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GalleryItem(BaseModel):
    id: str
    title: str
    asset_type: str
    url: str
    thumbnail_url: str | None = None
    module: str | None = None
    tags: list[str] = []


class GallerySection(BaseModel):
    category: str
    count: int
    assets: list[GalleryItem] = []


class GalleryResponse(BaseModel):
    sections: list[GallerySection] = []
    total_assets: int = 0
