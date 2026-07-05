from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_approval,
    setup_qa_approval_pipeline,
    switch_organization,
)


async def test_cannot_read_qa_approval_run_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="qa_approval-iso-a@example.com", username="qa_approisoa")
    _, tokens_b = await create_authenticated_user(client, email="qa_approval-iso-b@example.com", username="qa_approisob")
    org_a = await create_organization(client, tokens_a["access_token"], name="QaApproval Org A", slug="qa_approval-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="QaApproval Org B", slug="qa_approval-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="qa_approval-iso-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="qa_approval-iso-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/qa-approvals/runs/{run_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404


async def test_cannot_read_qa_approval_artifact_from_other_org(client):
    _, tokens_a = await create_authenticated_user(client, email="qa_approval-art-a@example.com", username="qa_approarta")
    _, tokens_b = await create_authenticated_user(client, email="qa_approval-art-b@example.com", username="qa_approartb")
    org_a = await create_organization(client, tokens_a["access_token"], name="QaApproval Art Org A", slug="qa_approval-art-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="QaApproval Art Org B", slug="qa_approval-art-org-b")
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="qa_approval-art-ws")
    project = await create_project(client, tokens_a_org["access_token"], workspace_id=workspace["id"], slug="qa_approval-art-proj")
    requirement = await create_requirement(client, tokens_a_org["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(f"/v1/agents/qa-approvals/artifacts/{artifact_id}", headers=auth_headers(tokens_b_org["access_token"]))
    assert response.status_code == 404
