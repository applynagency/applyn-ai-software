"""Tests for integration live-data sync and capabilities enrichment."""

import pytest

from app.services.integration_capabilities import enrichment_for, supports_pipeline_sync
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers

JENKINS_CREDS = {"endpoint": "https://jenkins.example.com", "username": "bot", "api_token": "tok"}


def test_enrichment_for_jenkins():
    e = enrichment_for("JENKINS")
    assert e["pipeline_sync"] is True
    assert e["live_data"] is True
    assert "Delivery" in " ".join(e["unlocks_live"])


def test_supports_pipeline_sync():
    assert supports_pipeline_sync("JENKINS")
    assert supports_pipeline_sync("circleci")
    assert not supports_pipeline_sync("SLACK")


@pytest.mark.asyncio
async def test_sync_endpoint_requires_pipeline_integration(client):
    _, t = await create_authenticated_user(client, email="sync1@e.com", username="sync1")
    token = t["access_token"]
    conn = (await client.post(
        "/v1/integrations/connect", headers=H(token),
        json={"integration_key": "SLACK", "credentials": {"bot_token": "xoxb-1"}},
    )).json()
    r = await client.post(f"/v1/integrations/connections/{conn['id']}/sync", headers=H(token))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_sync_jenkins_pipelines(client, monkeypatch):
    from app.delivery.pipelines.base import PipelineInfo, PipelineRunInfo

    _, t = await create_authenticated_user(client, email="sync2@e.com", username="sync2")
    token = t["access_token"]
    conn = (await client.post(
        "/v1/integrations/connect", headers=H(token),
        json={"integration_key": "JENKINS", "credentials": JENKINS_CREDS},
    )).json()

    fake_pipes = [PipelineInfo(external_id="build", name="build", repository="jenkins", provider="JENKINS")]
    fake_runs = [PipelineRunInfo(
        external_id="1", pipeline_name="build", status="SUCCEEDED", conclusion="success",
        branch="main", commit_sha="abc", started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z", duration_seconds=60,
        url="https://jenkins.example.com/job/build/1", logs_preview="ok",
    )]

    class FakeProvider:
        provider = "JENKINS"

        def list_pipelines(self, secret, *, repository=None):
            return fake_pipes

        def list_runs(self, secret, pipeline, *, repository=None, limit=20):
            return fake_runs

    monkeypatch.setattr(
        "app.services.integration_sync.get_pipeline_provider",
        lambda _t: FakeProvider(),
    )

    r = await client.post(f"/v1/integrations/connections/{conn['id']}/sync", headers=H(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pipelines_synced"] == 1
    assert body["runs_synced"] == 1
    assert body["integration_key"] == "JENKINS"
    assert body["synced_at"]


@pytest.mark.asyncio
async def test_marketplace_catalog_includes_enrichment(client):
    _, t = await create_authenticated_user(client, email="sync3@e.com", username="sync3")
    token = t["access_token"]
    mp = (await client.get("/v1/integrations", headers=H(token))).json()
    jenkins = next(i for i in mp["integrations"] if i["integration_key"] == "JENKINS")
    assert jenkins["enrichment"]["pipeline_sync"] is True
    assert mp["summary"]["live_capable"] >= 1
