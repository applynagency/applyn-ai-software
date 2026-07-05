"""Sprint 62B — Enterprise Production Hardening & Scale tests.

Covers every hardening area: event-bus exactly-once + replay-by-range + durable
drain, AI provider circuit breaker + token budget + embedding/semantic caches,
graph caches + analytics + cycle/orphan detection, execution leases + stalled
recovery + analytics, search index + typo/synonym/phrase + analytics, DB
bulk/batch + keyset pagination, security (JWT key rotation, anomaly detection,
CSP nonce), multi-region (clock-skew, idempotent replication, UTC, object store),
and operations (maintenance/kill-switch/rollout/support-bundle/config io) — plus
API smoke tests.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import app.platform.activity  # noqa: F401 - registers the "*" subscriber
from app.database.base import utcnow
from app.database.session import AsyncSessionLocal
from app.models.organization import Organization

from .conftest import auth_headers, create_authenticated_user


async def _make_org(session, name="Hardening Co") -> str:
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    session.add(org)
    await session.flush()
    return org.id


# --------------------------------------------------------------------------- #
# 1. Event bus hardening
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_event_idempotency_no_duplicate(setup_db):
    from app.platform.events import DomainEventType, EventBus

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        bus = EventBus(session)
        e1 = await bus.publish(DomainEventType.ORGANIZATION_CREATED, organization_id=org_id,
                               idempotency_key="org-create-1", dispatch=False)
        e2 = await bus.publish(DomainEventType.ORGANIZATION_CREATED, organization_id=org_id,
                               idempotency_key="org-create-1", dispatch=False)
        await session.commit()
        assert e1.id == e2.id  # second publish is a no-op


@pytest.mark.asyncio
async def test_event_drain_pending_exactly_once(setup_db):
    from app.platform.events import DomainEventType as DT
    from app.platform.events import (
        EventBus,
        clear_subscribers,
        subscribe,
    )

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        delivered: list[str] = []

        async def handler(s, event):
            delivered.append(event.id)

        subscribe(DT.WORKFLOW_COMPLETED.value, handler)
        try:
            bus = EventBus(session)
            # Persist without dispatching (outbox), then drain.
            for i in range(3):
                await bus.publish(DT.WORKFLOW_COMPLETED, organization_id=org_id,
                                  payload={"i": i}, dispatch=False)
            await session.commit()
            assert await bus.pending_count(organization_id=org_id) == 3

            first = await bus.drain_pending(limit=10)
            await session.commit()
            assert first["delivered"] == 3
            # Re-draining delivers nothing more (exactly-once via status ack).
            second = await bus.drain_pending(limit=10)
            assert second["claimed"] == 0
            assert len(delivered) == 3
        finally:
            clear_subscribers()
            from app.platform.events import register_default_subscribers

            register_default_subscribers()


@pytest.mark.asyncio
async def test_event_poison_dead_letters_then_replay_range(setup_db):
    from app.models.platform_core import EventStatus
    from app.platform.events import DomainEventType as DT
    from app.platform.events import (
        EventBus,
        clear_subscribers,
        subscribe,
    )

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)

        async def boom(s, event):
            raise RuntimeError("handler always fails")

        subscribe(DT.DEPLOYMENT_COMPLETED.value, boom)
        try:
            bus = EventBus(session)
            ev = await bus.publish(DT.DEPLOYMENT_COMPLETED, organization_id=org_id,
                                   max_attempts=2, dispatch=False)
            await session.commit()
            # Drain repeatedly until poison-guard dead-letters it.
            for _ in range(5):
                await bus.drain_pending(limit=10)
                await session.commit()
            await session.refresh(ev)
            assert ev.status == EventStatus.DEAD_LETTER.value
            assert ev.attempts >= 2
        finally:
            clear_subscribers()
            from app.platform.events import register_default_subscribers

            register_default_subscribers()

        # Replay by time range counts the matching events.
        count = await EventBus(session).replay_range(
            since=utcnow() - timedelta(hours=1), organization_id=org_id,
            event_type=DT.DEPLOYMENT_COMPLETED.value)
        assert count == 1


# --------------------------------------------------------------------------- #
# 2. AI platform hardening
# --------------------------------------------------------------------------- #
def test_provider_circuit_breaker_open_halfopen_close(monkeypatch):
    from app.ai.health import ProviderHealthRegistry
    from app.core.config import settings

    # The breaker enforces a 1.0s minimum cooldown, so use that floor.
    monkeypatch.setattr(settings, "AI_PROVIDER_CB_THRESHOLD", 2)
    monkeypatch.setattr(settings, "AI_PROVIDER_CB_COOLDOWN_SECONDS", 1.0)
    reg = ProviderHealthRegistry()

    assert reg.is_available("openai")
    reg.record_failure("openai", "timeout")
    assert reg.is_available("openai")  # one failure < threshold
    reg.record_failure("openai", "timeout")
    assert reg.is_open("openai")
    assert not reg.is_available("openai")  # circuit open

    import time
    time.sleep(1.1)
    assert reg.is_available("openai")  # half-open probe allowed
    reg.record_success("openai")
    assert not reg.is_open("openai")  # closed again


@pytest.mark.asyncio
async def test_token_budget_status_and_check(setup_db, monkeypatch):
    from app.ai.budget import BudgetExceededError, TokenBudget
    from app.ai.cost import CostTracker
    from app.ai.types import LLMResponse, TokenUsage
    from app.core.config import settings

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        # Record some usage today.
        resp = LLMResponse(text="x", provider="anthropic", model="m",
                           usage=TokenUsage(600, 600), mode="live")
        await CostTracker(session).record(organization_id=org_id, feature="t", response=resp)
        await session.commit()

        monkeypatch.setattr(settings, "AI_TOKEN_BUDGET_ENABLED", True)
        monkeypatch.setattr(settings, "AI_DAILY_TOKEN_BUDGET", 1000)
        budget = TokenBudget(session)
        status = await budget.status(org_id)
        assert status["used"] == 1200
        assert status["exceeded"] is True
        with pytest.raises(BudgetExceededError):
            await budget.check(org_id)


@pytest.mark.asyncio
async def test_embedding_cache_reuses_vectors(setup_db, monkeypatch):
    from app.ai import cache as ai_cache
    from app.core.config import settings
    from app.redis import cache as redis_cache

    redis_cache.clear_fallback()
    monkeypatch.setattr(settings, "AI_EMBEDDING_CACHE_ENABLED", True)

    calls = {"n": 0}

    class _Embedder:
        provider = "offline-hash"

        async def embed_texts(self, texts):
            calls["n"] += 1
            return [[float(len(t))] for t in texts]

    emb = _Embedder()
    v1 = await ai_cache.cached_embed(["alpha", "beta"], embedder=emb)
    assert calls["n"] == 1
    v2 = await ai_cache.cached_embed(["alpha", "beta"], embedder=emb)
    assert v1 == v2
    assert calls["n"] == 1  # served from cache


def test_semantic_cache_hits_near_duplicate(monkeypatch):
    from app.ai.cache import SemanticResponseCache
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_SEMANTIC_CACHE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_SEMANTIC_CACHE_THRESHOLD", 0.9)
    sc = SemanticResponseCache()
    sc.store("org1", [1.0, 0.0, 0.0], "cached answer")
    assert sc.lookup("org1", [0.99, 0.01, 0.0]) == "cached answer"
    assert sc.lookup("org1", [0.0, 1.0, 0.0]) is None


# --------------------------------------------------------------------------- #
# 3. Graph optimization
# --------------------------------------------------------------------------- #
async def _make_service_graph(session, org_id, edges, nodes=None):
    from app.models.universal_discovery import KnowledgeGraphEdge, KnowledgeGraphNode
    from app.services.graph import invalidate_graph_cache, service_key

    node_ids = set(nodes or [])
    for a, b in edges:
        node_ids.add(a)
        node_ids.add(b)
    for nid in node_ids:
        session.add(KnowledgeGraphNode(
            organization_id=org_id, node_key=service_key(nid),
            node_type="service", name=nid))
    for a, b in edges:
        session.add(KnowledgeGraphEdge(
            organization_id=org_id, source_key=service_key(a),
            target_key=service_key(b), relationship_type="depends_on"))
    await session.flush()
    await invalidate_graph_cache(org_id)


@pytest.mark.asyncio
async def test_graph_traversal_and_analytics(setup_db):
    from app.redis import cache as redis_cache
    from app.services.graph import GraphService

    redis_cache.clear_fallback()
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        # A -> B -> C  (A depends on B depends on C); D is an orphan.
        await _make_service_graph(session, org_id, [("A", "B"), ("B", "C")], nodes=["D"])
        await session.commit()

        gs = GraphService(session)
        assert set(await gs.downstream_dependencies(org_id, "A")) == {"B", "C"}
        assert set(await gs.blast_radius(org_id, "C")) == {"A", "B"}
        assert await gs.cached_shortest_path(org_id, "A", "C") == ["A", "B", "C"]
        assert await gs.find_orphans(org_id) == ["D"]
        assert await gs.find_cycle(org_id) is False

        analytics = await gs.analytics(org_id)
        assert analytics["nodes"] == 4
        assert analytics["edges"] == 2
        assert analytics["orphan_count"] == 1
        # Second call is served from cache (no error, same shape).
        assert (await gs.analytics(org_id))["edges"] == 2


@pytest.mark.asyncio
async def test_graph_cycle_detection(setup_db):
    from app.redis import cache as redis_cache
    from app.services.graph import GraphService

    redis_cache.clear_fallback()
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        await _make_service_graph(session, org_id, [("X", "Y"), ("Y", "Z"), ("Z", "X")])
        await session.commit()
        assert await GraphService(session).find_cycle(org_id) is True


# --------------------------------------------------------------------------- #
# 4. Execution engine hardening
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_execution_leases_and_heartbeat(setup_db):
    from app.models.job import JobType
    from app.platform.execution import ExecutionEngine
    from app.services.jobs import JobService

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        job = await JobService(session).create(
            job_type=JobType.AI_TEAM_AGENT, organization_id=org_id, created_by=None)
        await session.commit()
        engine = ExecutionEngine(session)
        assert await engine.claim(job.id, "worker-1") is True
        # A different worker cannot steal a live lease.
        assert await engine.claim(job.id, "worker-2") is False
        assert await engine.heartbeat(job.id, "worker-1") is True
        assert await engine.heartbeat(job.id, "worker-2") is False


@pytest.mark.asyncio
async def test_execution_recovery_of_stalled_run(setup_db):
    from app.models.job import Job, JobStatus, JobType
    from app.platform.execution import ExecutionEngine

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        past = utcnow() - timedelta(minutes=10)
        job = Job(job_type=JobType.AI_TEAM_AGENT.value, organization_id=org_id,
                  status=JobStatus.RUNNING.value, attempts=1, max_attempts=3,
                  started_at=past, lease_owner="dead-worker", lease_expires_at=past,
                  heartbeat_at=past)
        session.add(job)
        await session.commit()

        result = await ExecutionEngine(session).recover_stalled()
        assert result["checked"] == 1
        assert result["requeued"] == 1
        await session.refresh(job)
        assert job.status == JobStatus.QUEUED.value
        assert job.lease_owner is None


@pytest.mark.asyncio
async def test_execution_analytics(setup_db):
    from app.models.job import JobType
    from app.platform.execution import ExecutionEngine
    from app.services.jobs import JobService

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        for _ in range(2):
            await JobService(session).create(
                job_type=JobType.AI_TEAM_AGENT, organization_id=org_id, created_by=None)
        await session.commit()
        analytics = await ExecutionEngine(session).analytics(organization_id=org_id)
        assert analytics["total"] == 2


# --------------------------------------------------------------------------- #
# 5. Search platform
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_search_index_typo_synonym_phrase(setup_db, monkeypatch):
    from app.core.config import settings
    from app.platform.search import SearchIndexer, SearchService

    monkeypatch.setattr(settings, "SEARCH_INDEX_ENABLED", True)
    monkeypatch.setattr(settings, "SEARCH_TYPO_TOLERANCE", True)
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        indexer = SearchIndexer(session)
        await indexer.index_entity(
            entity_type="runbook", entity_id="r1", organization_id=org_id,
            title="Database failover runbook",
            body="Steps to recover the primary postgres database during an outage")
        await indexer.index_entity(
            entity_type="incident", entity_id="i1", organization_id=org_id,
            title="Kubernetes node pressure", body="k8s eviction storm")
        await session.commit()

        svc = SearchService(session)
        # synonym: "db" should match "database" docs
        r = await svc.search("db", organization_id=org_id)
        assert r["backend"] == "index"
        assert any(h["id"] == "r1" for h in r["results"])
        # typo tolerance: "databse" (typo) still scores against "database"
        # (the correct token "failover" keeps it in the candidate set).
        r2 = await svc.search("databse failover", organization_id=org_id)
        assert any(h["id"] == "r1" for h in r2["results"])
        # phrase search
        r3 = await svc.search('"primary postgres"', organization_id=org_id)
        assert any(h["id"] == "r1" for h in r3["results"])
        # synonym k8s -> kubernetes
        r4 = await svc.search("k8s", organization_id=org_id)
        assert any(h["id"] == "i1" for h in r4["results"])


@pytest.mark.asyncio
async def test_search_analytics_logged(setup_db, monkeypatch):
    from app.core.config import settings
    from app.platform.search import SearchService

    monkeypatch.setattr(settings, "SEARCH_ANALYTICS_ENABLED", True)
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = SearchService(session)
        await svc.search("nothing matches xyzzy", organization_id=org_id)
        await session.commit()
        analytics = await svc.analytics(organization_id=org_id)
        assert analytics["window_days"] == 7
        assert any(q["query"] for q in analytics["top_queries"])


# --------------------------------------------------------------------------- #
# 6. Database optimization
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_bulk_insert_and_batch_update(setup_db):
    import uuid

    from app.database.bulk import batch_update_by_ids, bulk_insert
    from app.models.platform_core import SearchDocument

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        rows = [{
            "id": uuid.uuid4().hex, "organization_id": org_id,
            "entity_type": "asset", "entity_id": f"a{i}", "title": f"asset {i}",
            "body": "", "keywords": f"asset {i}", "weight": 1.0,
            "created_at": utcnow(), "updated_at": utcnow(),
        } for i in range(5)]
        n = await bulk_insert(session, SearchDocument, rows, chunk_size=2)
        await session.commit()
        assert n == 5

        ids = [r["id"] for r in rows[:3]]
        updated = await batch_update_by_ids(
            session, SearchDocument, ids, {"weight": 2.0})
        await session.commit()
        assert updated == 3


@pytest.mark.asyncio
async def test_keyset_pagination(setup_db):
    from sqlalchemy import select

    from app.database.pagination import keyset_page
    from app.models.job import Job, JobType
    from app.services.jobs import JobService

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        for _ in range(5):
            await JobService(session).create(
                job_type=JobType.AI_TEAM_AGENT, organization_id=org_id, created_by=None)
        await session.commit()

        # Order by id (a stable string key) so the cursor round-trips cleanly on
        # SQLite (the DateTime column type rejects string-bound cursor values).
        base = select(Job).where(Job.organization_id == org_id)
        page1 = await keyset_page(session, Job, order_col=Job.id,
                                  id_col=Job.id, limit=2, base_stmt=base)
        assert len(page1.items) == 2
        assert page1.has_more is True
        page2 = await keyset_page(session, Job, order_col=Job.id, id_col=Job.id,
                                  limit=2, base_stmt=base, cursor=page1.next_cursor)
        assert len(page2.items) == 2
        # No overlap between pages.
        assert {j.id for j in page1.items}.isdisjoint({j.id for j in page2.items})


# --------------------------------------------------------------------------- #
# 7. Security hardening
# --------------------------------------------------------------------------- #
def test_jwt_key_rotation_accepts_retired_secret(monkeypatch):
    from jose import jwt

    from app.core import security
    from app.core.config import settings

    old_secret = "old-secret-value"
    token = jwt.encode({"sub": "u1", "type": "access"}, old_secret,
                       algorithm=settings.JWT_ALGORITHM)
    # Active key differs; retired list contains the old secret → still verifies.
    monkeypatch.setattr(settings, "JWT_SECRET_KEYS_RETIRED", old_secret)
    payload = security.decode_token(token)
    assert payload["sub"] == "u1"


@pytest.mark.asyncio
async def test_login_anomaly_records_failures(setup_db):
    from app.services.identity.anomaly import LoginAnomalyDetector

    async with AsyncSessionLocal() as session:
        await _make_org(session)
        det = LoginAnomalyDetector(session)
        await det.record_failure(email="attacker@example.com", ip="1.2.3.4")
        await det.record_failure(email="attacker@example.com", ip="1.2.3.4")
        await session.commit()
        assert await det.recent_failures(email="attacker@example.com") == 2


def test_csp_nonce_header(monkeypatch):
    """Security headers can carry a per-request CSP nonce when enabled."""
    from app.middleware.security_headers import _build_app_csp, generate_nonce

    nonce = generate_nonce()
    csp = _build_app_csp(production=True, nonce=nonce, trusted_types=True)
    assert f"'nonce-{nonce}'" in csp
    assert "require-trusted-types-for 'script'" in csp


# --------------------------------------------------------------------------- #
# 8. Multi-region readiness
# --------------------------------------------------------------------------- #
def test_clock_skew_and_utc(monkeypatch):
    from app.core.config import settings
    from app.platform import region

    monkeypatch.setattr(settings, "CLOCK_SKEW_TOLERANCE_SECONDS", 60)
    assert region.clock_skew_ok(region.now_utc()) is True
    assert region.clock_skew_ok(region.now_utc() - timedelta(hours=2)) is False
    assert region.is_utc(region.now_utc()) is True


@pytest.mark.asyncio
async def test_idempotent_replication(setup_db):
    from app.platform import region

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        a = await region.apply_replicated_event(
            session, source_region="eu", event_type="WorkflowCompleted",
            payload={"x": 1}, aggregate_id="wf1", revision="1", organization_id=org_id)
        b = await region.apply_replicated_event(
            session, source_region="eu", event_type="WorkflowCompleted",
            payload={"x": 1}, aggregate_id="wf1", revision="1", organization_id=org_id)
        await session.commit()
        assert a["accepted"] and b["accepted"]
        assert a["event_id"] == b["event_id"]  # deduped


def test_utc_storage_verification():
    from app.models.job import Job
    from app.models.platform_core import DomainEvent
    from app.platform.region import verify_utc_storage

    # Our timezone-aware models should report no issues.
    assert verify_utc_storage(Job, DomainEvent) == []


@pytest.mark.asyncio
async def test_local_object_store(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.storage.objectstore import LocalObjectStore

    monkeypatch.setattr(settings, "OBJECT_STORE_LOCAL_DIR", str(tmp_path))
    store = LocalObjectStore(str(tmp_path))
    await store.put("exports/report.json", b'{"ok":true}')
    assert await store.exists("exports/report.json")
    assert await store.get("exports/report.json") == b'{"ok":true}'
    await store.delete("exports/report.json")
    assert not await store.exists("exports/report.json")


# --------------------------------------------------------------------------- #
# 9. Operations
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_maintenance_and_kill_switch(setup_db):
    from app.platform.operations import OperationsService, clear_cache

    async with AsyncSessionLocal() as session:
        ops = OperationsService(session)
        clear_cache()
        assert (await ops.maintenance_status())["enabled"] is False
        await ops.set_maintenance(True, message="brb")
        await session.commit()
        clear_cache()
        status = await ops.maintenance_status()
        assert status["enabled"] is True and status["message"] == "brb"

        await ops.set_kill_switch("discovery", True)
        await session.commit()
        clear_cache()
        assert await ops.is_killed("discovery") is True


@pytest.mark.asyncio
async def test_feature_rollout_is_deterministic(setup_db):
    from app.platform.operations import OperationsService

    async with AsyncSessionLocal() as session:
        ops = OperationsService(session)
        await ops.set_rollout("new_ui", 100)
        await session.commit()
        assert await ops.is_rolled_out("new_ui", organization_id="org-x") is True
        await ops.set_rollout("new_ui", 0)
        await session.commit()
        assert await ops.is_rolled_out("new_ui", organization_id="org-x") is False


@pytest.mark.asyncio
async def test_config_export_import(setup_db):
    from app.platform.config import ConfigService
    from app.platform.operations import OperationsService

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        await ConfigService(session).set(key="theme", value="dark",
                                         scope="organization", scope_id=org_id)
        await session.commit()
        ops = OperationsService(session)
        bundle = await ops.export_config(organization_id=org_id)
        assert any(e["key"] == "theme" for e in bundle["entries"])
        # Import into a fresh value set.
        count = await ops.import_config(bundle)
        await session.commit()
        assert count >= 1


@pytest.mark.asyncio
async def test_support_bundle(setup_db):
    from app.platform.operations import OperationsService

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        bundle = await OperationsService(session).support_bundle(organization_id=org_id)
        assert "diagnostics" in bundle
        assert "execution" in bundle


# --------------------------------------------------------------------------- #
# 10. API smoke tests
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ai_health_endpoint(client):
    _, tokens = await create_authenticated_user(
        client, email="hard1@example.com", username="hard1")
    h = auth_headers(tokens["access_token"])
    resp = await client.get("/v1/ai/health", headers=h)
    assert resp.status_code == 200, resp.text
    assert "providers" in resp.json()


@pytest.mark.asyncio
async def test_events_pending_endpoint(client):
    _, tokens = await create_authenticated_user(
        client, email="hard2@example.com", username="hard2")
    h = auth_headers(tokens["access_token"])
    resp = await client.get("/v1/platform/events/pending", headers=h)
    assert resp.status_code == 200, resp.text
    assert "pending" in resp.json()


@pytest.mark.asyncio
async def test_graph_analytics_endpoint(client):
    _, tokens = await create_authenticated_user(
        client, email="hard3@example.com", username="hard3")
    h = auth_headers(tokens["access_token"])
    resp = await client.get("/v1/platform/graph/analytics", headers=h)
    assert resp.status_code == 200, resp.text
    assert "nodes" in resp.json()
