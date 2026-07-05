"""Sprint 51A - Product Documentation Center engine.

Org-scoped CRUD over documentation categories and articles with:

* Default category seeding (idempotent, per organization).
* Inline article versioning (prior snapshots kept in ``revisions``).
* Search across title / summary / content / slug.
* Markdown content with first-class screenshots, code snippets and videos.
* A navigation tree (categories -> child categories -> articles).
* View tracking and last-updated timestamps.
* Export to Markdown, HTML and PDF.

Everything is tenant-isolated and audited. Nothing here executes infrastructure
actions or stores secrets. Strictly additive.
"""

from __future__ import annotations

import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.database.base import utcnow
from app.models.documentation import DocArticleStatus, DocumentationArticle, DocumentationCategory
from app.repositories.audit import AuditLogRepository
from app.repositories.documentation import (
    DocumentationArticleRepository,
    DocumentationCategoryRepository,
)
from app.services.document_export import render_html, render_pdf
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

# Ordered default documentation structure (Sprint 51A spec).
DEFAULT_CATEGORIES: list[tuple[str, str, str, str]] = [
    # (key, name, icon, description)
    ("getting-started", "Getting Started", "rocket", "Introduction and first steps with the platform."),
    ("onboarding", "Onboarding", "compass", "Guided setup and account onboarding."),
    ("infrastructure-discovery", "Infrastructure Discovery", "radar", "Automatic discovery of your environment."),
    ("monitoring", "Monitoring", "activity", "Continuous monitoring and alerting."),
    ("incidents", "Incidents", "alert", "Incident detection, triage and response."),
    ("ai-teams", "AI Teams", "users", "Custom AI teams and agents."),
    ("workflows", "Workflows", "workflow", "Automation workflows."),
    ("knowledge-base", "Knowledge Base", "book", "Reusable knowledge and articles."),
    ("memory", "Memory", "brain", "Long-term platform memory."),
    ("war-room", "War Room", "shield", "AI incident war room collaboration."),
    ("slo", "SLO", "target", "Service level objectives."),
    ("service-health", "Service Health", "heart", "Service health intelligence."),
    ("deployment-safety", "Deployment Safety", "lock", "Safe deployment and canary intelligence."),
    ("capacity-planning", "Capacity Planning", "gauge", "Capacity planning and forecasting."),
    ("cost-optimization", "Cost Optimization", "coins", "Cost optimization intelligence."),
    ("reports", "Reports", "chart", "Executive and reliability reporting."),
    ("ai-copilot", "AI Copilot", "sparkles", "AI reliability and SRE copilots."),
    ("administration", "Administration", "settings", "Org, users and platform administration."),
    ("api-reference", "API Reference", "code", "REST API reference."),
    ("troubleshooting", "Troubleshooting", "wrench", "Common problems and fixes."),
]

_MAX_REVISIONS = 50


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:200] or "untitled"


class DocumentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.category_repo = DocumentationCategoryRepository(session)
        self.article_repo = DocumentationArticleRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ----------------------------------------------------------- permissions
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    # ------------------------------------------------------------- seeding
    async def ensure_categories(self, organization_id: str) -> list[DocumentationCategory]:
        existing = await self.category_repo.list_for_org(organization_id)
        if existing:
            return existing
        created: list[DocumentationCategory] = []
        for idx, (key, name, icon, desc) in enumerate(DEFAULT_CATEGORIES):
            cat = await self.category_repo.create(
                organization_id=organization_id,
                key=key,
                name=name,
                icon=icon,
                description=desc,
                order_index=idx,
                is_system=True,
            )
            created.append(cat)
        return created

    # ------------------------------------------------------------- categories
    async def list_categories(self, user, org_context) -> list[DocumentationCategory]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self.ensure_categories(organization_id)
        await self.session.commit()
        return await self.category_repo.list_for_org(organization_id)

    async def _resolve_category(
        self, organization_id: str, category_id: str | None, category_key: str | None
    ) -> DocumentationCategory:
        await self.ensure_categories(organization_id)
        if category_id:
            cat = await self.category_repo.get_for_org(category_id, organization_id)
            if cat is None:
                raise NexoraException("Documentation category not found.", status_code=404)
            return cat
        if category_key:
            cat = await self.category_repo.get_by_key(category_key, organization_id)
            if cat is None:
                raise NexoraException("Documentation category not found.", status_code=404)
            return cat
        raise NexoraException("A category_id or category_key is required.", status_code=400)

    async def _unique_slug(self, base: str, organization_id: str, exclude_id: str | None = None) -> str:
        slug = _slugify(base)
        candidate = slug
        n = 2
        while await self.article_repo.slug_exists(candidate, organization_id, exclude_id=exclude_id):
            candidate = f"{slug}-{n}"
            n += 1
        return candidate

    # ------------------------------------------------------------- articles
    async def create_article(self, user, org_context, payload) -> DocumentationArticle:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        cat = await self._resolve_category(organization_id, payload.category_id, payload.category_key)
        slug = await self._unique_slug(payload.slug or payload.title, organization_id)
        status = self._validate_status(payload.status)

        article = await self.article_repo.create(
            organization_id=organization_id,
            category_id=cat.id,
            slug=slug,
            title=payload.title,
            summary=payload.summary,
            content=payload.content or "",
            status=status,
            version=1,
            tags=list(payload.tags or []),
            screenshots=[s.model_dump() for s in (payload.screenshots or [])],
            code_snippets=[c.model_dump() for c in (payload.code_snippets or [])],
            videos=[v.model_dump() for v in (payload.videos or [])],
            revisions=[],
            view_count=0,
            order_index=payload.order_index or 0,
            created_by=user.id,
            updated_by=user.id,
        )
        await self.audit_repo.log(
            action="documentation_article_created",
            resource_type="documentation_article",
            resource_id=article.id,
            user_id=user.id,
            details={"organization_id": organization_id, "category": cat.key, "slug": slug},
        )
        await self.session.commit()
        return article

    async def list_articles(
        self, user, org_context, *, category_id=None, category_key=None, status=None, search=None,
        offset=0, limit=50,
    ) -> tuple[list[DocumentationArticle], int]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        if category_key and not category_id:
            cat = await self.category_repo.get_by_key(category_key, organization_id)
            category_id = cat.id if cat else "__none__"
        return await self.article_repo.list_for_org(
            organization_id,
            category_id=category_id,
            status=self._validate_status(status) if status else None,
            search=search,
            offset=offset,
            limit=min(max(limit, 1), 200),
        )

    async def get_article(self, user, org_context, article_id: str, *, track_view: bool = True) -> DocumentationArticle:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        article = await self.article_repo.get_for_org(article_id, organization_id)
        if article is None:
            raise NexoraException("Documentation article not found.", status_code=404)
        if track_view:
            article.view_count = (article.view_count or 0) + 1
            self.session.add(article)
            await self.audit_repo.log(
                action="documentation_article_viewed",
                resource_type="documentation_article",
                resource_id=article.id,
                user_id=user.id,
                details={"organization_id": organization_id, "views": article.view_count},
            )
            await self.session.commit()
            await self.session.refresh(article)
        return article

    async def update_article(self, user, org_context, article_id: str, payload) -> DocumentationArticle:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        article = await self.article_repo.get_for_org(article_id, organization_id)
        if article is None:
            raise NexoraException("Documentation article not found.", status_code=404)

        data = payload.model_dump(exclude_unset=True)

        # Versioning: snapshot the current state if a content-bearing field changes.
        content_fields = {"title", "summary", "content"}
        changes_content = any(
            f in data and data[f] is not None and data[f] != getattr(article, f) for f in content_fields
        )
        if changes_content:
            revisions = list(article.revisions or [])
            revisions.append(
                {
                    "version": article.version,
                    "title": article.title,
                    "summary": article.summary,
                    "content": article.content,
                    "updated_at": article.updated_at.isoformat() if article.updated_at else None,
                    "updated_by": article.updated_by,
                }
            )
            article.revisions = revisions[-_MAX_REVISIONS:]
            article.version = (article.version or 1) + 1

        if "category_id" in data or "category_key" in data:
            cat = await self._resolve_category(
                organization_id, data.get("category_id"), data.get("category_key")
            )
            article.category_id = cat.id
        if "slug" in data and data["slug"]:
            article.slug = await self._unique_slug(data["slug"], organization_id, exclude_id=article.id)
        if "title" in data and data["title"] is not None:
            article.title = data["title"]
        if "summary" in data:
            article.summary = data["summary"]
        if "content" in data and data["content"] is not None:
            article.content = data["content"]
        if "status" in data and data["status"] is not None:
            article.status = self._validate_status(data["status"])
        if "tags" in data and data["tags"] is not None:
            article.tags = list(data["tags"])
        if "screenshots" in data and data["screenshots"] is not None:
            article.screenshots = [s if isinstance(s, dict) else s.model_dump() for s in data["screenshots"]]
        if "code_snippets" in data and data["code_snippets"] is not None:
            article.code_snippets = [c if isinstance(c, dict) else c.model_dump() for c in data["code_snippets"]]
        if "videos" in data and data["videos"] is not None:
            article.videos = [v if isinstance(v, dict) else v.model_dump() for v in data["videos"]]
        if "order_index" in data and data["order_index"] is not None:
            article.order_index = data["order_index"]

        article.updated_by = user.id
        article.updated_at = utcnow()
        self.session.add(article)

        await self.audit_repo.log(
            action="documentation_article_updated",
            resource_type="documentation_article",
            resource_id=article.id,
            user_id=user.id,
            details={"organization_id": organization_id, "version": article.version},
        )
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def delete_article(self, user, org_context, article_id: str) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        article = await self.article_repo.get_for_org(article_id, organization_id)
        if article is None:
            raise NexoraException("Documentation article not found.", status_code=404)
        await self.article_repo.hard_delete(article)
        await self.audit_repo.log(
            action="documentation_article_deleted",
            resource_type="documentation_article",
            resource_id=article_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # ------------------------------------------------------------- navigation
    async def navigation(self, user, org_context) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self.ensure_categories(organization_id)
        await self.session.commit()

        categories = await self.category_repo.list_for_org(organization_id)
        articles = await self.article_repo.list_by_category(organization_id)

        by_cat: dict[str, list] = {}
        for a in articles:
            by_cat.setdefault(a.category_id, []).append(
                {
                    "id": a.id,
                    "slug": a.slug,
                    "title": a.title,
                    "status": a.status,
                    "view_count": a.view_count or 0,
                    "order_index": a.order_index or 0,
                    "updated_at": a.updated_at,
                }
            )

        # Build tree honoring parent_id (defaults to a flat, ordered list).
        children_of: dict[str | None, list[DocumentationCategory]] = {}
        for c in categories:
            children_of.setdefault(c.parent_id, []).append(c)

        def build(cat: DocumentationCategory) -> dict:
            kids = [build(ch) for ch in children_of.get(cat.id, [])]
            arts = by_cat.get(cat.id, [])
            return {
                "id": cat.id,
                "key": cat.key,
                "name": cat.name,
                "icon": cat.icon,
                "order_index": cat.order_index or 0,
                "article_count": len(arts),
                "articles": arts,
                "children": kids,
            }

        roots = [build(c) for c in children_of.get(None, [])]
        return {"categories": roots, "total_articles": len(articles)}

    # ----------------------------------------------------------------- export
    async def export_article(
        self, user, org_context, article_id: str, fmt: str = "markdown"
    ) -> tuple[bytes, str, str]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        article = await self.article_repo.get_for_org(article_id, organization_id)
        if article is None:
            raise NexoraException("Documentation article not found.", status_code=404)

        fmt = (fmt or "markdown").lower()
        markdown = self.compose_markdown(article)
        base = article.slug or "article"

        if fmt == "markdown" or fmt == "md":
            content = markdown.encode("utf-8")
            media_type, filename = "text/markdown", f"{base}.md"
        elif fmt == "html":
            content = render_html(article.title, markdown).encode("utf-8")
            media_type, filename = "text/html", f"{base}.html"
        elif fmt == "pdf":
            content = render_pdf(markdown)
            media_type, filename = "application/pdf", f"{base}.pdf"
        else:
            raise NexoraException("Unsupported export format. Use markdown, html or pdf.", status_code=400)

        await self.audit_repo.log(
            action="documentation_article_exported",
            resource_type="documentation_article",
            resource_id=article.id,
            user_id=user.id,
            details={"organization_id": organization_id, "format": fmt},
        )
        await self.session.commit()
        return content, media_type, filename

    @staticmethod
    def compose_markdown(article: DocumentationArticle) -> str:
        """Assemble a complete Markdown document incorporating rich media."""
        parts: list[str] = [f"# {article.title}", ""]
        if article.summary:
            parts += [f"_{article.summary}_", ""]
        if article.content:
            parts += [article.content, ""]

        for snip in article.code_snippets or []:
            cap = snip.get("caption")
            lang = snip.get("language") or ""
            if cap:
                parts.append(f"**{cap}**")
            parts.append(f"```{lang}")
            parts.append(snip.get("code") or "")
            parts.append("```")
            parts.append("")

        if article.screenshots:
            parts.append("## Screenshots")
            for shot in article.screenshots:
                cap = shot.get("caption") or "screenshot"
                parts.append(f"![{cap}]({shot.get('url')})")
            parts.append("")

        if article.videos:
            parts.append("## Videos")
            for vid in article.videos:
                title = vid.get("title") or vid.get("url")
                parts.append(f"- [{title}]({vid.get('url')})")
            parts.append("")

        return "\n".join(parts).strip() + "\n"

    @staticmethod
    def content_html(article: DocumentationArticle) -> str:
        return render_html(article.title, DocumentationService.compose_markdown(article))

    @staticmethod
    def _validate_status(status: str | None) -> str:
        if status is None:
            return DocArticleStatus.PUBLISHED.value
        s = str(status).upper()
        valid = {e.value for e in DocArticleStatus}
        if s not in valid:
            raise NexoraException(
                f"Invalid status. Use one of: {', '.join(sorted(valid))}.", status_code=400
            )
        return s
