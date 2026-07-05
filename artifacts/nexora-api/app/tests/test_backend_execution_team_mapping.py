from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_backend_execution_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-be@example.com", username="mapproductbe"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert agents.index("backend_code_review") < agents.index("backend_execution")
    assert agents.index("backend_execution") < agents.index("uiux_designer")


async def test_backend_team_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-backend-be@example.com", username="mapbackendbe"
    )
    team = await create_team(client, tokens["access_token"], team_type="BACKEND")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == [
        "backend_architect",
        "backend_v1",
        "backend_v2",
        "backend_v3",
        "backend_code_review",
        "backend_execution",
    ]


async def test_frontend_team_does_not_include_backend_execution(client):
    _, tokens = await create_authenticated_user(
        client, email="map-frontend-be@example.com", username="mapfrontendbe"
    )
    team = await create_team(client, tokens["access_token"], team_type="FRONTEND")
    agents = [m["internal_agent"] for m in team["agent_mappings"]]
    assert "backend_execution" not in agents
