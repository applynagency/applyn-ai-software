from app.tests.conftest import (
    EXPECTED_PRODUCT_TEAM_AGENTS,
    EXPECTED_QA_TEAM_AGENTS,
    create_authenticated_user,
    create_team,
)


async def test_product_team_includes_unit_test_generator_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-ut@example.com", username="mapproductut"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert "unit_test_generator" in agents


async def test_qa_team_contains_unit_test_generator(client):
    _, tokens = await create_authenticated_user(
        client, email="map-qa-ut@example.com", username="mapqaut"
    )
    team = await create_team(client, tokens["access_token"], team_type="QA")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_QA_TEAM_AGENTS
