from app.tests.conftest import auth_headers, create_authenticated_user


async def test_list_ai_agent_templates(client):
    _, tokens = await create_authenticated_user(
        client, email="at-list@example.com", username="atlist"
    )
    response = await client.get(
        "/v1/ai-agent-templates", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 7
    slugs = {item["slug"] for item in data["items"]}
    assert "security-review-agent" in slugs
    assert "cloud-cost-optimization-agent" in slugs


async def test_get_ai_agent_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-get@example.com", username="atget"
    )
    response = await client.get(
        "/v1/ai-agent-templates/security-review-agent",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Security Review Agent"
    assert data["agent"]["input_count"] >= 2


async def test_apply_security_review_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-sec@example.com", username="atsec"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "security-review-agent"},
    )
    assert response.status_code == 201
    agent = response.json()["agent"]
    assert agent["name"] == "Security Review Agent"
    assert len(agent["inputs"]) >= 2
    assert len(agent["outputs"]) >= 2
    assert len(agent["responsibilities"]) >= 1


async def test_apply_healthcare_compliance_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-health@example.com", username="athealth"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "healthcare-compliance-agent"},
    )
    assert response.status_code == 201
    assert "Healthcare" in response.json()["agent"]["name"]


async def test_apply_fintech_risk_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-fintech@example.com", username="atfintech"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "fintech-risk-agent"},
    )
    assert response.status_code == 201
    assert response.json()["agent"]["goal"]


async def test_apply_architecture_review_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-arch@example.com", username="atarch"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "architecture-review-agent"},
    )
    assert response.status_code == 201
    assert response.json()["agent"]["prompt_template"]


async def test_apply_performance_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-perf@example.com", username="atperf"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "performance-optimization-agent"},
    )
    assert response.status_code == 201


async def test_apply_documentation_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-docs@example.com", username="atdocs"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "documentation-agent"},
    )
    assert response.status_code == 201


async def test_apply_cloud_cost_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-cloud@example.com", username="atcloud"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "cloud-cost-optimization-agent"},
    )
    assert response.status_code == 201


async def test_apply_unknown_agent_template(client):
    _, tokens = await create_authenticated_user(
        client, email="at-unknown@example.com", username="atunknown"
    )
    response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "missing-agent"},
    )
    assert response.status_code == 404
