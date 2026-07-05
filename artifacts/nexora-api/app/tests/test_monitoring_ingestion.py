"""Tests for Sprint 58A.3 — Monitoring Ingestion Engine.

Live provider reads are mocked at the ``poll_provider`` boundary (no network).
Asserts: collect_alerts returns real alerts (never [] when the provider has
alerts), the alert→dedup→correlate→auto-incident→dashboard pipeline runs from
the polled path, webhook ingestion works, failures are dead-lettered, and
ingestion metrics are reported. Webhook parsers run for real (pure functions).
"""

from app.services import monitoring as mon
from app.services.monitoring_ingestion import (
    IngestError,
    NormalizedAlert,
    parse_alertmanager,
    parse_datadog,
    parse_github,
    parse_jenkins,
    parse_pagerduty,
    provider_supports_ingestion,
)
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _cred(client, token, provider, secret, name="c"):
    return await client.post("/v1/credentials", headers=H(token),
                             json={"provider": provider, "name": name, "secret": secret})


def _na(provider, name, *, severity="CRITICAL", service="checkout", resource="i-1",
        region="us-east-1", status="FIRING"):
    return NormalizedAlert(
        provider=provider, alert_id=f"{provider}-{name}", alert_name=name, severity=severity,
        status=status, service=service, environment="production", resource=resource,
        region=region, labels={"team": "core"}, annotations={"summary": "boom"},
        description=f"{name} firing",
    )


def _patch_pollers(monkeypatch, mapping):
    async def _fake(provider, secret):
        val = mapping.get(provider.upper(), [])
        if isinstance(val, Exception):
            raise val
        return val
    monkeypatch.setattr(mon, "poll_provider", _fake)


# ============================== unit ==================================== #
def test_provider_supports_ingestion():
    for p in ("AWS", "AZURE", "PROMETHEUS", "ALERTMANAGER", "KUBERNETES", "GITHUB", "GITLAB", "JENKINS"):
        assert provider_supports_ingestion(p)
    assert not provider_supports_ingestion("SLACK")


def test_alertmanager_parser_normalizes():
    payload = {"alerts": [{
        "fingerprint": "abc", "status": "firing",
        "labels": {"alertname": "HighCPU", "severity": "critical", "service": "api",
                   "namespace": "prod", "instance": "10.0.0.1"},
        "annotations": {"summary": "cpu high"}, "startsAt": "2026-06-27T10:00:00Z",
    }]}
    alerts = parse_alertmanager(payload)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.alert_name == "HighCPU" and a.severity == "critical"
    assert a.service == "api" and a.resource == "10.0.0.1"
    assert a.correlation_id  # auto-computed


def test_github_parser_ignores_success():
    assert parse_github({"workflow_run": {"conclusion": "success"}}) == []
    out = parse_github({
        "workflow_run": {"id": 5, "name": "CI", "conclusion": "failure",
                         "head_branch": "main", "html_url": "u", "updated_at": "2026-06-27T10:00:00Z"},
        "repository": {"full_name": "acme/app"}})
    assert len(out) == 1 and out[0].severity == "HIGH" and out[0].service == "acme/app"


def test_jenkins_parser_ignores_success():
    assert parse_jenkins({"build": {"status": "SUCCESS", "number": 1}}) == []
    out = parse_jenkins({
        "name": "smoke-job",
        "build": {"number": 42, "status": "FAILURE", "url": "http://jenkins/job/smoke-job/42/"},
    })
    assert len(out) == 1
    a = out[0]
    assert a.provider == "JENKINS" and a.severity == "HIGH"
    assert a.alert_id == "smoke-job#42"
    assert a.labels["job"] == "smoke-job"
    assert a.annotations["url"] == "http://jenkins/job/smoke-job/42/"


def test_datadog_parser_normalizes():
    payload = {
        "id": "dd-1", "title": "High CPU", "alert_type": "error",
        "body": "CPU > 90%", "tags": ["env:prod", "service:api"], "date": "2026-06-27T10:00:00Z",
    }
    alerts = parse_datadog(payload)
    assert len(alerts) == 1
    assert alerts[0].provider == "DATADOG" and alerts[0].status == "FIRING"
    assert alerts[0].labels.get("env") == "prod"


def test_pagerduty_parser_triggered():
    payload = {
        "messages": [{
            "event": "incident.triggered",
            "incident": {
                "id": "PD-9", "title": "DB down", "urgency": "high",
                "service": {"summary": "postgres"}, "created_at": "2026-06-27T10:00:00Z",
            },
        }],
    }
    alerts = parse_pagerduty(payload)
    assert len(alerts) == 1 and alerts[0].severity == "CRITICAL" and alerts[0].status == "FIRING"


def test_pagerduty_parser_resolved():
    payload = {
        "event": "incident.resolved",
        "incident": {"id": "PD-9", "title": "DB down", "urgency": "high", "created_at": "2026-06-27T10:00:00Z"},
    }
    alerts = parse_pagerduty(payload)
    assert len(alerts) == 1 and alerts[0].status == "RESOLVED"


# ============================== collect (polled) ======================== #
async def test_collect_alerts_returns_real_alerts_and_creates_incident(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi1@e.com", username="mi1")
    token = t["access_token"]
    await _cred(client, token, "AWS", {"access_key": "a", "secret_key": "s", "region": "us-east-1"})
    _patch_pollers(monkeypatch, {"AWS": [_na("AWS", "CPUAlarm", severity="CRITICAL")]})

    # No provided alerts -> collect_alerts must run for real (mocked poller).
    resp = await client.post("/v1/monitoring/poll", headers=H(token), json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alerts_ingested"] == 1            # collect_alerts did NOT return []
    assert body["new_alerts"] == 1
    assert body["incidents_created"] == 1
    assert body["polled_providers"] == ["AWS"]
    a = body["alerts"][0]
    assert a["provider"] == "AWS" and a["resource"] == "i-1" and a["region"] == "us-east-1"
    assert a["labels"] == {"team": "core"} and a["correlation_id"]
    # metrics surfaced
    assert body["metrics"]["alerts_received"] == 1
    assert body["metrics"]["alerts_processed"] == 1
    assert body["metrics"]["failures"] == 0


async def test_jenkins_failed_build_poll_creates_incident(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi-jenkins@e.com", username="mij")
    token = t["access_token"]
    await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={"integration_key": "JENKINS", "credentials": {
            "endpoint": "http://jenkins", "username": "u", "api_token": "t",
        }},
    )
    _patch_pollers(monkeypatch, {"JENKINS": [NormalizedAlert(
        provider="JENKINS", alert_id="smoke-job#42", alert_name="build-failed:smoke-job",
        severity="HIGH", status="FIRING", service="smoke-job",
        labels={"job": "smoke-job", "result": "FAILURE"},
        annotations={"url": "http://jenkins/job/smoke-job/42/"},
        description="Jenkins build #42 failed on smoke-job",
    ).with_correlation()]})
    body = (await client.post("/v1/monitoring/poll", headers=H(token), json={})).json()
    assert body["alerts_ingested"] == 1
    assert body["incidents_created"] == 1
    assert body["polled_providers"] == ["JENKINS"]
    assert body["alerts"][0]["incident_id"]


async def test_collect_multiple_providers_aggregate(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi2@e.com", username="mi2")
    token = t["access_token"]
    await _cred(client, token, "AWS", {"access_key": "a", "secret_key": "s", "region": "us-east-1"}, name="aws")
    await _cred(client, token, "PROMETHEUS", {"endpoint": "http://p"}, name="prom")
    _patch_pollers(monkeypatch, {
        "AWS": [_na("AWS", "CPUAlarm", service="api")],
        "PROMETHEUS": [_na("PROMETHEUS", "HighErrorRate", service="checkout")],
    })
    body = (await client.post("/v1/monitoring/poll", headers=H(token), json={})).json()
    assert body["alerts_ingested"] == 2
    assert set(body["polled_providers"]) == {"AWS", "PROMETHEUS"}
    assert body["metrics"]["alerts_received"] == 2


async def test_failed_provider_is_dead_lettered(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi3@e.com", username="mi3")
    token = t["access_token"]
    await _cred(client, token, "PROMETHEUS", {"endpoint": "http://p"})
    _patch_pollers(monkeypatch, {"PROMETHEUS": IngestError("Prometheus unreachable.")})
    body = (await client.post("/v1/monitoring/poll", headers=H(token), json={})).json()
    assert body["alerts_ingested"] == 0
    assert body["metrics"]["failures"] == 1
    # dead-letter recorded + surfaced
    dl = (await client.get("/v1/monitoring/dead-letters", headers=H(token))).json()
    assert len(dl) == 1 and dl[0]["provider"] == "PROMETHEUS" and dl[0]["source"] == "POLL"
    dash = (await client.get("/v1/monitoring/dashboard", headers=H(token))).json()
    assert dash["dead_letters"] >= 1


async def test_collect_truly_empty_returns_no_alerts(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi4@e.com", username="mi4")
    token = t["access_token"]
    await _cred(client, token, "AWS", {"access_key": "a", "secret_key": "s", "region": "us-east-1"})
    _patch_pollers(monkeypatch, {"AWS": []})  # provider genuinely has zero alerts
    body = (await client.post("/v1/monitoring/poll", headers=H(token), json={})).json()
    assert body["alerts_ingested"] == 0
    assert body["metrics"]["failures"] == 0
    assert (await client.get("/v1/monitoring/dead-letters", headers=H(token))).json() == []


# ============================== webhook ================================= #
async def test_webhook_ingestion_creates_incident(client):
    _, t = await create_authenticated_user(client, email="mi5@e.com", username="mi5")
    token = t["access_token"]
    payload = {"alerts": [{
        "fingerprint": "fp1", "status": "firing",
        "labels": {"alertname": "DiskFull", "severity": "critical", "service": "db",
                   "namespace": "prod", "instance": "node-1"},
        "annotations": {"summary": "disk full"}, "startsAt": "2026-06-27T10:00:00Z"}]}
    resp = await client.post("/v1/monitoring/ingest", headers=H(token),
                             json={"provider": "ALERTMANAGER", "payload": payload})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alerts_ingested"] == 1
    assert body["incidents_created"] == 1
    assert body["polled_providers"] == ["ALERTMANAGER"]
    assert body["alerts"][0]["alert_name"] == "DiskFull"


async def test_datadog_webhook_ingestion(client):
    _, t = await create_authenticated_user(client, email="mi5b@e.com", username="mi5b")
    token = t["access_token"]
    payload = {"id": "dd-2", "title": "Latency spike", "alert_type": "error",
               "body": "p99 high", "date": "2026-06-27T10:00:00Z"}
    resp = await client.post("/v1/monitoring/ingest", headers=H(token),
                             json={"provider": "DATADOG", "payload": payload})
    assert resp.status_code == 200, resp.text
    assert resp.json()["alerts_ingested"] == 1


async def test_jenkins_webhook_ingestion_creates_incident(client):
    _, t = await create_authenticated_user(client, email="mi-jw@e.com", username="mijw")
    token = t["access_token"]
    payload = {
        "name": "deploy-job",
        "build": {"number": 7, "status": "FAILURE", "url": "http://jenkins/job/deploy-job/7/"},
    }
    resp = await client.post("/v1/monitoring/ingest", headers=H(token),
                             json={"provider": "JENKINS", "payload": payload})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alerts_ingested"] == 1
    assert body["incidents_created"] == 1
    assert body["alerts"][0]["provider"] == "JENKINS"


async def test_alert_manual_investigate_creates_incident(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi-inv@e.com", username="miinv")
    token = t["access_token"]
    await _cred(client, token, "PROMETHEUS", {"endpoint": "http://p"})
    _patch_pollers(monkeypatch, {"PROMETHEUS": [_na("PROMETHEUS", "HighLatency", severity="WARNING")]})
    poll = (await client.post("/v1/monitoring/poll", headers=H(token), json={})).json()
    assert poll["incidents_created"] == 0
    alert_id = poll["alerts"][0]["id"]
    inv = await client.post(f"/v1/monitoring/alerts/{alert_id}/investigate", headers=H(token), json={})
    assert inv.status_code == 200, inv.text
    body = inv.json()
    assert body["created"] is True
    assert body["incident_id"]


async def test_webhook_bad_payload_is_dead_lettered(client):
    _, t = await create_authenticated_user(client, email="mi6@e.com", username="mi6")
    token = t["access_token"]
    resp = await client.post("/v1/monitoring/ingest", headers=H(token),
                             json={"provider": "UNKNOWN_PROVIDER", "payload": {"x": 1}})
    assert resp.status_code == 422
    dl = (await client.get("/v1/monitoring/dead-letters", headers=H(token))).json()
    assert len(dl) == 1 and dl[0]["source"] == "WEBHOOK"


# ============================== isolation + auth ======================== #
async def test_webhook_requires_auth(client):
    resp = await client.post("/v1/monitoring/ingest",
                             json={"provider": "ALERTMANAGER", "payload": {"alerts": []}})
    assert resp.status_code in (401, 403)


async def test_dead_letters_tenant_isolated(client, monkeypatch):
    _, ta = await create_authenticated_user(client, email="miA@e.com", username="miA")
    _, tb = await create_authenticated_user(client, email="miB@e.com", username="miB")
    toka, tokb = ta["access_token"], tb["access_token"]
    await _cred(client, toka, "PROMETHEUS", {"endpoint": "http://p"})
    _patch_pollers(monkeypatch, {"PROMETHEUS": IngestError("down")})
    await client.post("/v1/monitoring/poll", headers=H(toka), json={})
    assert (await client.get("/v1/monitoring/dead-letters", headers=H(tokb))).json() == []


# ============================== no secret leak ========================== #
async def test_ingestion_never_leaks_secret(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="mi7@e.com", username="mi7")
    token = t["access_token"]
    await _cred(client, token, "PROMETHEUS", {"endpoint": "http://p", "token": "TOP-SECRET-INGEST"})
    _patch_pollers(monkeypatch, {"PROMETHEUS": [_na("PROMETHEUS", "HighLatency", severity="WARNING")]})
    resp = await client.post("/v1/monitoring/poll", headers=H(token), json={})
    assert "TOP-SECRET-INGEST" not in resp.text
    dl = await client.get("/v1/monitoring/dead-letters", headers=H(token))
    assert "TOP-SECRET-INGEST" not in dl.text
