"""Sprint 51E - Customer Documentation Portal generator schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GenerateResponse(BaseModel):
    articles_generated: int
    created: int
    updated: int
    routes_scanned: int
    navigation_paths: int
    modules_scanned: int
    guides: list[str] = []
    quality_score: int = 0
    quality: dict[str, Any] = {}


class PortalArticle(BaseModel):
    id: str
    slug: str
    title: str


class PortalGuide(BaseModel):
    key: str
    title: str
    article_count: int = 0
    articles: list[PortalArticle] = []


class PortalResponse(BaseModel):
    title: str
    guides: list[PortalGuide] = []
    navigation: list[Any] = []
    total_articles: int = 0
    generated_articles: int = 0
    modules: int = 0
