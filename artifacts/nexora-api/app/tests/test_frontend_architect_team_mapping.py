from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_frontend_architect_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-fa@example.com", username="mapproductfa"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS


async def test_frontend_team_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-frontend-team@example.com", username="mapfrontendteam"
    )
    team = await create_team(client, tokens["access_token"], team_type="FRONTEND")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == ["frontend_architect", "frontend_v1", "frontend_v2", "frontend_v3", "frontend_code_review", "frontend_execution", "fullstack_assembly"]
