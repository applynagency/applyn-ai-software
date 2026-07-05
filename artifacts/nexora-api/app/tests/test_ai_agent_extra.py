from app.ai_agents.templates import AI_AGENT_TEMPLATES, get_template_by_slug
from app.tests.conftest import auth_headers, create_ai_agent, create_authenticated_user


async def test_all_template_slugs_loadable():
    assert len(AI_AGENT_TEMPLATES) == 7
    for template in AI_AGENT_TEMPLATES:
        assert get_template_by_slug(template.slug) is not None


async def test_create_agent_with_prompt_template(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-prompt@example.com", username="agentprompt"
    )
    response = await client.post(
        "/v1/ai-agents",
        headers=auth_headers(tokens["access_token"]),
        json={
            "name": "Prompt Agent",
            "prompt_template": "You are a helpful assistant.",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 201
    assert response.json()["prompt_template"] == "You are a helpful assistant."


async def test_agent_inactive_status(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-inactive@example.com", username="agentinactive"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.put(
        f"/v1/ai-agents/{agent['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"status": "INACTIVE"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"


async def test_viewer_can_read_agent_templates(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="at-viewer-owner@example.com", username="atviewerowner"
    )
    from app.tests.conftest import create_organization, login_user, switch_organization

    viewer, _ = await create_authenticated_user(
        client, email="at-viewer@example.com", username="atviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="AT Viewer Org", slug="at-viewer-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get(
        "/v1/ai-agent-templates", headers=auth_headers(viewer_tokens["access_token"])
    )
    assert response.status_code == 200


async def test_viewer_cannot_apply_agent_template(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="at-viewer-block-owner@example.com", username="atviewerblockowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="at-viewer-block@example.com", username="atviewerblock"
    )
    from app.tests.conftest import create_organization, login_user, switch_organization

    organization = await create_organization(
        client, owner_tokens["access_token"], name="AT Block Org", slug="at-block-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(viewer_tokens["access_token"]),
        json={"template_slug": "documentation-agent"},
    )
    assert response.status_code == 403


async def test_agent_detail_includes_nested_components(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-nested@example.com", username="agentnested"
    )
    apply = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "documentation-agent"},
    )
    agent_id = apply.json()["agent"]["id"]
    response = await client.get(
        f"/v1/ai-agents/{agent_id}", headers=auth_headers(tokens["access_token"])
    )
    data = response.json()
    assert len(data["inputs"]) >= 2
    assert len(data["outputs"]) >= 2
    assert len(data["responsibilities"]) >= 1
