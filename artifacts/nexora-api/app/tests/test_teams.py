from app.tests.conftest import auth_headers, create_authenticated_user, create_team


async def test_create_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-create@example.com", username="teamcreate"
    )
    team = await create_team(client, tokens["access_token"], name="Backend Team", team_type="BACKEND")
    assert team["name"] == "Backend Team"
    assert team["team_type"] == "BACKEND"
    assert team["organization_id"]


async def test_list_teams(client):
    _, tokens = await create_authenticated_user(
        client, email="team-list@example.com", username="teamlist"
    )
    await create_team(client, tokens["access_token"], name="QA Team", team_type="QA")
    response = await client.get("/v1/teams", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-get@example.com", username="teamget"
    )
    team = await create_team(client, tokens["access_token"], name="Product Team", team_type="PRODUCT")
    response = await client.get(
        f"/v1/teams/{team['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == team["id"]


async def test_update_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-update@example.com", username="teamupdate"
    )
    team = await create_team(client, tokens["access_token"], name="Old Team", team_type="CUSTOM")
    response = await client.put(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Updated Team", "status": "INACTIVE"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Team"
    assert response.json()["status"] == "INACTIVE"


async def test_delete_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-delete@example.com", username="teamdelete"
    )
    team = await create_team(client, tokens["access_token"], name="Delete Team")
    response = await client.delete(
        f"/v1/teams/{team['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 204


async def test_duplicate_team(client):
    _, tokens = await create_authenticated_user(
        client, email="team-dup@example.com", username="teamdup"
    )
    team = await create_team(client, tokens["access_token"], name="Source Team", team_type="FRONTEND")
    await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Build components", "priority": "HIGH"},
    )
    response = await client.post(
        f"/v1/teams/{team['id']}/duplicate",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    duplicate = response.json()["team"]
    assert duplicate["name"] == "Source Team (Copy)"
    assert len(duplicate["responsibilities"]) == 1
    assert len(duplicate["agent_mappings"]) >= 1


async def test_list_teams_filter_by_type(client):
    _, tokens = await create_authenticated_user(
        client, email="team-filter@example.com", username="teamfilter"
    )
    await create_team(client, tokens["access_token"], name="FE", team_type="FRONTEND")
    await create_team(client, tokens["access_token"], name="BE", team_type="BACKEND")
    response = await client.get(
        "/v1/teams?team_type=FRONTEND",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["team_type"] == "FRONTEND" for item in response.json()["items"])


async def test_get_team_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="team-missing@example.com", username="teammissing"
    )
    response = await client.get(
        "/v1/teams/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
