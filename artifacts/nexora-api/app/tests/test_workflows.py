from app.tests.conftest import auth_headers, create_authenticated_user, create_workflow


async def test_create_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-create@example.com", username="wfcreate"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="CRM Flow")
    assert workflow["name"] == "CRM Flow"
    assert workflow["status"] == "DRAFT"
    assert workflow["organization_id"]


async def test_list_workflows(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-list@example.com", username="wflist"
    )
    await create_workflow(client, tokens["access_token"], name="Listed Workflow")
    response = await client.get("/v1/workflows", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-get@example.com", username="wfget"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.get(
        f"/v1/workflows/{workflow['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == workflow["id"]


async def test_update_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-update@example.com", username="wfupdate"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="Old Name")
    response = await client.put(
        f"/v1/workflows/{workflow['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "New Name", "status": "ACTIVE"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["status"] == "ACTIVE"


async def test_delete_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-delete@example.com", username="wfdelete"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.delete(
        f"/v1/workflows/{workflow['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 204


async def test_archive_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-archive@example.com", username="wfarchive"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.post(
        f"/v1/workflows/{workflow['id']}/archive",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"


async def test_duplicate_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-dup@example.com", username="wfdup"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="Source Workflow")
    await client.post(
        f"/v1/workflows/{workflow['id']}/stages",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Planning", "sequence": 1, "stage_type": "PLANNING"},
    )
    response = await client.post(
        f"/v1/workflows/{workflow['id']}/duplicate",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    duplicate = response.json()["workflow"]
    assert duplicate["name"] == "Source Workflow (Copy)"
    assert duplicate["status"] == "DRAFT"
    assert len(duplicate["stages"]) == 1


async def test_workflow_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-missing@example.com", username="wfmissing"
    )
    response = await client.get(
        "/v1/workflows/nonexistent-id", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 404


async def test_list_workflows_filter_by_status(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-filter@example.com", username="wffilter"
    )
    await create_workflow(client, tokens["access_token"], name="Draft One", status="DRAFT")
    await create_workflow(client, tokens["access_token"], name="Active One", status="ACTIVE")
    response = await client.get(
        "/v1/workflows?status=ACTIVE",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["status"] == "ACTIVE" for item in response.json()["items"])
