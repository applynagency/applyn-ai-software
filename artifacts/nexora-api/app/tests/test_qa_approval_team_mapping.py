from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_qa_approval_mapping(client):
    _, tokens = await create_authenticated_user(client, email="map-product-qa_approval@example.com", username="mapqa_appropr")
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert "qa_approval" in agents


async def test_qa_team_includes_qa_approval_mapping(client):
    _, tokens = await create_authenticated_user(client, email="map-qa-qa_approval@example.com", username="mapqa_approqa")
    team = await create_team(client, tokens["access_token"], team_type="QA")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert "qa_approval" in agents
