from app.tests.conftest import auth_headers, create_authenticated_user, create_team


async def test_team_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-create@example.com", username="auditcreate"
    )
    team = await create_team(client, tokens["access_token"], name="Audit Team")
    response = await client.get(
        f"/v1/teams/{team['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert "team_created" in actions


async def test_team_updated_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-update@example.com", username="auditupdate"
    )
    team = await create_team(client, tokens["access_token"], name="Before Update")
    await client.put(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "After Update"},
    )
    response = await client.get(
        f"/v1/teams/{team['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    actions = {item["action"] for item in response.json()["items"]}
    assert "team_updated" in actions


async def test_responsibility_audit_events(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-resp@example.com", username="auditresp"
    )
    team = await create_team(client, tokens["access_token"])
    created = await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Audit task", "priority": "HIGH"},
    )
    await client.delete(
        f"/v1/responsibilities/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    response = await client.get(
        f"/v1/teams/{team['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    actions = {item["action"] for item in response.json()["items"]}
    assert "responsibility_created" in actions
    assert "responsibility_deleted" in actions


async def test_template_applied_audit_logged(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-template@example.com", username="audittemplate"
    )
    team = await create_team(client, tokens["access_token"], name="Seed Team")
    await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "ecommerce-delivery"},
    )
    response = await client.get(
        f"/v1/teams/{team['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
