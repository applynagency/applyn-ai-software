from app.tests.conftest import auth_headers, create_authenticated_user, create_workflow


async def test_workflow_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-audit-create@example.com", username="wfauditcreate"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="Audited Workflow")
    response = await client.get(
        f"/v1/workflows/{workflow['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert "workflow_created" in actions


async def test_workflow_updated_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-audit-update@example.com", username="wfauditupdate"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    await client.put(
        f"/v1/workflows/{workflow['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Updated Audited"},
    )
    response = await client.get(
        f"/v1/workflows/{workflow['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    actions = {item["action"] for item in response.json()["items"]}
    assert "workflow_updated" in actions


async def test_stage_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-audit-stage@example.com", username="wfauditstage"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    await client.post(
        f"/v1/workflows/{workflow['id']}/stages",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Planning", "sequence": 1, "stage_type": "PLANNING"},
    )
    response = await client.get(
        f"/v1/workflows/{workflow['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    actions = {item["action"] for item in response.json()["items"]}
    assert "stage_created" in actions


async def test_workflow_duplicated_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-audit-dup@example.com", username="wfauditdup"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    dup = await client.post(
        f"/v1/workflows/{workflow['id']}/duplicate",
        headers=auth_headers(tokens["access_token"]),
    )
    duplicate_id = dup.json()["workflow"]["id"]
    response = await client.get(
        f"/v1/workflows/{duplicate_id}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    actions = {item["action"] for item in response.json()["items"]}
    assert "workflow_duplicated" in actions


async def test_template_applied_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="wf-audit-template@example.com", username="wfaudittemplate"
    )
    apply_response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "crm-workflow"},
    )
    workflow_id = apply_response.json()["workflow"]["id"]
    response = await client.get(
        f"/v1/workflows/{workflow_id}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    actions = {item["action"] for item in response.json()["items"]}
    assert "workflow_template_applied" in actions
