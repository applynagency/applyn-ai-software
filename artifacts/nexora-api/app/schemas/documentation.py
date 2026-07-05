"""Sprint 51A - Product Documentation Center schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Screenshot(BaseModel):
    url: str
    caption: str | None = None


class CodeSnippet(BaseModel):
    language: str = "text"
    code: str
    caption: str | None = None


class Video(BaseModel):
    url: str
    title: str | None = None
    provider: str | None = None  # youtube | vimeo | loom | direct


class ArticleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    # Either an existing category id or a default category key (e.g. "monitoring").
    category_id: str | None = None
    category_key: str | None = None
    slug: str | None = Field(default=None, max_length=200)
    summary: str | None = None
    content: str = ""
    status: str = "PUBLISHED"
    tags: list[str] = []
    screenshots: list[Screenshot] = []
    code_snippets: list[CodeSnippet] = []
    videos: list[Video] = []
    order_index: int = 0


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: str | None = None
    category_key: str | None = None
    slug: str | None = Field(default=None, max_length=200)
    summary: str | None = None
    content: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    screenshots: list[Screenshot] | None = None
    code_snippets: list[CodeSnippet] | None = None
    videos: list[Video] | None = None
    order_index: int | None = None


class RevisionView(BaseModel):
    version: int
    title: str
    updated_at: str | None = None
    updated_by: str | None = None


class ArticleSummary(BaseModel):
    id: str
    category_id: str
    slug: str
    title: str
    summary: str | None = None
    status: str
    version: int
    tags: list[str] = []
    view_count: int = 0
    order_index: int = 0
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArticleDetail(ArticleSummary):
    organization_id: str
    content: str = ""
    content_html: str | None = None
    screenshots: list[Screenshot] = []
    code_snippets: list[CodeSnippet] = []
    videos: list[Video] = []
    revisions: list[RevisionView] = []
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime


class ArticleListResponse(BaseModel):
    items: list[ArticleSummary] = []
    total: int = 0


class CategoryView(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    icon: str | None = None
    order_index: int = 0
    parent_id: str | None = None

    model_config = {"from_attributes": True}


class NavArticle(BaseModel):
    id: str
    slug: str
    title: str
    status: str
    view_count: int = 0
    order_index: int = 0
    updated_at: datetime


class NavCategory(BaseModel):
    id: str
    key: str
    name: str
    icon: str | None = None
    order_index: int = 0
    article_count: int = 0
    articles: list[NavArticle] = []
    children: list[NavCategory] = []


class NavigationResponse(BaseModel):
    categories: list[NavCategory] = []
    total_articles: int = 0
