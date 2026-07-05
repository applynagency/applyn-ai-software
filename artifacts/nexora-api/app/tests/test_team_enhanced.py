from app.tests.conftest import auth_headers, create_authenticated_user, create_team


async def test_team_response_includes_metrics(client):
    _, tokens = await create_authenticated_user(
        client, email="metrics@example.com", username="metricsuser"
    )
    team = await create_team(client, tokens["access_token"], team_type="FRONTEND")
    await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Metric task", "priority": "MEDIUM"},
    )
    response = await client.get(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    data = response.json()
    assert data["responsibility_count"] == 1
    assert data["agent_count"] == 7
    assert data["workflow_count"] == 0


async def test_create_team_defaults_to_draft(client):
    _, tokens = await create_authenticated_user(
        client, email="draft@example.com", username="draftuser"
    )
    team = await create_team(client, tokens["access_token"], name="Draft Team")
    assert team["status"] == "DRAFT"


async def test_template_definition_json_available(client):
    _, tokens = await create_authenticated_user(
        client, email="json-template@example.com", username="jsontemplate"
    )
    response = await client.get(
        "/v1/team-templates/crm-delivery",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    definition = response.json()["definition"]
    assert definition["slug"] == "crm-delivery"
    assert len(definition["teams"]) == 6


async def test_template_list_include_definition(client):
    _, tokens = await create_authenticated_user(
        client, email="json-list@example.com", username="jsonlist"
    )
    response = await client.get(
        "/v1/team-templates?include_definition=true",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["definition"] is not None
