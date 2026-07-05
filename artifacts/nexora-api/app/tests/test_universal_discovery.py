"""Tests for Sprint 58A.2.1 — Universal Discovery Framework.

Provider adapters (real cloud/API reads) are mocked at the
``run_universal_provider`` boundary so the engine's behaviour is asserted
deterministically without a network: every connected integration contributes
assets across its domains, the Universal Resource Model is populated, the
Platform Knowledge Graph is built (incl. cross-provider relationships),
discovery events are emitted, the pipeline continues after a provider fails,
deleted-resource detection is safe, tenants are isolated, the AI can consume the
result, and the scheduler tick works.
"""

import pytest

from app.database.session import AsyncSessionLocal
from app.services import universal_discovery as ud
from app.services.universal_discovery_adapters import (
    UniversalAdapterError,
    UniversalResource,
    node_key,
    supports_universal_discovery,
)
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers

CREDS = {
    "AWS": {"access_key": "AKIA...", "secret_key": "shh", "region": "us-east-1"},
    "GITHUB": {"token": "ghp_secrettoken"},
    "GITLAB": {"token": "glpat_secrettoken"},
    "JIRA": {"base_url": "https://acme.atlassian.net", "email": "a@e.com", "api_token": "jiratok"},
    "SLACK": {"bot_token": "xoxb-secret"},
    "MICROSOFT_TEAMS": {"tenant_id": "t1", "client_id": "c1", "client_secret": "shh"},
    "PROMETHEUS": {"endpoint": "https://prom.example.com"},
}


async def _connect(client, token, key):
    return await client.post("/v1/integrations/connect", headers=H(token),
                             json={"integration_key": key, "credentials": CREDS[key]})


def _ur(provider, domain, rtype, rid, name, *, display_name=None, owner=None,
        account=None, region=None, environment=None, health="HEALTHY", status=None,
        tags=None, rels=None, metadata=None):
    return UniversalResource(
        provider=provider, domain=domain, resource_type=rtype, resource_id=rid,
        resource_name=name, display_name=display_name, owner=owner, account=account,
        region=region, environment=environment, health=health, status=status,
        tags=tags or {}, relationships=rels or [], metadata=metadata or {},
    )


def _patch(monkeypatch, mapping):
    """mapping: provider -> list[UniversalResource] | Exception."""
    async def _fake(integration_key, secret):
        val = mapping.get(integration_key, [])
        if isinstance(val, Exception):
            raise val
        return val
    monkeypatch.setattr(ud, "run_universal_provider", _fake)


# ============================== adapter unit ============================= #
def test_supports_universal_discovery():
    for key in ("AWS", "AZURE", "KUBERNETES", "GITHUB", "GITLAB", "JIRA", "SLACK",
                "MICROSOFT_TEAMS"):
        assert supports_universal_discovery(key), key
    assert not supports_universal_discovery("PROMETHEUS")
    assert not supports_universal_discovery("NOPE")


async def test_run_universal_provider_unknown_raises():
    from app.services.universal_discovery_adapters import run_universal_provider

    with pytest.raises(UniversalAdapterError):
        await run_universal_provider("NOPE", {})


# ============================ every provider/domain ====================== #
async def test_all_providers_all_domains(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u1@e.com", username="udisc1")
    token = t["access_token"]
    for key in ("AWS", "GITHUB", "GITLAB", "JIRA", "SLACK", "MICROSOFT_TEAMS"):
        await _connect(client, token, key)

    _patch(monkeypatch, {
        "AWS": [
            _ur("AWS", "INFRASTRUCTURE", "RDS", "arn:rds:orders", "orders-db",
                display_name="orders-db", account="111", region="us-east-1"),
            _ur("AWS", "INFRASTRUCTURE", "EC2", "i-1", "i-1", account="111", region="us-east-1"),
        ],
        "GITHUB": [
            _ur("GITHUB", "REPOSITORY", "ORGANIZATION", "acme", "acme"),
            _ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/orders", display_name="orders",
                owner="acme"),
            _ur("GITHUB", "DEPLOYMENT", "DEPLOYMENT", "d1", "acme/orders#1", owner="acme",
                environment="prod",
                rels=[{"target_key": node_key("GITHUB", "REPOSITORY", "REPOSITORY", "r1"),
                       "type": "DEPLOYS"}]),
        ],
        "GITLAB": [
            _ur("GITLAB", "REPOSITORY", "PROJECT", "100", "team/api", display_name="api"),
            _ur("GITLAB", "DEPLOYMENT", "PIPELINE", "100/pipe/9", "pipeline-9", status="success"),
        ],
        "JIRA": [
            _ur("JIRA", "BUSINESS", "PROJECT", "OPS", "Operations", display_name="Operations"),
            _ur("JIRA", "BUSINESS", "COMPONENT", "5", "orders", display_name="orders"),
        ],
        "SLACK": [
            _ur("SLACK", "COLLABORATION", "WORKSPACE", "T1", "acme"),
            _ur("SLACK", "COLLABORATION", "CHANNEL", "C1", "orders", display_name="orders"),
            _ur("SLACK", "COLLABORATION", "INCIDENT_CHANNEL", "C2", "incidents"),
        ],
        "MICROSOFT_TEAMS": [
            _ur("MICROSOFT_TEAMS", "COLLABORATION", "TENANT", "t1", "Acme"),
            _ur("MICROSOFT_TEAMS", "COLLABORATION", "CHANNEL", "ch1", "General"),
        ],
    })

    r = await client.post("/v1/discovery/sync", headers=H(token), json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scan"]["status"] == "COMPLETED"
    assert body["scan"]["resources_found"] == 14
    assert set(body["scan"]["providers"]) == {"AWS", "GITHUB", "GITLAB", "JIRA", "SLACK",
                                              "MICROSOFT_TEAMS"}
    # no secret ever surfaced
    assert "shh" not in r.text and "ghp_secrettoken" not in r.text

    # every domain present in the summary
    summary = body["summary"]
    domains = {d["domain"] for d in summary["domains"]}
    assert {"INFRASTRUCTURE", "REPOSITORY", "DEPLOYMENT", "BUSINESS", "COLLABORATION"} <= domains
    assert summary["total_assets"] == 14
    assert summary["node_count"] == 14
    assert summary["edge_count"] >= 1

    # every connected provider listed in the status panel (no provider hidden)
    statuses = {p["provider"]: p for p in summary["providers"]}
    assert set(statuses) >= {"AWS", "GITHUB", "GITLAB", "JIRA", "SLACK", "MICROSOFT_TEAMS"}
    assert statuses["GITHUB"]["domains"] == ["REPOSITORY", "DEPLOYMENT"]

    # all 13 are RESOURCE_ADDED on the first scan; deployment events emitted too
    events = body["events"]
    added = [e for e in events if e["event_type"] == "RESOURCE_ADDED"]
    assert len(added) == 14
    assert any(e["event_type"] == "DEPLOYMENT_CHANGED" for e in events)

    # assets endpoint, filtered by domain
    repos = (await client.get("/v1/discovery/assets?domain=REPOSITORY",
                              headers=H(token))).json()
    assert any(a["resource_type"] == "REPOSITORY" for a in repos)
    coll = (await client.get("/v1/discovery/assets?provider=SLACK",
                             headers=H(token))).json()
    assert {a["resource_type"] for a in coll} >= {"CHANNEL", "INCIDENT_CHANNEL", "WORKSPACE"}


# ============================ cross-provider graph ======================= #
async def test_cross_provider_relationships(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u2@e.com", username="udisc2")
    token = t["access_token"]
    for key in ("AWS", "GITHUB", "SLACK"):
        await _connect(client, token, key)
    _patch(monkeypatch, {
        "AWS": [_ur("AWS", "INFRASTRUCTURE", "RDS", "arn:rds:orders", "orders-db",
                    display_name="orders")],
        "GITHUB": [_ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/orders",
                       display_name="orders", owner="acme")],
        "SLACK": [_ur("SLACK", "COLLABORATION", "CHANNEL", "C1", "orders", display_name="orders")],
    })
    await client.post("/v1/discovery/sync", headers=H(token), json={})

    graph = (await client.get("/v1/discovery/graph", headers=H(token))).json()
    assert graph["node_count"] == 3
    rel_edges = [e for e in graph["edges"] if e["relationship_type"] == "RELATES_TO"]
    # the three "orders" assets from different providers are linked together
    keyed = {(e["source_key"].split(":")[0], e["target_key"].split(":")[0]) for e in rel_edges}
    providers_linked = {p for pair in keyed for p in pair}
    assert {"AWS", "GITHUB", "SLACK"} <= providers_linked

    # AI context can consume them
    ctx = (await client.get("/v1/discovery/context?subject=orders",
                            headers=H(token))).json()
    assert any(r["resource_type"] == "REPOSITORY" for r in ctx["repositories"])
    assert ctx["slack_channels"]
    assert ctx["matched_assets"]


# ============================ explicit relationship ===================== #
async def test_explicit_relationship_edges(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u3@e.com", username="udisc3")
    token = t["access_token"]
    await _connect(client, token, "AWS")
    _patch(monkeypatch, {"AWS": [
        _ur("AWS", "INFRASTRUCTURE", "RDS", "arn:rds:orders", "orders-db", display_name="orders-db"),
        _ur("AWS", "INFRASTRUCTURE", "ALB", "arn:alb:web", "web-lb", display_name="web-lb",
            rels=[{"target_name": "orders-db", "type": "DATASTORE"}]),
    ]})
    await client.post("/v1/discovery/sync", headers=H(token), json={})
    graph = (await client.get("/v1/discovery/graph", headers=H(token))).json()
    assert any(e["relationship_type"] == "DATASTORE" for e in graph["edges"])


# ============================ diff add/update/remove ===================== #
async def test_diff_added_updated_removed(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u4@e.com", username="udisc4")
    token = t["access_token"]
    await _connect(client, token, "GITHUB")
    _patch(monkeypatch, {"GITHUB": [
        _ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/a", display_name="a", owner="team1"),
        _ur("GITHUB", "REPOSITORY", "REPOSITORY", "r2", "acme/b", display_name="b", owner="team1"),
    ]})
    first = (await client.post("/v1/discovery/sync", headers=H(token), json={})).json()
    assert first["scan"]["added_count"] == 2

    # r1 owner change (UPDATE + OWNERSHIP_CHANGED), r2 removed, r3 added
    _patch(monkeypatch, {"GITHUB": [
        _ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/a", display_name="a", owner="team2"),
        _ur("GITHUB", "REPOSITORY", "REPOSITORY", "r3", "acme/c", display_name="c", owner="team1"),
    ]})
    second = (await client.post("/v1/discovery/sync", headers=H(token), json={})).json()
    assert second["scan"]["added_count"] == 1
    assert second["scan"]["removed_count"] == 1
    assert second["scan"]["modified_count"] == 1
    types = {(e["event_type"], e["resource_name"]) for e in second["events"]}
    assert ("RESOURCE_ADDED", "acme/c") in types
    assert ("RESOURCE_REMOVED", "acme/b") in types
    assert ("RESOURCE_UPDATED", "acme/a") in types
    assert any(e["event_type"] == "OWNERSHIP_CHANGED" for e in second["events"])


# ============================ continue after failure ==================== #
async def test_pipeline_continues_after_provider_failure(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u5@e.com", username="udisc5")
    token = t["access_token"]
    await _connect(client, token, "GITHUB")
    await _connect(client, token, "SLACK")
    _patch(monkeypatch, {
        "GITHUB": [_ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/a", display_name="a")],
        "SLACK": [_ur("SLACK", "COLLABORATION", "CHANNEL", "C1", "general")],
    })
    first = (await client.post("/v1/discovery/sync", headers=H(token), json={})).json()
    assert first["scan"]["added_count"] == 2

    # GitHub fails this run; Slack unchanged -> GitHub asset NOT reported removed
    _patch(monkeypatch, {
        "GITHUB": UniversalAdapterError("GitHub rejected the supplied token."),
        "SLACK": [_ur("SLACK", "COLLABORATION", "CHANNEL", "C1", "general")],
    })
    second = (await client.post("/v1/discovery/sync", headers=H(token), json={})).json()
    assert second["scan"]["status"] == "PARTIAL"
    assert second["scan"]["removed_count"] == 0
    assert any("GITHUB" in w for w in second["scan"]["warnings"])
    # GitHub asset still present (failure is not a deletion)
    assets = (await client.get("/v1/discovery/assets?provider=GITHUB",
                               headers=H(token))).json()
    assert any(a["resource_name"] == "acme/a" for a in assets)


# ============================ tenant isolation ========================== #
async def test_tenant_isolation(client, monkeypatch):
    _, t1 = await create_authenticated_user(client, email="uA@e.com", username="udiscA")
    _, t2 = await create_authenticated_user(client, email="uB@e.com", username="udiscB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _connect(client, tok1, "GITHUB")
    _patch(monkeypatch, {"GITHUB": [_ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/a")]})
    await client.post("/v1/discovery/sync", headers=H(tok1), json={})

    other_summary = (await client.get("/v1/discovery/summary", headers=H(tok2))).json()
    assert other_summary["total_assets"] == 0
    assert (await client.get("/v1/discovery/assets", headers=H(tok2))).json() == []
    assert (await client.get("/v1/discovery/graph", headers=H(tok2))).json()["node_count"] == 0
    assert (await client.get("/v1/discovery/events", headers=H(tok2))).json() == []


# ============================ skipped providers shown =================== #
async def test_unsupported_provider_not_hidden(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u6@e.com", username="udisc6")
    token = t["access_token"]
    await _connect(client, token, "GITHUB")
    await _connect(client, token, "PROMETHEUS")  # connected but no discovery adapter
    _patch(monkeypatch, {"GITHUB": [_ur("GITHUB", "REPOSITORY", "REPOSITORY", "r1", "acme/a")]})
    await client.post("/v1/discovery/sync", headers=H(token), json={})
    summary = (await client.get("/v1/discovery/summary", headers=H(token))).json()
    statuses = {p["provider"]: p for p in summary["providers"]}
    assert "PROMETHEUS" in statuses
    assert statuses["PROMETHEUS"]["supported"] is False
    assert statuses["PROMETHEUS"]["note"]


# ============================ scheduler ================================= #
async def test_scheduler_run_once(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="u7@e.com", username="udisc7")
    token = t["access_token"]
    await _connect(client, token, "JIRA")
    _patch(monkeypatch, {"JIRA": [_ur("JIRA", "BUSINESS", "PROJECT", "OPS", "Operations")]})
    async with AsyncSessionLocal() as session:
        ran = await ud.UniversalDiscoveryRunner().run_once(session)
    assert ran == 1
    summary = (await client.get("/v1/discovery/summary", headers=H(token))).json()
    assert summary["total_assets"] == 1
    assert summary["latest_scan"]["trigger"] == "SCHEDULED"
