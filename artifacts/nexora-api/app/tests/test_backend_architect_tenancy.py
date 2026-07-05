from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    run_backend_architect,
    setup_backend_architect_pipeline,
    switch_organization,
)


async def test_cannot_read_backend_architect_run_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="ba-arch-iso-a@example.com", username="baarchisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="ba-arch-iso-b@example.com", username="baarchisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="BA Arch Org A", slug="ba-arch-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="BA Arch Org B", slug="ba-arch-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    ctx = await setup_backend_architect_pipeline(client, tokens_a_org["access_token"])
    created = await run_backend_architect(
        client, tokens_a_org["access_token"], ctx["requirement"]["id"]
    )
    run_id = created.json()["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-architect/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_cannot_read_backend_architect_artifact_from_other_org(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="ba-arch-art-iso-a@example.com", username="baarchartisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="ba-arch-art-iso-b@example.com", username="baarchartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="BA Arch Art Org A", slug="ba-arch-art-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="BA Arch Art Org B", slug="ba-arch-art-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    ctx = await setup_backend_architect_pipeline(client, tokens_a_org["access_token"])
    created = await run_backend_architect(
        client, tokens_a_org["access_token"], ctx["requirement"]["id"]
    )
    artifact_id = created.json()["artifact"]["id"]
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    response = await client.get(
        f"/v1/agents/backend-architect/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_runs_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-list-scope@example.com", username="baarchlistscope"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    await run_backend_architect(client, tokens["access_token"], ctx["requirement"]["id"])
    response = await client.get(
        f"/v1/agents/backend-architect/{ctx['requirement']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["requirement_id"] == ctx["requirement"]["id"] for item in response.json()["items"])
