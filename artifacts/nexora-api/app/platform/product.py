"""Product excellence platform (Sprint 63A).

Extends the converged platform (ActivityService, NotificationService, ConfigService,
SearchService, EventBus) with polished enterprise product capabilities:

* Inbox notification center (consumes domain events)
* Universal resource timelines (reuses ActivityService)
* Saved views + dashboard builder
* Unified reporting schedules (extends executive report engine)
* Collaboration (comments, mentions, reactions)
* User personalization (ConfigService user scope)
* Product analytics (privacy-aware)
* Command palette aggregation (search + actions + activity + favorites)
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.platform_core import (
    CollaborationComment,
    CollaborationReaction,
    DashboardLayout,
    DomainEvent,
    InboxNotification,
    ProductAnalyticsEvent,
    ReportSchedule,
    SavedView,
)
from app.platform.activity import ActivityService
from app.platform.config import ConfigService
from app.platform.events import subscribe
from app.platform.notifications import NotificationService
from app.platform.search import SearchService

logger = get_logger(__name__)

_MENTION_RE = re.compile(r"@([\w.+-]+)")
_PII_KEYS = frozenset({"email", "name", "full_name", "password", "token", "secret"})

# Widget types supported by the dashboard builder.
DASHBOARD_WIDGET_TYPES = (
    "incidents", "deployments", "slos", "ai", "billing", "usage",
    "search", "activity", "plugins",
)


# --------------------------------------------------------------------------- #
# Inbox notification center
# --------------------------------------------------------------------------- #
class InboxService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def from_domain_event(self, event: DomainEvent) -> list[InboxNotification]:
        """Create inbox entries for org members when a notable event fires."""
        if not settings.INBOX_FROM_EVENTS_ENABLED or not event.organization_id:
            return []
        from app.models.organization import OrganizationMember

        members = list((await self.session.execute(
            select(OrganizationMember.user_id).where(
                OrganizationMember.organization_id == event.organization_id)
        )).scalars().all())
        if not members:
            return []
        payload = event.payload or {}
        title = payload.get("title") or event.event_type
        body = payload.get("summary") or payload.get("body") or str(title)
        action_url = payload.get("url") or payload.get("action_url")
        priority = payload.get("priority", "normal")
        group_key = event.event_type
        created: list[InboxNotification] = []
        for user_id in members:
            if user_id == event.actor_id:
                continue  # don't notify the actor
            note = InboxNotification(
                organization_id=event.organization_id,
                user_id=user_id,
                title=str(title)[:300],
                body=str(body)[:4000],
                category=event.aggregate_type or "event",
                priority=str(priority)[:10],
                action_url=action_url,
                group_key=group_key,
                source_event_id=event.id,
                meta={"event_type": event.event_type, "aggregate_id": event.aggregate_id},
            )
            self.session.add(note)
            created.append(note)
        if created:
            await self.session.flush()
        return created

    async def list_inbox(
        self, *, organization_id: str, user_id: str,
        unread_only: bool = False, category: str | None = None,
        pinned_only: bool = False, limit: int = 50, offset: int = 0,
    ) -> list[InboxNotification]:
        now = utcnow()
        stmt = select(InboxNotification).where(
            InboxNotification.organization_id == organization_id,
            InboxNotification.user_id == user_id,
            or_(InboxNotification.snoozed_until.is_(None),
                InboxNotification.snoozed_until <= now),
        )
        if unread_only:
            stmt = stmt.where(InboxNotification.read_at.is_(None))
        if category:
            stmt = stmt.where(InboxNotification.category == category)
        if pinned_only:
            stmt = stmt.where(InboxNotification.pinned.is_(True))
        stmt = stmt.order_by(
            InboxNotification.pinned.desc(),
            InboxNotification.created_at.desc(),
        ).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def mark_read(self, note_id: str, *, user_id: str) -> InboxNotification | None:
        note = await self.session.get(InboxNotification, note_id)
        if note is None or note.user_id != user_id:
            return None
        note.read_at = utcnow()
        await self.session.flush()
        return note

    async def mark_all_read(self, *, organization_id: str, user_id: str) -> int:
        rows = await self.list_inbox(organization_id=organization_id, user_id=user_id,
                                     unread_only=True, limit=500)
        now = utcnow()
        for row in rows:
            row.read_at = now
        await self.session.flush()
        return len(rows)

    async def pin(self, note_id: str, *, user_id: str, pinned: bool = True) -> InboxNotification | None:
        note = await self.session.get(InboxNotification, note_id)
        if note is None or note.user_id != user_id:
            return None
        note.pinned = pinned
        await self.session.flush()
        return note

    async def snooze(self, note_id: str, *, user_id: str,
                     until: datetime | None = None, minutes: int = 60) -> InboxNotification | None:
        note = await self.session.get(InboxNotification, note_id)
        if note is None or note.user_id != user_id:
            return None
        note.snoozed_until = until or (utcnow() + timedelta(minutes=minutes))
        await self.session.flush()
        return note

    async def unread_count(self, *, organization_id: str, user_id: str) -> int:
        now = utcnow()
        stmt = select(func.count(InboxNotification.id)).where(
            InboxNotification.organization_id == organization_id,
            InboxNotification.user_id == user_id,
            InboxNotification.read_at.is_(None),
            or_(InboxNotification.snoozed_until.is_(None),
                InboxNotification.snoozed_until <= now),
        )
        return int((await self.session.execute(stmt)).scalar() or 0)


async def inbox_event_handler(session: AsyncSession, event: DomainEvent) -> None:
    """Domain-event subscriber → inbox notification center."""
    if not settings.PRODUCT_EXCELLENCE_ENABLED:
        return
    try:
        await InboxService(session).from_domain_event(event)
    except Exception as exc:  # noqa: BLE001 - must not break event dispatch
        logger.warning("inbox_from_event_failed", error=str(exc))


subscribe("*", inbox_event_handler)


# --------------------------------------------------------------------------- #
# Universal timeline (reuses ActivityService + collaboration)
# --------------------------------------------------------------------------- #
class TimelineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.activity = ActivityService(session)

    async def get(
        self, *, organization_id: str, resource_type: str, resource_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Merge activity entries + comments into a single chronological timeline."""
        activities = await self.activity.list(
            organization_id=organization_id,
            object_type=resource_type,
            object_id=resource_id,
            limit=limit,
        )
        comments = list((await self.session.execute(
            select(CollaborationComment).where(
                CollaborationComment.organization_id == organization_id,
                CollaborationComment.resource_type == resource_type,
                CollaborationComment.resource_id == resource_id,
            ).order_by(CollaborationComment.created_at.desc()).limit(limit)
        )).scalars().all())

        items: list[dict] = []
        for a in activities:
            items.append({
                "kind": "activity",
                "id": a.id,
                "at": a.created_at.isoformat() if a.created_at else None,
                "actor_id": a.actor_id,
                "verb": a.verb,
                "summary": a.summary,
                "event_type": a.event_type,
                "meta": a.meta,
            })
        for c in comments:
            items.append({
                "kind": "comment",
                "id": c.id,
                "at": c.created_at.isoformat() if c.created_at else None,
                "actor_id": c.author_id,
                "body": c.body,
                "parent_id": c.parent_id,
                "mentions": c.mentions,
                "attachments": c.attachments,
            })
        items.sort(key=lambda x: x.get("at") or "", reverse=True)
        return items[:limit]


# --------------------------------------------------------------------------- #
# Saved views
# --------------------------------------------------------------------------- #
class SavedViewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, organization_id: str, user_id: str, name: str,
        view_type: str = "filter", definition: dict | None = None,
        is_shared: bool = False, is_default: bool = False,
    ) -> SavedView:
        if is_default:
            await self._clear_default(organization_id, user_id, view_type)
        view = SavedView(
            organization_id=organization_id, user_id=user_id, name=name,
            view_type=view_type, definition=definition or {},
            is_shared=is_shared, is_default=is_default,
        )
        self.session.add(view)
        await self.session.flush()
        return view

    async def list(
        self, *, organization_id: str, user_id: str,
        view_type: str | None = None,
    ) -> list[SavedView]:
        stmt = select(SavedView).where(
            SavedView.organization_id == organization_id,
            or_(SavedView.user_id == user_id, SavedView.is_shared.is_(True)),
        )
        if view_type:
            stmt = stmt.where(SavedView.view_type == view_type)
        stmt = stmt.order_by(SavedView.is_default.desc(), SavedView.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete(self, view_id: str, *, user_id: str) -> bool:
        view = await self.session.get(SavedView, view_id)
        if view is None or view.user_id != user_id:
            return False
        await self.session.delete(view)
        await self.session.flush()
        return True

    async def _clear_default(self, org_id: str, user_id: str, view_type: str) -> None:
        rows = await self.list(organization_id=org_id, user_id=user_id, view_type=view_type)
        for row in rows:
            if row.is_default and row.user_id == user_id:
                row.is_default = False
        await self.session.flush()


# --------------------------------------------------------------------------- #
# Dashboard builder
# --------------------------------------------------------------------------- #
class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, organization_id: str, user_id: str, name: str,
        widgets: list | None = None, is_shared: bool = False,
        is_default: bool = False,
    ) -> DashboardLayout:
        if is_default:
            await self._clear_default(organization_id, user_id)
        dash = DashboardLayout(
            organization_id=organization_id, user_id=user_id, name=name,
            widgets=widgets or [], is_shared=is_shared, is_default=is_default,
        )
        self.session.add(dash)
        await self.session.flush()
        return dash

    async def update_widgets(self, dash_id: str, *, user_id: str,
                             widgets: list) -> DashboardLayout | None:
        dash = await self.session.get(DashboardLayout, dash_id)
        if dash is None or (dash.user_id != user_id and not dash.is_shared):
            return None
        dash.widgets = widgets
        await self.session.flush()
        return dash

    async def list(self, *, organization_id: str, user_id: str) -> list[DashboardLayout]:
        stmt = select(DashboardLayout).where(
            DashboardLayout.organization_id == organization_id,
            or_(DashboardLayout.user_id == user_id, DashboardLayout.is_shared.is_(True)),
        ).order_by(DashboardLayout.is_default.desc(), DashboardLayout.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete(self, dash_id: str, *, user_id: str) -> bool:
        dash = await self.session.get(DashboardLayout, dash_id)
        if dash is None or dash.user_id != user_id:
            return False
        await self.session.delete(dash)
        await self.session.flush()
        return True

    async def _clear_default(self, org_id: str, user_id: str) -> None:
        for dash in await self.list(organization_id=org_id, user_id=user_id):
            if dash.is_default and dash.user_id == user_id:
                dash.is_default = False
        await self.session.flush()


# --------------------------------------------------------------------------- #
# Reporting schedules (extends executive report engine)
# --------------------------------------------------------------------------- #
_CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90}


class ReportScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, organization_id: str, created_by: str | None, name: str,
        report_type: str = "executive", cadence: str = "monthly",
        export_format: str = "pdf", delivery_channel: str = "email",
        delivery_target: str = "",
    ) -> ReportSchedule:
        sched = ReportSchedule(
            organization_id=organization_id, created_by=created_by, name=name,
            report_type=report_type, cadence=cadence, export_format=export_format,
            delivery_channel=delivery_channel, delivery_target=delivery_target,
            next_run_at=utcnow(),
        )
        self.session.add(sched)
        await self.session.flush()
        return sched

    async def list(self, organization_id: str) -> list[ReportSchedule]:
        stmt = select(ReportSchedule).where(
            ReportSchedule.organization_id == organization_id,
        ).order_by(ReportSchedule.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def run_due(self, *, now: datetime | None = None) -> list[dict]:
        """Generate and deliver reports whose next_run_at has passed."""
        now = now or utcnow()
        stmt = select(ReportSchedule).where(
            ReportSchedule.enabled.is_(True),
            or_(ReportSchedule.next_run_at.is_(None),
                ReportSchedule.next_run_at <= now),
        )
        schedules = list((await self.session.execute(stmt)).scalars().all())
        results: list[dict] = []
        for sched in schedules:
            try:
                result = await self._run_one(sched)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("report_schedule_failed", schedule_id=sched.id, error=str(exc))
                results.append({"schedule_id": sched.id, "ok": False, "error": str(exc)})
        return results

    async def _run_one(self, sched: ReportSchedule) -> dict:
        from app.services.executive_report import ExecutiveReportingService

        # Use a lightweight org context shim for the reporting engine.
        class _Ctx:
            def __init__(self, org_id: str):
                self._org = org_id

            @property
            def requires_organization(self) -> str:
                return self._org

            role = None

        class _User:
            id = sched.created_by
            is_superuser = True

        svc = ExecutiveReportingService(self.session)
        cadence_map = {"weekly": "WEEKLY", "monthly": "MONTHLY", "quarterly": "QUARTERLY",
                       "daily": "WEEKLY"}
        report_type = cadence_map.get(sched.cadence, "MONTHLY")
        report = await svc.generate(
            _User(), _Ctx(sched.organization_id), report_type=report_type)
        content, media_type, filename = self._export(report, sched.export_format)

        delivered = False
        if sched.delivery_channel == "email":
            await NotificationService(self.session).send(
                channel="email", recipient=sched.delivery_target,
                organization_id=sched.organization_id,
                subject=f"Scheduled report: {sched.name}",
                body=f"Your scheduled {sched.report_type} report is attached ({filename}).",
            )
            delivered = True
        elif sched.delivery_channel == "webhook":
            await NotificationService(self.session).send(
                channel="webhook", recipient=sched.delivery_target,
                organization_id=sched.organization_id,
                context={"report_id": report.id, "format": sched.export_format},
            )
            delivered = True

        days = _CADENCE_DAYS.get(sched.cadence, 30)
        sched.last_run_at = utcnow()
        sched.next_run_at = utcnow() + timedelta(days=days)
        await self.session.flush()
        return {
            "schedule_id": sched.id, "ok": True, "report_id": report.id,
            "delivered": delivered, "bytes": len(content),
        }

    @staticmethod
    def _export(report, fmt: str) -> tuple[bytes, str, str]:
        from app.services._reporting import build_export

        if fmt == "csv":
            return _metrics_to_csv(report.metrics or {}), "text/csv", f"report-{report.id}.csv"
        return build_export(
            report.content_markdown or "", fmt,
            title=report.executive_summary or "Report",
            filename_prefix="report", tag=report.id[:8],
        )


def _metrics_to_csv(metrics: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value"])
    for k, v in sorted(metrics.items()):
        writer.writerow([k, v])
    return buf.getvalue().encode("utf-8")


# --------------------------------------------------------------------------- #
# Collaboration
# --------------------------------------------------------------------------- #
class CollaborationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _parse_mentions(self, body: str) -> list[str]:
        return list({m.group(1) for m in _MENTION_RE.finditer(body or "")})

    async def add_comment(
        self, *, organization_id: str, resource_type: str, resource_id: str,
        author_id: str, body: str, parent_id: str | None = None,
        attachments: list | None = None,
    ) -> CollaborationComment:
        mentions = self._parse_mentions(body)
        comment = CollaborationComment(
            organization_id=organization_id, resource_type=resource_type,
            resource_id=resource_id, parent_id=parent_id, author_id=author_id,
            body=body, mentions=mentions, attachments=attachments or [],
        )
        self.session.add(comment)
        await self.session.flush()
        await ActivityService(self.session).record(
            event_type="CommentAdded", organization_id=organization_id,
            actor_id=author_id, verb="commented",
            object_type=resource_type, object_id=resource_id,
            summary=body[:200], meta={"comment_id": comment.id, "mentions": mentions},
        )
        return comment

    async def list_comments(
        self, *, organization_id: str, resource_type: str, resource_id: str,
        limit: int = 100,
    ) -> list[CollaborationComment]:
        stmt = select(CollaborationComment).where(
            CollaborationComment.organization_id == organization_id,
            CollaborationComment.resource_type == resource_type,
            CollaborationComment.resource_id == resource_id,
        ).order_by(CollaborationComment.created_at).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def add_reaction(
        self, *, organization_id: str, user_id: str, emoji: str,
        comment_id: str | None = None,
        resource_type: str | None = None, resource_id: str | None = None,
    ) -> CollaborationReaction:
        reaction = CollaborationReaction(
            organization_id=organization_id, user_id=user_id, emoji=emoji,
            comment_id=comment_id, resource_type=resource_type, resource_id=resource_id,
        )
        self.session.add(reaction)
        await self.session.flush()
        return reaction

    async def list_reactions(
        self, *, organization_id: str, comment_id: str | None = None,
        resource_type: str | None = None, resource_id: str | None = None,
    ) -> list[CollaborationReaction]:
        stmt = select(CollaborationReaction).where(
            CollaborationReaction.organization_id == organization_id)
        if comment_id:
            stmt = stmt.where(CollaborationReaction.comment_id == comment_id)
        elif resource_type and resource_id:
            stmt = stmt.where(
                CollaborationReaction.resource_type == resource_type,
                CollaborationReaction.resource_id == resource_id,
            )
        return list((await self.session.execute(stmt)).scalars().all())


# --------------------------------------------------------------------------- #
# User personalization (ConfigService user scope)
# --------------------------------------------------------------------------- #
_PREF_KEYS = (
    "ui.theme", "ui.density", "ui.language", "ui.timezone",
    "ui.homepage", "ui.favorites", "ui.recently_viewed", "ui.reduced_motion",
)


class PersonalizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.config = ConfigService(session)

    async def get_prefs(self, *, user_id: str, organization_id: str | None = None) -> dict:
        merged = await self.config.resolve_all(organization_id=organization_id, user_id=user_id)
        return {k: merged.get(k) for k in _PREF_KEYS if k in merged}

    async def set_pref(self, *, user_id: str, key: str, value,
                       organization_id: str | None = None) -> None:
        if key not in _PREF_KEYS:
            raise ValueError(f"Unknown preference key: {key}")
        await self.config.set(key=key, value=value, scope="user", scope_id=user_id)

    async def track_recent(self, *, user_id: str, item: dict, max_items: int = 20) -> list:
        recent = await self.config.get("ui.recently_viewed", user_id=user_id, default=[]) or []
        if not isinstance(recent, list):
            recent = []
        recent = [r for r in recent if r.get("path") != item.get("path")]
        recent.insert(0, {**item, "at": utcnow().isoformat()})
        recent = recent[:max_items]
        await self.config.set(key="ui.recently_viewed", value=recent, scope="user", scope_id=user_id)
        return recent

    async def toggle_favorite(self, *, user_id: str, item: dict) -> list:
        favs = await self.config.get("ui.favorites", user_id=user_id, default=[]) or []
        if not isinstance(favs, list):
            favs = []
        path = item.get("path")
        if any(f.get("path") == path for f in favs):
            favs = [f for f in favs if f.get("path") != path]
        else:
            favs.insert(0, item)
        await self.config.set(key="ui.favorites", value=favs, scope="user", scope_id=user_id)
        return favs


# --------------------------------------------------------------------------- #
# Product analytics (privacy-aware)
# --------------------------------------------------------------------------- #
class ProductAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _sanitize_properties(props: dict | None) -> dict:
        if not props:
            return {}
        return {k: v for k, v in props.items() if k.lower() not in _PII_KEYS}

    @staticmethod
    def _session_hash(session_id: str | None) -> str | None:
        if not session_id:
            return None
        return hashlib.sha256(session_id.encode()).hexdigest()[:32]

    async def track(
        self, *, organization_id: str, event_name: str,
        user_id: str | None = None, properties: dict | None = None,
        session_id: str | None = None,
    ) -> ProductAnalyticsEvent | None:
        if not settings.PRODUCT_ANALYTICS_ENABLED:
            return None
        event = ProductAnalyticsEvent(
            organization_id=organization_id, user_id=user_id,
            event_name=event_name[:120],
            properties=self._sanitize_properties(properties),
            session_hash=self._session_hash(session_id),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def summary(self, *, organization_id: str, days: int = 30) -> dict:
        since = utcnow() - timedelta(days=days)
        stmt = (
            select(ProductAnalyticsEvent.event_name, func.count(ProductAnalyticsEvent.id))
            .where(
                ProductAnalyticsEvent.organization_id == organization_id,
                ProductAnalyticsEvent.created_at >= since,
            )
            .group_by(ProductAnalyticsEvent.event_name)
            .order_by(func.count(ProductAnalyticsEvent.id).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return {
            "organization_id": organization_id,
            "window_days": days,
            "events": [{"name": name, "count": int(cnt)} for name, cnt in rows],
            "total": sum(int(c) for _, c in rows),
        }


# --------------------------------------------------------------------------- #
# Command palette aggregation
# --------------------------------------------------------------------------- #
class CommandPaletteService:
    """Server-side command palette: search + activity + favorites + actions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def query(
        self, *, organization_id: str, user_id: str, q: str = "",
        include_ai: bool = True, limit: int = 20,
    ) -> dict:
        results: list[dict] = []
        q = (q or "").strip()

        # Global search (platform index).
        if q:
            search = await SearchService(self.session).search(
                q, organization_id=organization_id, limit=limit // 2)
            for hit in search.get("results", []):
                results.append({
                    "kind": "search", "title": hit["title"], "sub": hit.get("type", ""),
                    "path": hit.get("url"), "score": hit.get("score", 0),
                })

        # Recent activity.
        activities = await ActivityService(self.session).list(
            organization_id=organization_id, limit=5)
        for a in activities:
            results.append({
                "kind": "activity", "title": a.summary, "sub": a.event_type,
                "path": (a.meta or {}).get("url"),
            })

        # User favorites + recents from personalization.
        prefs = await PersonalizationService(self.session).get_prefs(
            user_id=user_id, organization_id=organization_id)
        for fav in (prefs.get("ui.favorites") or [])[:5]:
            results.append({
                "kind": "favorite", "title": fav.get("title", ""), "sub": "Favorite",
                "path": fav.get("path"),
            })

        # AI command suggestions.
        if include_ai and q:
            results.append({
                "kind": "ai", "title": f'Ask Copilot: "{q}"',
                "sub": "AI command", "path": f"/copilot?q={q}",
            })

        # Static actions.
        if not q or "setting" in q.lower():
            results.append({
                "kind": "action", "title": "Open settings", "sub": "Actions",
                "path": "/settings",
            })

        return {"query": q, "results": results[:limit]}
