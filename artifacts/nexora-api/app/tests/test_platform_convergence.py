"""Sprint 62A — Final Platform Convergence tests.

Covers the converged platform: domain event bus (publish/subscribe/retries/
dead-letter/replay), activity feed, unified notifications (channels/templates/
localization/retries/delivery tracking), global search + autocomplete,
configuration inheritance, plugin lifecycle, and the unified execution engine —
plus API smoke tests for every surface.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# Importing the activity module registers the "*" subscriber (event → feed).
import app.platform.activity  # noqa: F401
from app.database.session import AsyncSessionLocal
from app.models.job import JobType
from app.models.organization import Organization
from app.models.runbook import Runbook
from app.platform.activity import ActivityService
from app.platform.config import ConfigService
from app.platform.events import (
    DomainEventType,
    EventBus,
    clear_subscribers,
    subscribe,
)
from app.platform.execution import ExecutionEngine
from app.platform.notifications import NotificationService, SlackProvider
from app.platform.plugins import PluginService
from app.platform.search import SearchService

from .conftest import auth_headers, create_authenticated_user


async def _make_org(session, name="Acme") -> str:
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    session.add(org)
    await session.flush()
    return org.id


def _restore_activity_subscriber():
    from app.platform.events import register_default_subscribers

    register_default_subscribers()


# --------------------------------------------------------------------------- #
# Event bus + activity feed
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_event_publish_dispatch_and_activity(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        seen: list[str] = []

        async def handler(s, event):
            seen.append(event.event_type)

        subscribe(DomainEventType.INCIDENT_CREATED.value, handler)
        try:
            bus = EventBus(session)
            event = await bus.publish(
                DomainEventType.INCIDENT_CREATED, organization_id=org_id,
                payload={"summary": "DB down"}, aggregate_type="incident",
                aggregate_id="inc-1")
            await session.commit()
        finally:
            clear_subscribers()
            _restore_activity_subscriber()

        assert seen == ["IncidentCreated"]
        assert event.status == "processed"
        # The "*" subscriber mirrored it into the activity feed.
        feed = await ActivityService(session).list(organization_id=org_id)
        assert len(feed) == 1
        assert feed[0].object_type == "incident"
        assert feed[0].summary == "DB down"


@pytest.mark.asyncio
async def test_event_retry_then_dead_letter(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)

        async def boom(s, event):
            raise RuntimeError("handler failure")

        subscribe("CustomBoom", boom)
        try:
            bus = EventBus(session)
            event = await bus.publish("CustomBoom", organization_id=org_id,
                                      max_attempts=3)
            assert event.status == "failed"
            assert event.attempts == 1

            await bus.retry_failed(organization_id=org_id)
            assert event.attempts == 2
            assert event.status == "failed"

            await bus.retry_failed(organization_id=org_id)
            assert event.attempts == 3
            assert event.status == "dead_letter"

            # Requeue resets attempts and re-dispatches (still failing -> DLQ).
            requeued = await bus.requeue_dead_letter(event.id)
            assert requeued.attempts == 1
            await session.commit()
        finally:
            clear_subscribers()
            _restore_activity_subscriber()


@pytest.mark.asyncio
async def test_event_replay(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        calls = {"n": 0}

        async def handler(s, event):
            calls["n"] += 1

        subscribe("Replayable", handler)
        try:
            bus = EventBus(session)
            event = await bus.publish("Replayable", organization_id=org_id)
            assert calls["n"] == 1
            await bus.replay(event.id)
            assert calls["n"] == 2
            await session.commit()
        finally:
            clear_subscribers()
            _restore_activity_subscriber()


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_notification_simulated_delivery(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = NotificationService(session)
        msg = await svc.send(channel="slack", recipient="#alerts",
                             organization_id=org_id, body="hello")
        await session.commit()
        assert msg.status == "sent"
        assert msg.provider == "simulated"
        assert msg.attempts == 1
        assert msg.sent_at is not None


@pytest.mark.asyncio
async def test_notification_template_and_localization(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = NotificationService(session)
        await svc.upsert_template(
            key="incident.alert", channel="email",
            subject_template="[{{severity}}] {{title}}",
            body_template="Incident {{title}} is {{severity}}", locale="en",
            organization_id=org_id)
        msg = await svc.send(
            channel="email", recipient="ops@acme.test", organization_id=org_id,
            template_key="incident.alert",
            context={"severity": "SEV1", "title": "API outage"})
        await session.commit()
        assert msg.subject == "[SEV1] API outage"
        assert msg.body == "Incident API outage is SEV1"


@pytest.mark.asyncio
async def test_notification_retry_and_dead_letter(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = NotificationService(session)
        with patch.object(SlackProvider, "send",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            msg = await svc.send(channel="slack", recipient="#x",
                                 organization_id=org_id, body="hi", max_attempts=2)
            assert msg.status == "dead_letter"
            assert msg.attempts == 2
            assert "boom" in (msg.error or "")
        # Recover on retry once the provider works again.
        recovered = await svc.retry(msg.id)
        await session.commit()
        assert recovered.status == "sent"


@pytest.mark.asyncio
async def test_notification_unsupported_channel(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        with pytest.raises(KeyError):
            await NotificationService(session).send(
                channel="carrier-pigeon", recipient="x", organization_id=org_id,
                body="hi")


# --------------------------------------------------------------------------- #
# Global search
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_search_and_autocomplete(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        session.add(Runbook(organization_id=org_id, title="Database Failover",
                            category="db", summary="How to fail over the primary DB",
                            status="published"))
        session.add(Runbook(organization_id=org_id, title="Cache Warmup",
                            category="cache", summary="Warm the Redis cache",
                            status="published"))
        await session.commit()

        svc = SearchService(session)
        result = await svc.search("Database", organization_id=org_id, types=["runbook"])
        assert result["total"] >= 1
        assert any(r["title"] == "Database Failover" for r in result["results"])
        # Tenant isolation: other org sees nothing.
        other = await svc.search("Database", organization_id="no-such-org",
                                 types=["runbook"])
        assert other["total"] == 0

        suggestions = await svc.autocomplete("Data", organization_id=org_id,
                                             types=["runbook"])
        assert any(s["title"] == "Database Failover" for s in suggestions)


@pytest.mark.asyncio
async def test_search_semantic_rerank_runs(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        session.add(Runbook(organization_id=org_id, title="Scaling Postgres",
                            category="db", summary="Scale the database",
                            status="published"))
        await session.commit()
        result = await SearchService(session).search(
            "database scaling", organization_id=org_id, types=["runbook"],
            semantic=True)
        assert result["total"] >= 1


# --------------------------------------------------------------------------- #
# Configuration platform
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_config_inheritance(setup_db):
    async with AsyncSessionLocal() as session:
        cfg = ConfigService(session)
        await cfg.set(key="theme", value="light", scope="global")
        await cfg.set(key="theme", value="dark", scope="organization", scope_id="org1")
        await cfg.set(key="theme", value="solarized", scope="user", scope_id="user1")
        await session.commit()

        # Global only.
        assert await cfg.get("theme") == "light"
        # Org overrides global.
        assert await cfg.get("theme", organization_id="org1") == "dark"
        # User overrides org + global.
        assert await cfg.get("theme", organization_id="org1", user_id="user1") == "solarized"
        # Unknown user falls back to org.
        assert await cfg.get("theme", organization_id="org1", user_id="other") == "dark"


@pytest.mark.asyncio
async def test_config_flags_and_resolve_all(setup_db):
    async with AsyncSessionLocal() as session:
        cfg = ConfigService(session)
        await cfg.set(key="beta_ui", value=True, scope="organization",
                     scope_id="org1", is_feature_flag=True)
        await cfg.set(key="max_items", value=50, scope="global")
        await session.commit()
        assert await cfg.get_flag("beta_ui", organization_id="org1") is True
        assert await cfg.get_flag("missing", organization_id="org1", default=False) is False
        merged = await cfg.resolve_all(organization_id="org1")
        assert merged["beta_ui"] is True
        assert merged["max_items"] == 50


# --------------------------------------------------------------------------- #
# Plugin framework
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_plugin_lifecycle(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = PluginService(session)
        created = await svc.seed_catalog()
        assert created >= 1
        catalog = await svc.list_catalog()
        slugs = {p.slug for p in catalog}
        assert "slack-notifications" in slugs

        inst = await svc.install(organization_id=org_id, slug="jira-sync")
        assert inst.status == "enabled"
        caps = await svc.capabilities(org_id)
        assert "jira.create_issue" in caps["tools"]

        await svc.disable(organization_id=org_id, slug="jira-sync")
        caps_after = await svc.capabilities(org_id)
        assert caps_after["tools"] == []

        await svc.enable(organization_id=org_id, slug="jira-sync")
        upgraded = await svc.upgrade(organization_id=org_id, slug="jira-sync",
                                     version="2.0.0")
        assert upgraded.version == "2.0.0"

        assert await svc.uninstall(organization_id=org_id, slug="jira-sync") is True
        assert await svc.list_installed(org_id) == []
        await session.commit()


# --------------------------------------------------------------------------- #
# Unified execution engine
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_execution_engine_checkpoint_resume_cancel(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        from app.services.jobs import JobService

        job = await JobService(session).create(
            job_type=JobType.AI_TEAM_AGENT, organization_id=org_id,
            created_by=None, params={"x": 1})
        await session.commit()

        engine = ExecutionEngine(session)
        cp1 = await engine.checkpoint(job.id, label="step1", state={"i": 1},
                                      organization_id=org_id)
        cp2 = await engine.checkpoint(job.id, label="step2", state={"i": 2},
                                      organization_id=org_id)
        assert cp1.sequence == 0 and cp2.sequence == 1
        assert len(await engine.list_checkpoints(job.id)) == 2
        latest = await engine.latest_checkpoint(job.id)
        assert latest.state == {"i": 2}

        resumed = await engine.resume(job.id, organization_id=org_id)
        assert resumed["params"]["_resume_state"] == {"i": 2}
        assert resumed["status"] == "QUEUED"

        cancelled = await engine.cancel(job.id, organization_id=org_id)
        assert cancelled is True


@pytest.mark.asyncio
async def test_execution_engine_submit(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        fake_pool = AsyncMock()
        fake_pool.enqueue_job = AsyncMock(return_value=type("J", (), {"job_id": "arq-1"})())
        with patch("app.jobs.queue.get_arq_pool", new=AsyncMock(return_value=fake_pool)):
            data = await ExecutionEngine(session).submit(
                task_name="run_ai_team_agent", job_type=JobType.AI_TEAM_AGENT,
                organization_id=org_id, user_id=None, params={"agent_id": "a"})
        assert data["status"] == "QUEUED"
        assert data["job_type"] == "AI_TEAM_AGENT"


# --------------------------------------------------------------------------- #
# API smoke tests
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_platform_api_events_and_activity(client):
    _, tokens = await create_authenticated_user(
        client, email="plat1@example.com", username="plat1")
    h = auth_headers(tokens["access_token"])

    pub = await client.post("/v1/platform/events", headers=h, json={
        "event_type": "DeploymentCompleted", "payload": {"summary": "v2 shipped"},
        "aggregate_type": "deployment", "aggregate_id": "dep-1"})
    assert pub.status_code == 201, pub.text
    assert pub.json()["status"] == "processed"

    events = await client.get("/v1/platform/events", headers=h)
    assert events.status_code == 200
    assert any(e["event_type"] == "DeploymentCompleted" for e in events.json())

    feed = await client.get("/v1/platform/activity", headers=h)
    assert feed.status_code == 200
    assert any(a["event_type"] == "DeploymentCompleted" for a in feed.json())


@pytest.mark.asyncio
async def test_platform_api_notifications_search_config_plugins(client):
    _, tokens = await create_authenticated_user(
        client, email="plat2@example.com", username="plat2")
    h = auth_headers(tokens["access_token"])

    note = await client.post("/v1/platform/notifications", headers=h, json={
        "channel": "slack", "recipient": "#ops", "body": "hi"})
    assert note.status_code == 201, note.text
    assert note.json()["status"] == "sent"

    search = await client.get("/v1/platform/search", headers=h, params={"q": "anything"})
    assert search.status_code == 200
    assert "results" in search.json()

    set_cfg = await client.put("/v1/platform/config", headers=h, json={
        "key": "ui.density", "value": "compact", "scope": "user"})
    assert set_cfg.status_code == 200
    got = await client.get("/v1/platform/config/ui.density", headers=h)
    assert got.json()["value"] == "compact"

    # The test client does not run the startup lifespan, so seed the catalog.
    async with AsyncSessionLocal() as session:
        await PluginService(session).seed_catalog()
        await session.commit()

    catalog = await client.get("/v1/platform/plugins/catalog", headers=h)
    assert catalog.status_code == 200
    assert len(catalog.json()) >= 1
    install = await client.post("/v1/platform/plugins/install", headers=h,
                               json={"slug": "slack-notifications"})
    assert install.status_code == 201, install.text
    installed = await client.get("/v1/platform/plugins", headers=h)
    assert any(p["plugin_slug"] == "slack-notifications" for p in installed.json())


# --------------------------------------------------------------------------- #
# SDK generation
# --------------------------------------------------------------------------- #
def test_sdk_generation_from_api():
    import ast

    from scripts.generate_sdk import generate

    artifacts = generate(write=False)
    assert int(artifacts["operations"]) > 100
    # Generated Python client must be valid Python and expose a converged op.
    py = artifacts["sdk/python/nexora_client/__init__.py"]
    ast.parse(py)
    assert "class NexoraClient" in py
    assert "platform_search" in py  # the global search operation is present
    ts = artifacts["sdk/typescript/src/client.ts"]
    assert "export class NexoraClient" in ts
    assert "openapi" in artifacts["sdk/openapi.json"]
