"""Sprint 63A — Product Excellence tests.

Covers inbox notification center, universal timeline, saved views, dashboard
builder, report schedules, collaboration, personalization, product analytics,
command palette, and documentation diagrams — plus API smoke tests.
"""

from __future__ import annotations

import pytest

import app.platform.activity  # noqa: F401 - activity subscriber
import app.platform.product  # noqa: F401 - inbox subscriber
from app.database.session import AsyncSessionLocal
from app.models.organization import Organization, OrganizationMember, OrganizationRole
from app.platform.events import DomainEventType, EventBus
from app.platform.product import (
    CollaborationService,
    DashboardService,
    InboxService,
    PersonalizationService,
    ProductAnalyticsService,
    SavedViewService,
    TimelineService,
)
from app.services.documentation_generator import DocumentationGeneratorService

from .conftest import auth_headers, create_authenticated_user


async def _make_org(session, name="Product Co") -> str:
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    session.add(org)
    await session.flush()
    return org.id


async def _make_user(session, email: str, username: str) -> str:
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        email=email, username=username, full_name="Test User",
        hashed_password=hash_password("password123"),
    )
    session.add(user)
    await session.flush()
    return user.id


async def _add_member(session, org_id: str, user_id: str,
                      role: OrganizationRole = OrganizationRole.DEVELOPER) -> None:
    session.add(OrganizationMember(
        organization_id=org_id, user_id=user_id, role=role))
    await session.flush()


# --------------------------------------------------------------------------- #
# Inbox + timeline
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_inbox_from_domain_event(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        actor_id = await _make_user(session, "actor@example.com", "actor")
        viewer_id = await _make_user(session, "viewer@example.com", "viewer")
        await _add_member(session, org_id, actor_id)
        await _add_member(session, org_id, viewer_id)

        bus = EventBus(session)
        await bus.publish(
            DomainEventType.INCIDENT_CREATED, organization_id=org_id,
            actor_id=actor_id, payload={"summary": "DB outage", "title": "Incident"},
            aggregate_type="incident", aggregate_id="inc-1")
        await session.commit()

        inbox = await InboxService(session).list_inbox(
            organization_id=org_id, user_id=viewer_id)
        assert len(inbox) == 1
        assert inbox[0].title == "Incident"
        assert inbox[0].read_at is None

        actor_inbox = await InboxService(session).list_inbox(
            organization_id=org_id, user_id=actor_id)
        assert len(actor_inbox) == 0


@pytest.mark.asyncio
async def test_timeline_merges_activity_and_comments(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        user_id = await _make_user(session, "tl@example.com", "tluser")
        await _add_member(session, org_id, user_id)

        bus = EventBus(session)
        await bus.publish(
            DomainEventType.INCIDENT_CREATED, organization_id=org_id,
            payload={"summary": "Created"}, aggregate_type="incident",
            aggregate_id="inc-tl")
        await CollaborationService(session).add_comment(
            organization_id=org_id, resource_type="incident", resource_id="inc-tl",
            author_id=user_id, body="Investigating @viewer")
        await session.commit()

        items = await TimelineService(session).get(
            organization_id=org_id, resource_type="incident", resource_id="inc-tl")
        kinds = {i["kind"] for i in items}
        assert "activity" in kinds
        assert "comment" in kinds


# --------------------------------------------------------------------------- #
# Saved views + dashboards
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_saved_views_crud(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        user_id = await _make_user(session, "sv@example.com", "svuser")

        svc = SavedViewService(session)
        view = await svc.create(
            organization_id=org_id, user_id=user_id, name="Open incidents",
            view_type="filter", definition={"status": "open"}, is_shared=False)
        await session.commit()

        listed = await svc.list(organization_id=org_id, user_id=user_id)
        assert any(v.id == view.id for v in listed)
        assert await svc.delete(view.id, user_id=user_id)
        await session.commit()


@pytest.mark.asyncio
async def test_dashboard_widgets(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        user_id = await _make_user(session, "db@example.com", "dbuser")

        svc = DashboardService(session)
        dash = await svc.create(
            organization_id=org_id, user_id=user_id, name="Ops",
            widgets=[{"type": "incidents", "x": 0, "y": 0, "w": 6, "h": 4}])
        updated = await svc.update_widgets(
            dash.id, user_id=user_id,
            widgets=[{"type": "deployments", "x": 0, "y": 0, "w": 12, "h": 4}])
        await session.commit()
        assert updated is not None
        assert updated.widgets[0]["type"] == "deployments"


# --------------------------------------------------------------------------- #
# Personalization + analytics
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_personalization_and_analytics(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        user_id = await _make_user(session, "pa@example.com", "pauser")

        prefs = PersonalizationService(session)
        await prefs.set_pref(user_id=user_id, key="ui.theme", value="dark")
        got = await prefs.get_prefs(user_id=user_id, organization_id=org_id)
        assert got["ui.theme"] == "dark"

        analytics = ProductAnalyticsService(session)
        event = await analytics.track(
            organization_id=org_id, user_id=user_id,
            event_name="navigation", properties={"path": "/incidents", "email": "secret@test.com"},
            session_id="sess-1")
        await session.commit()
        assert event is not None
        assert "email" not in (event.properties or {})

        summary = await analytics.summary(organization_id=org_id, days=7)
        assert summary["total"] >= 1


# --------------------------------------------------------------------------- #
# Documentation diagrams
# --------------------------------------------------------------------------- #
def test_documentation_diagram_bundle():
    bundle = DocumentationGeneratorService.diagram_bundle()
    assert "architecture_mermaid" in bundle
    assert "erd_mermaid" in bundle
    assert "event_flow_mermaid" in bundle
    assert "flowchart" in bundle["architecture_mermaid"]


# --------------------------------------------------------------------------- #
# API smoke tests
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_product_api_smoke(client):
    _, tokens = await create_authenticated_user(
        client, email="prod@example.com", username="produser")
    h = auth_headers(tokens["access_token"])

    inbox = await client.get("/v1/product/inbox", headers=h)
    assert inbox.status_code == 200
    assert isinstance(inbox.json(), list)

    unread = await client.get("/v1/product/inbox/unread-count", headers=h)
    assert unread.status_code == 200
    assert "unread" in unread.json()

    commands = await client.get("/v1/product/commands", headers=h, params={"q": "setting"})
    assert commands.status_code == 200
    assert "results" in commands.json()

    view = await client.post("/v1/product/views", headers=h, json={
        "name": "My view", "view_type": "filter", "definition": {"q": "open"}})
    assert view.status_code == 201, view.text

    dash = await client.post("/v1/product/dashboards", headers=h, json={
        "name": "Main", "widgets": [{"type": "incidents", "x": 0, "y": 0, "w": 6, "h": 4}]})
    assert dash.status_code == 201, dash.text
    dash_id = dash.json()["id"]

    widgets = await client.put(f"/v1/product/dashboards/{dash_id}/widgets", headers=h,
                               json=[{"type": "usage", "x": 0, "y": 0, "w": 12, "h": 4}])
    assert widgets.status_code == 200

    comment = await client.post("/v1/product/collaboration/incident/inc-99/comments",
                                headers=h, json={"body": "Looks resolved"})
    assert comment.status_code == 201, comment.text

    timeline = await client.get("/v1/product/timeline/incident/inc-99", headers=h)
    assert timeline.status_code == 200
    assert timeline.json()["resource_id"] == "inc-99"

    pref = await client.put("/v1/product/preferences", headers=h,
                            json={"key": "ui.density", "value": "compact"})
    assert pref.status_code == 200

    prefs = await client.get("/v1/product/preferences", headers=h)
    assert prefs.status_code == 200
    assert prefs.json().get("ui.density") == "compact"

    track = await client.post("/v1/product/analytics/track", headers=h, json={
        "event_name": "command_palette_open", "properties": {"source": "keyboard"}})
    assert track.status_code == 201

    diagrams = await client.get("/v1/product/docs/diagrams", headers=h)
    assert diagrams.status_code == 200
    assert "architecture_mermaid" in diagrams.json()
