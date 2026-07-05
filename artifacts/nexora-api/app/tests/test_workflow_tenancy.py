from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_workflow,
    switch_organization,
)


async def test_workflow_isolation_between_organizations(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="wf-iso-a@example.com", username="wfisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="wf-iso-b@example.com", username="wfisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Org A Workflows", slug="org-a-wf"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Org B Workflows", slug="org-b-wf"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    workflow_a = await create_workflow(client, tokens_a_org["access_token"], name="Org A Workflow")

    response = await client.get(
        f"/v1/workflows/{workflow_a['id']}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_stage_isolation_between_organizations(client):
    owner_a, tokens_a = await create_authenticated_user(
        client, email="stage-iso-a@example.com", username="stageisoa"
    )
    owner_b, tokens_b = await create_authenticated_user(
        client, email="stage-iso-b@example.com", username="stageisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Stage Org A", slug="stage-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Stage Org B", slug="stage-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    workflow = await create_workflow(client, tokens_a_org["access_token"])
    stage_response = await client.post(
        f"/v1/workflows/{workflow['id']}/stages",
        headers=auth_headers(tokens_a_org["access_token"]),
        json={"name": "Planning", "sequence": 1, "stage_type": "PLANNING"},
    )
    stage_id = stage_response.json()["id"]

    response = await client.put(
        f"/v1/stages/{stage_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
        json={"name": "Blocked"},
    )
    assert response.status_code == 404


async def test_list_workflows_scoped_to_active_org(client):
    user, tokens = await create_authenticated_user(
        client, email="wf-scope@example.com", username="wfscope"
    )
    org_one = await create_organization(
        client, tokens["access_token"], name="Scope One", slug="scope-one"
    )
    org_two = await create_organization(
        client, tokens["access_token"], name="Scope Two", slug="scope-two"
    )
    tokens_one = await switch_organization(client, tokens["access_token"], org_one["id"])
    await create_workflow(client, tokens_one["access_token"], name="Workflow One")
    tokens_two = await switch_organization(client, tokens["access_token"], org_two["id"])
    await create_workflow(client, tokens_two["access_token"], name="Workflow Two")
    await create_workflow(client, tokens_two["access_token"], name="Workflow Two B")

    list_two = await client.get("/v1/workflows", headers=auth_headers(tokens_two["access_token"]))
    assert list_two.status_code == 200
    assert list_two.json()["total"] == 2

    list_one = await client.get("/v1/workflows", headers=auth_headers(tokens_one["access_token"]))
    assert list_one.status_code == 200
    assert list_one.json()["total"] == 1
