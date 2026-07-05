from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_backend_v2_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-bv2@example.com", username="mapproductbv2"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS


async def test_backend_team_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-backend-bv2@example.com", username="mapbackendbv2"
    )
    team = await create_team(client, tokens["access_token"], team_type="BACKEND")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == ["backend_architect", "backend_v1", "backend_v2", "backend_v3", "backend_code_review", "backend_execution"]


async def test_backend_v2_follows_backend_v1_in_product_team(client):
    _, tokens = await create_authenticated_user(
        client, email="map-bv2-order@example.com", username="mapbv2order"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    mappings = sorted(team["agent_mappings"], key=lambda x: x["execution_order"])
    agents = [m["internal_agent"] for m in mappings]
    assert agents.index("backend_v1") + 1 == agents.index("backend_v2")


async def test_backend_v2_precedes_uiux_designer_in_product_team(client):
    _, tokens = await create_authenticated_user(
        client, email="map-bv2-uiux@example.com", username="mapbv2uiux"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents.index("backend_v2") < agents.index("uiux_designer")
