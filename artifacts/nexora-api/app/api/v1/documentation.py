"""Sprint 51A - Product Documentation Center API.

* POST   /v1/docs/articles            - create an article
* GET    /v1/docs/articles            - list/search articles (filters + pagination)
* GET    /v1/docs/articles/{id}       - fetch an article (tracks a view)
* PUT    /v1/docs/articles/{id}       - update an article (versioned)
* DELETE /v1/docs/articles/{id}       - delete an article
* GET    /v1/docs/articles/{id}/export- export an article (markdown | html | pdf)
* GET    /v1/docs/navigation          - documentation navigation tree
* GET    /v1/docs/categories          - documentation categories

Org-scoped, audited, read/write gated by role. Strictly additive.
"""

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.documentation import DocumentationArticle
from app.schemas.documentation import (
    ArticleCreate,
    ArticleDetail,
    ArticleListResponse,
    ArticleSummary,
    ArticleUpdate,
    CategoryView,
    NavigationResponse,
)
from app.services.documentation import DocumentationService

router = APIRouter(prefix="/docs", tags=["Documentation"])


def _summary(a: DocumentationArticle) -> ArticleSummary:
    return ArticleSummary(
        id=a.id,
        category_id=a.category_id,
        slug=a.slug,
        title=a.title,
        summary=a.summary,
        status=a.status,
        version=a.version,
        tags=list(a.tags or []),
        view_count=a.view_count or 0,
        order_index=a.order_index or 0,
        updated_at=a.updated_at,
    )


def _detail(a: DocumentationArticle) -> ArticleDetail:
    revisions = [
        {
            "version": r.get("version"),
            "title": r.get("title") or "",
            "updated_at": r.get("updated_at"),
            "updated_by": r.get("updated_by"),
        }
        for r in (a.revisions or [])
    ]
    return ArticleDetail(
        id=a.id,
        organization_id=a.organization_id,
        category_id=a.category_id,
        slug=a.slug,
        title=a.title,
        summary=a.summary,
        status=a.status,
        version=a.version,
        tags=list(a.tags or []),
        view_count=a.view_count or 0,
        order_index=a.order_index or 0,
        content=a.content or "",
        content_html=DocumentationService.content_html(a),
        screenshots=list(a.screenshots or []),
        code_snippets=list(a.code_snippets or []),
        videos=list(a.videos or []),
        revisions=revisions,
        created_by=a.created_by,
        updated_by=a.updated_by,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.post("/articles", response_model=ArticleDetail, status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: ArticleCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    article = await DocumentationService(session).create_article(current_user, org_context, payload)
    return _detail(article)


@router.get("/articles", response_model=ArticleListResponse)
async def list_articles(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    category_id: str | None = Query(default=None),
    category_key: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    items, total = await DocumentationService(session).list_articles(
        current_user,
        org_context,
        category_id=category_id,
        category_key=category_key,
        status=status_filter,
        search=search,
        offset=offset,
        limit=limit,
    )
    return ArticleListResponse(items=[_summary(a) for a in items], total=total)


@router.get("/navigation", response_model=NavigationResponse)
async def get_navigation(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DocumentationService(session).navigation(current_user, org_context)


@router.get("/categories", response_model=list[CategoryView])
async def list_categories(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    cats = await DocumentationService(session).list_categories(current_user, org_context)
    return [CategoryView.model_validate(c) for c in cats]


@router.get("/articles/{article_id}", response_model=ArticleDetail)
async def get_article(
    article_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    track_view: bool = Query(default=True),
):
    article = await DocumentationService(session).get_article(
        current_user, org_context, article_id, track_view=track_view
    )
    return _detail(article)


@router.get("/articles/{article_id}/export")
async def export_article(
    article_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="markdown"),
):
    content, media_type, filename = await DocumentationService(session).export_article(
        current_user, org_context, article_id, fmt=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/articles/{article_id}", response_model=ArticleDetail)
async def update_article(
    article_id: str,
    payload: ArticleUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    article = await DocumentationService(session).update_article(
        current_user, org_context, article_id, payload
    )
    return _detail(article)


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    await DocumentationService(session).delete_article(current_user, org_context, article_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
