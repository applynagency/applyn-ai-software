from app.tests.conftest import (
    EXPECTED_PRODUCT_TEAM_AGENTS,
    PRODUCT_DEPLOYMENT_ORDER,
    create_authenticated_user,
    create_team,
)


async def test_product_team_includes_deployment_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-dep@example.com", username="mapproductdep"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert agents.index("approval") < agents.index("deployment")
    assert len(agents) == len(EXPECTED_PRODUCT_TEAM_AGENTS)


async def test_frontend_team_still_ends_with_fullstack_assembly(client):
    _, tokens = await create_authenticated_user(
        client, email="map-frontend-dep@example.com", username="mapfrontenddep"
    )
    team = await create_team(client, tokens["access_token"], team_type="FRONTEND")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == [
        "frontend_architect",
        "frontend_v1",
        "frontend_v2",
        "frontend_v3",
        "frontend_code_review",
        "frontend_execution",
        "fullstack_assembly",
    ]
    assert "deployment" not in agents
    assert len(agents) == 7


async def test_deployment_team_includes_deployment(client):
    _, tokens = await create_authenticated_user(
        client, email="map-deploy-dep@example.com", username="mapdeploydep"
    )
    team = await create_team(client, tokens["access_token"], team_type="DEPLOYMENT")
    agents = {m["internal_agent"] for m in team["agent_mappings"]}
    assert agents == {"fullstack_assembly", "approval", "deployment"}


async def test_product_team_deployment_at_order_12(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-dep-order@example.com", username="mapproductdeporder"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    deployment_mapping = next(
        m for m in team["agent_mappings"] if m["internal_agent"] == "deployment"
    )
    assert deployment_mapping["execution_order"] == PRODUCT_DEPLOYMENT_ORDER
