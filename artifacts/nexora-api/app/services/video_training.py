"""Sprint 56E.2 — Video Training Platform.

Turns the human-quality documentation into visual learning assets. For every
module it scripts three training videos:

* a 2-minute Overview (Beginner),
* a 5-minute Walkthrough (Intermediate),
* a 10-minute Deep Dive (Advanced).

Each script is a sequence of scenes, every scene carrying narration, the screen
to show, the expected action, and the exact voice-over text. Each video also
carries video / GIF / thumbnail metadata. Portal helpers expose a Video Library,
Featured Videos, and Recently Added. Deterministic, read-only, no DB.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import MODULES, get_module
from app.services.document_export import render_html, render_pdf
from app.services.human_documentation import HumanDocumentationEngine
from app.services.screenshot_assets import AREAS

# Video kinds → duration / category.
VIDEO_KINDS = [
    {"kind": "overview", "label": "2-Minute Overview", "duration": 120, "category": "Beginner"},
    {"kind": "walkthrough", "label": "5-Minute Walkthrough", "duration": 300, "category": "Intermediate"},
    {"kind": "deep-dive", "label": "10-Minute Deep Dive", "duration": 600, "category": "Advanced"},
]
CATEGORIES = ["Beginner", "Intermediate", "Advanced"]

# Modules whose overview videos are featured on the portal.
FEATURED_MODULES = {"monitoring", "incidents", "deployment-safety", "executive-reports", "discovery", "cost"}

_DEVICE = "desktop"
_SHOTS = ["overview", "detail", "workflow"]
_AREA_SLUG_BY_ROUTE = {a["route"]: a["slug"] for a in AREAS}
_BASE_DATE = date(2026, 6, 24)


def _mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _render_url(route: str, shot: str) -> str:
    r = route or "/"
    return f"/nexora-api/v1/customer-success/screenshot-render?route={r}&shot={shot}&device={_DEVICE}"


def _screenshot_id(route: str, shot: str) -> str:
    slug = _AREA_SLUG_BY_ROUTE.get(route)
    return f"{slug}-{shot}-{_DEVICE}" if slug else f"route-{(route or '/').strip('/').replace('/', '-').replace(':', '') or 'home'}-{shot}-{_DEVICE}"


class VideoTrainingEngine:
    def __init__(self) -> None:
        self.human = HumanDocumentationEngine()
        self._cache: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------- scene helpers
    def _scene(self, order: int, *, title: str, route: str, shot: str,
               voice_over: str, on_screen: str, expected_action: str,
               duration: int = 0, screenshot_id: str = "") -> dict[str, Any]:
        return {
            "order": order,
            "title": title,
            "duration_seconds": duration,
            "timecode": "",  # filled after allocation
            "narration": f"On screen: {title}. {on_screen}",
            "voice_over": voice_over,
            "on_screen_text": on_screen,
            "expected_action": expected_action,
            "screen": {
                "route": route,
                "shot": shot,
                "device": _DEVICE,
                "screenshot_id": screenshot_id or _screenshot_id(route, shot),
                "thumbnail_url": _render_url(route, shot),
            },
        }

    def _allocate(self, scenes: list[dict[str, Any]], total: int) -> None:
        n = len(scenes)
        if not n:
            return
        each = total // n
        for s in scenes:
            s["duration_seconds"] = each
        scenes[-1]["duration_seconds"] = total - each * (n - 1)
        t = 0
        for s in scenes:
            s["timecode"] = _mmss(t)
            t += s["duration_seconds"]

    # ------------------------------------------------------- script builders
    def _overview_scenes(self, g: dict[str, Any]) -> list[dict[str, Any]]:
        name, route = g["name"], g["route"]
        bp = g["business_problem"]
        a = g["answers"]
        outcomes = "; ".join(o["metric"] for o in g["business_outcomes"][:3])
        steps = g["walkthrough"]
        scenes = [
            self._scene(1, title=f"Meet {name}", route=route, shot="overview",
                        voice_over=f"Welcome. {bp['without']}",
                        on_screen=f"{name} — why it matters",
                        expected_action="Press play to begin the overview."),
            self._scene(2, title=f"What {name} is", route=route, shot="overview",
                        voice_over=f"{a['what']} In short, {bp['with_solution']}",
                        on_screen=a["what"],
                        expected_action=f"Open {name} from the navigation."),
            self._scene(3, title="Why it matters", route=route, shot="detail",
                        voice_over=f"{bp['summary']} The measurable wins: {outcomes}.",
                        on_screen=f"Outcomes: {outcomes}",
                        expected_action="Note the business outcomes shown."),
        ]
        for i, st in enumerate(steps[:2], start=4):
            scenes.append(self._scene(
                i, title=st["action"][:60], route=route, shot=_SHOTS[i % len(_SHOTS)],
                voice_over=f"{st['action']} {st['why']}",
                on_screen=st["expected_result"],
                expected_action=st["expected_result"],
                screenshot_id=str(st.get("screenshot_id", "")),
            ))
        scenes.append(self._scene(
            len(scenes) + 1, title="Get started", route=route, shot="overview",
            voice_over=f"That's {name}. Expected outcome: {a['expected_outcome']}. Try it yourself now.",
            on_screen=f"Start using {name}",
            expected_action=f"Click into {name} and follow the walkthrough video next."))
        self._allocate(scenes, 120)
        return scenes

    def _walkthrough_scenes(self, g: dict[str, Any]) -> list[dict[str, Any]]:
        name, route = g["name"], g["route"]
        steps = g["walkthrough"][:8]
        scenes = [self._scene(
            1, title=f"{name} walkthrough", route=route, shot="overview",
            voice_over=f"In this walkthrough we'll use {name} step by step. {g['answers']['how']}",
            on_screen=f"{name}: step-by-step",
            expected_action="Follow along in your own account.")]
        for i, st in enumerate(steps, start=2):
            scenes.append(self._scene(
                i, title=f"Step {st['order']}: {st['action'][:50]}", route=route,
                shot=_SHOTS[i % len(_SHOTS)],
                voice_over=f"{st['action']} {st['why']}",
                on_screen=st["action"],
                expected_action=st["expected_result"],
                screenshot_id=str(st.get("screenshot_id", "")),
            ))
        scenes.append(self._scene(
            len(scenes) + 1, title="Recap", route=route, shot="detail",
            voice_over=f"You've now used the core of {name}. Watch the deep dive for advanced usage.",
            on_screen="Walkthrough complete",
            expected_action="Continue to the deep-dive video."))
        self._allocate(scenes, 300)
        return scenes

    def _deep_dive_scenes(self, g: dict[str, Any]) -> list[dict[str, Any]]:
        name, route = g["name"], g["route"]
        steps = g["walkthrough"]
        scenes = [self._scene(
            1, title=f"{name} deep dive", route=route, shot="overview",
            voice_over=f"This deep dive covers {name} end to end, including how to read results and operate it well.",
            on_screen=f"{name}: complete deep dive",
            expected_action="Settle in — this is the full tour.")]
        for i, st in enumerate(steps, start=2):
            mistakes = "; ".join(st.get("common_mistakes", []))
            scenes.append(self._scene(
                i, title=f"Step {st['order']}: {st['action'][:50]}", route=route,
                shot=_SHOTS[i % len(_SHOTS)],
                voice_over=f"{st['action']} {st['why']} Expected: {st['expected_result']}"
                           + (f" Avoid: {mistakes}" if mistakes else ""),
                on_screen=st["action"],
                expected_action=st["expected_result"],
                screenshot_id=str(st.get("screenshot_id", "")),
            ))
        # Results interpretation scene.
        groups = g["results_interpretation"]
        if groups:
            labels = ", ".join(grp["name"] for grp in groups[:4])
            scenes.append(self._scene(
                len(scenes) + 1, title="Reading the results", route=route, shot="detail",
                voice_over=f"Here's how to interpret what {name} shows you: {labels}. "
                           f"Each score tells you what to do next.",
                on_screen="How to read scores, risk, and status",
                expected_action="Learn to interpret the indicators."))
        # Best-practices scene.
        if g["best_practices"]:
            bp = "; ".join(g["best_practices"][:3])
            scenes.append(self._scene(
                len(scenes) + 1, title="Best practices", route=route, shot="workflow",
                voice_over=f"To get the most from {name}: {bp}.",
                on_screen="Operational best practices",
                expected_action="Adopt these practices in your team."))
        scenes.append(self._scene(
            len(scenes) + 1, title="Wrap up", route=route, shot="overview",
            voice_over=f"That's the complete {name} deep dive. Expected outcome: {g['answers']['expected_outcome']}.",
            on_screen="Deep dive complete",
            expected_action="Apply what you learned in your environment."))
        self._allocate(scenes, 600)
        return scenes

    def _scenes_for(self, g: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        if kind == "overview":
            return self._overview_scenes(g)
        if kind == "walkthrough":
            return self._walkthrough_scenes(g)
        return self._deep_dive_scenes(g)

    # ------------------------------------------------------- metadata
    def _metadata(self, vid: str, route: str, duration: int) -> tuple[dict, dict, dict]:
        thumb_id = _screenshot_id(route, "overview")
        thumb_url = _render_url(route, "overview")
        video_metadata = {
            "format": "mp4", "codec": "h264", "resolution": "1920x1080",
            "aspect_ratio": "16:9", "fps": 30, "duration_seconds": duration,
            "has_captions": True, "audio": "voice-over",
            "file": f"assets/documentation/videos/{vid}.mp4",
            "poster_url": thumb_url, "status": "scripted",
        }
        gif_metadata = {
            "format": "gif", "resolution": "640x360", "fps": 12, "loop": True,
            "duration_seconds": min(10, max(6, duration // 20)),
            "file": f"assets/documentation/videos/{vid}.gif",
            "preview_url": thumb_url,
        }
        thumbnail_metadata = {
            "format": "svg", "resolution": "1280x720",
            "screenshot_id": thumb_id, "route": route,
            "file": f"assets/documentation/videos/{vid}-thumb.svg",
            "url": thumb_url, "alt": "Training video thumbnail",
        }
        return video_metadata, gif_metadata, thumbnail_metadata

    # ------------------------------------------------------- assembly
    def _build_all(self) -> dict[str, dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        videos: dict[str, dict[str, Any]] = {}
        ordered: list[str] = []
        for m in MODULES:
            g = self.human.guide(m["key"])
            for spec in VIDEO_KINDS:
                kind = spec["kind"]
                vid = f"{m['key']}-{kind}"
                scenes = self._scenes_for(g, kind)
                duration = spec["duration"]
                vmeta, gmeta, tmeta = self._metadata(vid, g["route"], duration)
                featured = kind == "overview" and m["key"] in FEATURED_MODULES
                videos[vid] = {
                    "id": vid,
                    "module": m["key"],
                    "module_name": g["name"],
                    "route": g["route"],
                    "kind": kind,
                    "label": spec["label"],
                    "title": f"{g['name']} — {spec['label']}",
                    "category": spec["category"],
                    "duration_seconds": duration,
                    "duration_label": _mmss(duration),
                    "summary": g["business_problem"]["summary"],
                    "featured": featured,
                    "scene_count": len(scenes),
                    "scenes": scenes,
                    "video_metadata": vmeta,
                    "gif_metadata": gmeta,
                    "thumbnail_metadata": tmeta,
                    "added_at": "",  # set below
                }
                ordered.append(vid)
        total = len(ordered)
        for idx, vid in enumerate(ordered):
            # Later-generated videos are "more recently added".
            videos[vid]["added_at"] = (_BASE_DATE - timedelta(days=total - 1 - idx)).isoformat()
        self._cache = videos
        return videos

    def _summary(self, v: dict[str, Any]) -> dict[str, Any]:
        return {k: v[k] for k in (
            "id", "module", "module_name", "route", "kind", "label", "title",
            "category", "duration_seconds", "duration_label", "summary",
            "featured", "scene_count", "added_at", "thumbnail_metadata",
        )}

    # ------------------------------------------------------- public API
    def library(self, *, module: str | None = None, category: str | None = None,
                kind: str | None = None) -> dict[str, Any]:
        videos = list(self._build_all().values())
        if module:
            videos = [v for v in videos if v["module"] == module]
        if category:
            videos = [v for v in videos if v["category"].lower() == category.lower()]
        if kind:
            videos = [v for v in videos if v["kind"] == kind]
        items = [self._summary(v) for v in videos]
        all_videos = list(self._build_all().values())
        facets = {
            "categories": {c: sum(1 for v in all_videos if v["category"] == c) for c in CATEGORIES},
            "kinds": {s["kind"]: sum(1 for v in all_videos if v["kind"] == s["kind"]) for s in VIDEO_KINDS},
            "modules": len({v["module"] for v in all_videos}),
        }
        return {
            "items": items,
            "total": len(items),
            "library_total": len(all_videos),
            "facets": facets,
        }

    def featured(self) -> dict[str, Any]:
        videos = [v for v in self._build_all().values() if v["featured"]]
        return {"items": [self._summary(v) for v in videos], "total": len(videos)}

    def recently_added(self, limit: int = 12) -> dict[str, Any]:
        videos = sorted(self._build_all().values(), key=lambda v: v["added_at"], reverse=True)
        items = [self._summary(v) for v in videos[:limit]]
        return {"items": items, "total": len(items)}

    def get(self, video_id: str) -> dict[str, Any]:
        v = self._build_all().get(video_id)
        if not v:
            raise NotFoundError("Training video", video_id)
        return v

    def for_module(self, module: str) -> dict[str, Any]:
        if not get_module(module):
            raise NotFoundError("Documentation module", module)
        videos = [v for v in self._build_all().values() if v["module"] == module]
        return {"items": videos, "total": len(videos)}

    # ------------------------------------------------------- export
    def _markdown(self, v: dict[str, Any]) -> str:
        L: list[str] = [f"# {v['title']}", ""]
        L.append(f"*{v['category']} · {v['duration_label']} · {v['scene_count']} scenes*")
        L.append("")
        L.append(v["summary"])
        L.append("")
        L.append("## Script")
        L.append("")
        for s in v["scenes"]:
            L.append(f"### {s['timecode']} — Scene {s['order']}: {s['title']}")
            L.append("")
            L.append(f"- **Screen:** {s['screen']['route']} ({s['screen']['shot']})")
            L.append(f"- **On-screen text:** {s['on_screen_text']}")
            L.append(f"- **Voice-over:** {s['voice_over']}")
            L.append(f"- **Narration:** {s['narration']}")
            L.append(f"- **Expected action:** {s['expected_action']}")
            L.append(f"- **Duration:** {s['duration_seconds']}s")
            L.append("")
        return "\n".join(L)

    def export(self, video_id: str, fmt: str) -> tuple[bytes | str, str, str]:
        v = self.get(video_id)
        markdown = self._markdown(v)
        title = v["title"]
        fmt = (fmt or "pdf").lower()
        if fmt in ("markdown", "md"):
            return markdown, "text/markdown", f"video-{video_id}.md"
        if fmt == "html":
            return render_html(title, markdown), "text/html", f"video-{video_id}.html"
        return render_pdf(markdown), "application/pdf", f"video-{video_id}.pdf"
