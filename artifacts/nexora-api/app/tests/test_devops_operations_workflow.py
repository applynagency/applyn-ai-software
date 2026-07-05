from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_cicd_agent,
    run_kubernetes_agent,
    run_observability_agent,
    run_sre_approval,
    setup_cicd_agent_pipeline,
    setup_kubernetes_pipeline,
    setup_observability_pipeline,
)


async def _bootstrap(client, slug):
    _, tokens = await create_authenticated_user(client, email=f"{slug}@example.com", username=slug.replace("-", "")[:18])
    workspace = await create_workspace(client, tokens["access_token"], slug=f"{slug}-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug=f"{slug}-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    return tokens["access_token"], requirement["id"]


async def test_full_devops_operations_chain_runs(client):
    token, req_id = await _bootstrap(client, "devops-chain")
    await setup_cicd_agent_pipeline(client, token, req_id)
    cicd = await run_cicd_agent(client, token, req_id)
    assert cicd.status_code == 201
    k8s = await run_kubernetes_agent(client, token, req_id)
    assert k8s.status_code == 201
    obs = await run_observability_agent(client, token, req_id)
    assert obs.status_code == 201
    sre = await run_sre_approval(client, token, req_id)
    assert sre.status_code == 201
    assert sre.json()["artifact"]["artifact_json"]["sre_status"].startswith("SRE_")


async def test_observability_requires_kubernetes(client):
    token, req_id = await _bootstrap(client, "obs-needs-k8s")
    await setup_cicd_agent_pipeline(client, token, req_id)
    await run_cicd_agent(client, token, req_id)
    # Kubernetes has not run yet.
    response = await run_observability_agent(client, token, req_id)
    assert response.status_code == 422


async def test_sre_requires_observability(client):
    token, req_id = await _bootstrap(client, "sre-needs-obs")
    await setup_kubernetes_pipeline(client, token, req_id)
    await run_kubernetes_agent(client, token, req_id)
    # Observability has not run yet.
    response = await run_sre_approval(client, token, req_id)
    assert response.status_code == 422


async def test_sre_runs_after_observability(client):
    token, req_id = await _bootstrap(client, "sre-after-obs")
    await setup_observability_pipeline(client, token, req_id)
    await run_observability_agent(client, token, req_id)
    response = await run_sre_approval(client, token, req_id)
    assert response.status_code == 201


async def test_kubernetes_requires_cicd(client):
    token, req_id = await _bootstrap(client, "k8s-needs-cicd")
    # No CI/CD run yet.
    response = await run_kubernetes_agent(client, token, req_id)
    assert response.status_code == 422
