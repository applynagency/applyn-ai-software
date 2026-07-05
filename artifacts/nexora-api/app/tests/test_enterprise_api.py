"""API tests for enterprise enrichment summary and scoped mutations."""

from unittest.mock import AsyncMock, patch

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


@pytest.mark.asyncio
async def test_enterprise_summary_empty_org(client):
    _, t = await create_authenticated_user(client, email="ent1@e.com", username="ent1")
    token = t["access_token"]
    r = await client.get("/v1/integrations/enterprise/summary", headers=H(token))
    assert r.status_code == 200
    body = r.json()
    assert body["providers"] == []


@pytest.mark.asyncio
async def test_enterprise_summary_filters_enterprise_keys(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="ent2@e.com", username="ent2")
    token = t["access_token"]
    await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={"integration_key": "SLACK", "credentials": {"bot_token": "xoxb-test"}},
    )
    sn = (await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={
            "integration_key": "SERVICENOW",
            "credentials": {"instance_url": "https://sn.example", "username": "u", "password": "p"},
        },
    )).json()

    async def _fake_resolve(*_args, **_kwargs):
        return None, {"instance_url": "https://sn.example", "username": "u", "password": "p"}

    with patch(
        "app.api.v1.integration.SecretManagerService.resolve_secret",
        new_callable=AsyncMock,
        side_effect=_fake_resolve,
    ):
        with patch(
            "app.api.v1.integration.summarize_provider",
            return_value={
                "integration_key": "SERVICENOW",
                "available": True,
                "open_incidents": 2,
                "cmdb_services": 5,
            },
        ):
            r = await client.get("/v1/integrations/enterprise/summary", headers=H(token))

    assert r.status_code == 200
    providers = r.json()["providers"]
    assert len(providers) == 1
    assert providers[0]["connection_id"] == sn["id"]
    assert providers[0]["integration_key"] == "SERVICENOW"
    assert providers[0]["open_incidents"] == 2


@pytest.mark.asyncio
async def test_enterprise_mutate_unsupported_action(client):
    _, t = await create_authenticated_user(client, email="ent3@e.com", username="ent3")
    token = t["access_token"]
    conn = (await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={"integration_key": "SPLUNK", "credentials": {"endpoint": "https://spl.example", "token": "tok"}},
    )).json()

    r = await client.post(
        f"/v1/integrations/connections/{conn['id']}/mutate",
        headers=H(token),
        json={"action": "bad", "resource_id": "x"},
    )

    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert "unsupported_action" in r.json()["reason"]


@pytest.mark.asyncio
async def test_enterprise_mutate_blocked_without_simulation(client):
    _, t = await create_authenticated_user(client, email="ent3b@e.com", username="ent3b")
    token = t["access_token"]
    conn = (await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={"integration_key": "SPLUNK", "credentials": {"endpoint": "https://spl.example", "token": "tok"}},
    )).json()

    r = await client.post(
        f"/v1/integrations/connections/{conn['id']}/mutate",
        headers=H(token),
        json={"action": "trigger_search", "resource_id": "my-search"},
    )

    assert r.status_code == 400
    body = r.json()
    assert "integration_readiness" in (body.get("details") or body.get("detail") or str(body))


@pytest.mark.asyncio
async def test_enterprise_mutate_explicit_simulation(client):
    _, t = await create_authenticated_user(client, email="ent3c@e.com", username="ent3c")
    token = t["access_token"]
    conn = (await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={"integration_key": "SPLUNK", "credentials": {"endpoint": "https://spl.example", "token": "tok"}},
    )).json()

    r = await client.post(
        f"/v1/integrations/connections/{conn['id']}/mutate",
        headers=H(token),
        json={"action": "trigger_search", "resource_id": "my-search", "explicit_simulation": True},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "simulated"
    assert body.get("simulated") is True


@pytest.mark.asyncio
async def test_enterprise_mutate_requires_write(client):
    from sqlalchemy import select

    from app.models.organization import OrganizationMember, OrganizationRole
    from app.models.user import User
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ent4@e.com", username="ent4",
    )
    conn = (await client.post(
        "/v1/integrations/connect",
        headers=H(tokens["access_token"]),
        json={"integration_key": "SENTRY", "credentials": {"endpoint": "https://sentry.io", "token": "tok"}},
    )).json()

    async with AsyncSessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.email == "ent4@e.com"),
        )).scalar_one()
        members = (
            await session.execute(
                select(OrganizationMember).where(OrganizationMember.user_id == user.id),
            )
        ).scalars().all()
        for member in members:
            member.role = OrganizationRole.VIEWER
            session.add(member)
        await session.commit()

    r = await client.post(
        f"/v1/integrations/connections/{conn['id']}/mutate",
        headers=H(tokens["access_token"]),
        json={"action": "resolve_issue", "resource_id": "123"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_enterprise_summary_includes_pagerduty(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="ent5@e.com", username="ent5")
    token = t["access_token"]
    pd = (await client.post(
        "/v1/integrations/connect",
        headers=H(token),
        json={"integration_key": "PAGERDUTY", "credentials": {"api_key": "pd-test-key"}},
    )).json()

    async def _fake_resolve(*_args, **_kwargs):
        return None, {"api_key": "pd-test-key"}

    with patch(
        "app.api.v1.integration.SecretManagerService.resolve_secret",
        new_callable=AsyncMock,
        side_effect=_fake_resolve,
    ):
        with patch(
            "app.api.v1.integration.summarize_provider",
            return_value={
                "integration_key": "PAGERDUTY",
                "available": True,
                "open_incidents": 3,
            },
        ):
            r = await client.get("/v1/integrations/enterprise/summary", headers=H(token))

    assert r.status_code == 200
    providers = r.json()["providers"]
    assert len(providers) == 1
    assert providers[0]["connection_id"] == pd["id"]
    assert providers[0]["integration_key"] == "PAGERDUTY"
