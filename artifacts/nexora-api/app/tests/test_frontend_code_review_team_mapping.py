from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_frontend_code_review_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-fcr@example.com", username="mapproductfcr"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert agents.index("frontend_v3") < agents.index("frontend_code_review")
    assert agents.index("frontend_code_review") < agents.index("frontend_execution")
    assert agents.index("frontend_execution") < agents.index("fullstack_assembly")


async def test_frontend_team_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-frontend-fcr@example.com", username="mapfrontendfcr"
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
