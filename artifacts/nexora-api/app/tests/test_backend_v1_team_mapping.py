from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_backend_v1_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-bv1@example.com", username="mapproductbv1"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS


async def test_backend_team_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-backend-bv1@example.com", username="mapbackendbv1"
    )
    team = await create_team(client, tokens["access_token"], team_type="BACKEND")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == ["backend_architect", "backend_v1", "backend_v2", "backend_v3", "backend_code_review", "backend_execution"]


async def test_backend_v1_follows_backend_architect_in_product_team(client):
    _, tokens = await create_authenticated_user(
        client, email="map-bv1-order@example.com", username="mapbv1order"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    mappings = sorted(team["agent_mappings"], key=lambda x: x["execution_order"])
    agents = [m["internal_agent"] for m in mappings]
    assert agents.index("backend_architect") + 1 == agents.index("backend_v1")
