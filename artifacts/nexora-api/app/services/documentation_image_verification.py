"""Sprint 56F.8 — Documentation Image Rendering Verification.

The screenshot *asset* audit (56F.7) proves every canonical screenshot URL
resolves to HTTP 200, yet the documentation UI still shows broken images. The
reason is that stored help-center articles reference screenshots by **stale
static PNG paths** — e.g. ``/static/docs/screenshots/dashboard-overview.png`` —
which have no ``BASE_PATH`` prefix and point at a directory that does not exist,
so the browser ``<img>`` tag 404s.

This module performs the end-to-end rendering verification:

* opens every generated documentation article,
* extracts every rendered image source (gallery screenshots + inline content),
* compares the **stored** URL against the **canonical** screenshot URL,
* classifies the root cause (stale reference, old PNG, missing BASE_PATH,
  external placeholder, frontend rendering bug),
* and can **repair** articles in place so every image renders.

Canonical URL: ``{BASE_PATH}/v1/customer-success/screenshots/{screenshot_id}``.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.documentation import DocumentationArticleRepository
from app.services.screenshot_assets import ScreenshotAssetGenerator

CANON_PREFIX = f"{settings.BASE_PATH}/v1/customer-success/screenshots"
STALE_STATIC_PREFIX = "/static/docs/screenshots/"

# Inline image references inside markdown/HTML article bodies.
_MD_IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
_HTML_IMG = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


def screenshot_id_from_url(url: str) -> str:
    """Last path segment without query/hash/extension."""
    base = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    name = base.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def canonical_url(url: str) -> str:
    sid = screenshot_id_from_url(url)
    return f"{CANON_PREFIX}/{sid}" if sid else url


def is_canonical(url: str) -> bool:
    return url.startswith(CANON_PREFIX + "/")


def classify(url: str) -> tuple[bool, list[str], str]:
    """Return (renders_ok, flags, root_cause) for a stored image URL."""
    if is_canonical(url):
        return True, [], ""

    flags: list[str] = []
    reasons: list[str] = []

    if url.startswith(STALE_STATIC_PREFIX):
        flags.append("stale_reference")
        reasons.append("stale static docs path that is not served")
    if url.lower().split("?", 1)[0].endswith(".png"):
        flags.append("old_png")
        reasons.append("legacy .png reference (assets are rendered SVG)")
    if url.startswith(("http://", "https://")):
        flags.append("external")
        reasons.append("external placeholder URL")
    elif not url.startswith(settings.BASE_PATH):
        flags.append("wrong_base_path")
        reasons.append(f"missing BASE_PATH prefix ({settings.BASE_PATH})")

    if not screenshot_id_from_url(url):
        flags.append("frontend_rendering_error")
        reasons.append("URL has no resolvable screenshot id")

    root_cause = "; ".join(reasons) or "non-canonical screenshot URL"
    return False, flags, root_cause


class DocumentationImageVerificationEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DocumentationArticleRepository(session)
        self._assets = ScreenshotAssetGenerator()

    def _renderable(self, screenshot_id: str) -> bool:
        try:
            svg = self._assets.svg_for_id(screenshot_id)
        except Exception:
            return False
        return bool(svg) and svg.lstrip().startswith("<svg")

    @staticmethod
    def _image_urls(article: Any) -> list[str]:
        urls: list[str] = []
        for shot in (article.screenshots or []):
            if isinstance(shot, dict) and shot.get("url"):
                urls.append(str(shot["url"]))
        content = article.content or ""
        urls.extend(_MD_IMG.findall(content))
        urls.extend(_HTML_IMG.findall(content))
        return urls

    async def _articles(self, organization_id: str) -> list[Any]:
        return await self.repo.list_by_category(organization_id)

    async def verify(self, organization_id: str) -> dict[str, Any]:
        articles = await self._articles(organization_id)
        images_rendered = 0
        images_broken = 0
        stale_references = 0
        wrong_base_path = 0
        frontend_rendering_errors = 0
        total_images = 0
        broken: list[dict[str, str]] = []

        for a in articles:
            for url in self._image_urls(a):
                total_images += 1
                ok, flags, root_cause = classify(url)
                expected = canonical_url(url)
                # A canonical URL still counts as a rendering error if the
                # endpoint cannot produce an image for it.
                if ok and not self._renderable(screenshot_id_from_url(url)):
                    ok = False
                    flags = ["frontend_rendering_error"]
                    root_cause = "screenshot endpoint cannot render this id"

                if ok:
                    images_rendered += 1
                    continue

                images_broken += 1
                if "stale_reference" in flags:
                    stale_references += 1
                if "wrong_base_path" in flags:
                    wrong_base_path += 1
                if "frontend_rendering_error" in flags:
                    frontend_rendering_errors += 1
                broken.append({
                    "article_id": a.id,
                    "article_title": a.title,
                    "stored_url": url,
                    "expected_url": expected,
                    "root_cause": root_cause,
                })

        report = {
            "article_count": len(articles),
            "images_rendered": images_rendered,
            "images_broken": images_broken,
            "stale_references": stale_references,
            "wrong_base_path": wrong_base_path,
            "frontend_rendering_errors": frontend_rendering_errors,
        }
        summary = {
            "total_images": total_images,
            "all_render": images_broken == 0,
            "canonical_prefix": CANON_PREFIX,
        }
        return {"report": report, "summary": summary, "broken": broken}

    async def repair(self, organization_id: str) -> dict[str, Any]:
        """Rewrite every stored image URL to its canonical form."""
        articles = await self._articles(organization_id)
        articles_updated = 0
        images_fixed = 0

        for a in articles:
            changed = False

            shots = a.screenshots or []
            new_shots = []
            for shot in shots:
                if isinstance(shot, dict) and shot.get("url") and not is_canonical(str(shot["url"])):
                    fixed = dict(shot)
                    fixed["url"] = canonical_url(str(shot["url"]))
                    new_shots.append(fixed)
                    images_fixed += 1
                    changed = True
                else:
                    new_shots.append(shot)
            if changed:
                a.screenshots = new_shots

            content = a.content or ""
            if STALE_STATIC_PREFIX in content or ".png" in content:
                def _sub(m: re.Match) -> str:
                    return m.group(0).replace(m.group(1), canonical_url(m.group(1)))

                new_content = _MD_IMG.sub(_sub, content)
                new_content = _HTML_IMG.sub(_sub, new_content)
                if new_content != content:
                    a.content = new_content
                    changed = True

            if changed:
                articles_updated += 1

        if articles_updated:
            await self.session.commit()

        return {"articles_updated": articles_updated, "images_fixed": images_fixed}
