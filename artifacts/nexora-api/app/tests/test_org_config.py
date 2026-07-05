"""Organization configuration variables API tests."""

from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization

API = "/v1/org-config/variables"


async def _org_admin(client):
    user, tokens = await create_authenticated_user(
        client, email="orgcfg@e.com", username="orgcfg", password="Pass123!",
    )
    org = await create_organization(client, tokens["access_token"], name="OrgCfg", slug="orgcfg")
    switched = await switch_organization(client, tokens["access_token"], org["id"])
    return auth_headers(switched["access_token"]), org["id"]


async def test_org_variables_crud(client):
    headers, _ = await _org_admin(client)
    created = await client.post(
        API,
        headers=headers,
        json={"key": "LOG_LEVEL", "value": "info", "environment": "default", "is_secret": False},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["key"] == "LOG_LEVEL"
    assert body["is_secret"] is False
    assert body["value_preview"] == "info"
    var_id = body["id"]

    listed = await client.get(API, headers=headers)
    assert listed.status_code == 200
    assert any(v["id"] == var_id for v in listed.json())

    updated = await client.put(
        f"{API}/{var_id}",
        headers=headers,
        json={"value": "debug", "description": "runtime log level"},
    )
    assert updated.status_code == 200
    assert updated.json()["value_preview"] == "debug"
    assert updated.json()["description"] == "runtime log level"

    deleted = await client.delete(f"{API}/{var_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get(API, headers=headers)).json() == []


async def test_org_secret_variable_masked(client):
    headers, _ = await _org_admin(client)
    created = await client.post(
        API,
        headers=headers,
        json={"key": "API_TOKEN", "value": "super-secret-token", "environment": "staging", "is_secret": True},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["is_secret"] is True
    assert body["value_preview"] == "••••••"
    assert "super-secret-token" not in created.text


async def test_org_variable_duplicate_rejected(client):
    headers, _ = await _org_admin(client)
    payload = {"key": "DUP_KEY", "value": "a", "environment": "default"}
    assert (await client.post(API, headers=headers, json=payload)).status_code == 201
    dup = await client.post(API, headers=headers, json=payload)
    assert dup.status_code == 422
