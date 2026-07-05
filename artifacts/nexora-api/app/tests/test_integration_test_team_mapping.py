from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_integration_test_mapping(client):
    _, tokens = await create_authenticated_user(client, email="map-product-integration_test@example.com", username="mapintegratpr")
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert "integration_test" in agents


async def test_qa_team_includes_integration_test_mapping(client):
    _, tokens = await create_authenticated_user(client, email="map-qa-integration_test@example.com", username="mapintegratqa")
    team = await create_team(client, tokens["access_token"], team_type="QA")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert "integration_test" in agents
