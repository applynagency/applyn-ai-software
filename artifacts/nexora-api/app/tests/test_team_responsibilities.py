from app.tests.conftest import auth_headers, create_authenticated_user, create_team


async def test_create_responsibility(client):
    _, tokens = await create_authenticated_user(
        client, email="resp-create@example.com", username="respcreate"
    )
    team = await create_team(client, tokens["access_token"])
    response = await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={
            "title": "Implement UI",
            "description": "Build dashboard components",
            "priority": "HIGH",
        },
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Implement UI"


async def test_update_responsibility(client):
    _, tokens = await create_authenticated_user(
        client, email="resp-update@example.com", username="respupdate"
    )
    team = await create_team(client, tokens["access_token"])
    created = await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Old title", "priority": "LOW"},
    )
    responsibility_id = created.json()["id"]
    response = await client.put(
        f"/v1/responsibilities/{responsibility_id}",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "New title", "priority": "CRITICAL"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New title"
    assert response.json()["priority"] == "CRITICAL"


async def test_delete_responsibility(client):
    _, tokens = await create_authenticated_user(
        client, email="resp-delete@example.com", username="respdelete"
    )
    team = await create_team(client, tokens["access_token"])
    created = await client.post(
        f"/v1/teams/{team['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Temporary", "priority": "MEDIUM"},
    )
    response = await client.delete(
        f"/v1/responsibilities/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204
