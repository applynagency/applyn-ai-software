from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
)


async def test_list_team_templates(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-list@example.com", username="tpllist"
    )
    response = await client.get(
        "/v1/team-templates", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    slugs = {item["slug"] for item in data["items"]}
    assert "crm-delivery" in slugs
    assert "healthcare-delivery" in slugs
    assert "financial-services" in slugs
    assert "ecommerce-delivery" in slugs


async def test_apply_crm_template(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-apply@example.com", username="tplapply"
    )
    response = await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "crm-delivery"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["teams_created"] == 6
    assert len(data["items"]) == 6
    assert any(team["team_type"] == "FRONTEND" for team in data["items"])
    assert all(team["agent_mappings"] for team in data["items"] if team["team_type"] != "CUSTOM")


async def test_apply_healthcare_template(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-health@example.com", username="tplhealth"
    )
    response = await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "healthcare-delivery"},
    )
    assert response.status_code == 201
    types = {team["team_type"] for team in response.json()["items"]}
    assert "COMPLIANCE" in types


async def test_apply_financial_template(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-fin@example.com", username="tplfin"
    )
    response = await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "financial-services"},
    )
    assert response.status_code == 201
    types = {team["team_type"] for team in response.json()["items"]}
    assert "SECURITY" in types
    assert "COMPLIANCE" in types


async def test_apply_ecommerce_template(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-ecom@example.com", username="tplecom"
    )
    response = await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "ecommerce-delivery"},
    )
    assert response.status_code == 201
    assert response.json()["teams_created"] == 6


async def test_apply_unknown_template(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-unknown@example.com", username="tplunknown"
    )
    response = await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "does-not-exist"},
    )
    assert response.status_code == 404


async def test_template_teams_have_responsibilities(client):
    _, tokens = await create_authenticated_user(
        client, email="tpl-resp@example.com", username="tplresp"
    )
    response = await client.post(
        "/v1/team-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "ecommerce-delivery"},
    )
    assert all(team["responsibilities"] for team in response.json()["items"])
