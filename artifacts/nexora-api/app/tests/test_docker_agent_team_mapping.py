from app.tests.conftest import (
    EXPECTED_DEVOPS_TEAM_AGENTS,
    EXPECTED_PRODUCT_TEAM_AGENTS,
    create_authenticated_user,
    create_team,
)


async def test_product_team_includes_docker_agent_mapping(client):
    _, tokens = await create_authenticated_user(client, email="map-product-docker_agent@example.com", username="mapdocker")
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    assert "docker_agent" in agents


async def test_devops_team_includes_docker_agent_mapping(client):
    _, tokens = await create_authenticated_user(client, email="map-devops-docker_agent@example.com", username="mapdevdock")
    team = await create_team(client, tokens["access_token"], team_type="DEVOPS")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_DEVOPS_TEAM_AGENTS
