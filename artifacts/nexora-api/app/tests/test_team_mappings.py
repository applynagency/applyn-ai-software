from app.models.team import TeamType
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS, TeamMappingService
from app.tests.conftest import (
    EXPECTED_DEVOPS_TEAM_AGENTS,
    EXPECTED_PRODUCT_TEAM_AGENTS,
    auth_headers,
    create_authenticated_user,
    create_team,
)

PRODUCT_AGENT_COUNT = len(EXPECTED_PRODUCT_TEAM_AGENTS)


async def test_product_team_agent_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product@example.com", username="mapproduct"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    mappings = sorted(team["agent_mappings"], key=lambda item: item["execution_order"])
    assert mappings[-1]["internal_agent"] == "deployment"
    assert mappings[-1]["execution_order"] == PRODUCT_AGENT_COUNT
    assert len(mappings) == PRODUCT_AGENT_COUNT
    assert any(m["internal_agent"] == "qa_architect" for m in mappings)
    assert any(m["internal_agent"] == "unit_test_generator" for m in mappings)
    assert any(m["internal_agent"] == "integration_test" for m in mappings)
    assert any(m["internal_agent"] == "security_test" for m in mappings)
    assert any(m["internal_agent"] == "performance_test" for m in mappings)
    assert any(m["internal_agent"] == "qa_approval" for m in mappings)
    assert any(m["internal_agent"] == "infrastructure_architect" for m in mappings)
    assert any(m["internal_agent"] == "docker_agent" for m in mappings)
    assert any(m["internal_agent"] == "cicd_agent" for m in mappings)
    assert any(m["internal_agent"] == "kubernetes_agent" for m in mappings)
    assert any(m["internal_agent"] == "observability_agent" for m in mappings)
    assert any(m["internal_agent"] == "sre_approval_agent" for m in mappings)
    deployment_mapping = next(
        m for m in mappings if m["internal_agent"] == "deployment"
    )
    assert deployment_mapping["execution_order"] == PRODUCT_AGENT_COUNT


async def test_frontend_team_agent_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-fe@example.com", username="mapfe"
    )
    team = await create_team(client, tokens["access_token"], team_type="FRONTEND")
    mappings = sorted(team["agent_mappings"], key=lambda item: item["execution_order"])
    assert mappings[0]["internal_agent"] == "frontend_architect"
    assert mappings[0]["execution_order"] == 1
    assert mappings[0]["is_required"] is True
    assert mappings[-1]["internal_agent"] == "fullstack_assembly"
    assert mappings[-1]["execution_order"] == 7


async def test_backend_team_agent_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-be@example.com", username="mapbe"
    )
    team = await create_team(client, tokens["access_token"], team_type="BACKEND")
    agents = {mapping["internal_agent"] for mapping in team["agent_mappings"]}
    assert "backend_architect" in agents
    assert "backend_v3" in agents


async def test_qa_team_agent_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-qa@example.com", username="mapqa"
    )
    team = await create_team(client, tokens["access_token"], team_type="QA")
    agents = {mapping["internal_agent"] for mapping in team["agent_mappings"]}
    assert agents == {
        "qa_architect",
        "unit_test_generator",
        "integration_test",
        "security_test",
        "performance_test",
        "qa_approval",
    }


async def test_deployment_team_agent_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-deploy@example.com", username="mapdeploy"
    )
    team = await create_team(client, tokens["access_token"], team_type="DEPLOYMENT")
    agents = {mapping["internal_agent"] for mapping in team["agent_mappings"]}
    assert agents == {"fullstack_assembly", "approval", "deployment"}


async def test_devops_team_agent_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-devops@example.com", username="mapdevops"
    )
    team = await create_team(client, tokens["access_token"], team_type="DEVOPS")
    agents = {mapping["internal_agent"] for mapping in team["agent_mappings"]}
    assert agents == set(EXPECTED_DEVOPS_TEAM_AGENTS)
    assert agents == {
        "infrastructure_architect",
        "docker_agent",
        "cicd_agent",
        "kubernetes_agent",
        "observability_agent",
        "sre_approval_agent",
    }

async def test_custom_team_has_no_default_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-custom@example.com", username="mapcustom"
    )
    team = await create_team(client, tokens["access_token"], team_type="CUSTOM")
    assert team["agent_mappings"] == []


async def test_update_team_type_refreshes_mappings(client):
    _, tokens = await create_authenticated_user(
        client, email="map-update@example.com", username="mapupdate"
    )
    team = await create_team(client, tokens["access_token"], team_type="CUSTOM")
    response = await client.put(
        f"/v1/teams/{team['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"team_type": "QA"},
    )
    agents = {mapping["internal_agent"] for mapping in response.json()["agent_mappings"]}
    assert agents == {
        "qa_architect",
        "unit_test_generator",
        "integration_test",
        "security_test",
        "performance_test",
        "qa_approval",
    }


def test_mapping_service_catalog():
    service = TeamMappingService()
    assert service.agents_for_team_type(TeamType.FRONTEND) == TEAM_TYPE_AGENT_MAPPINGS[TeamType.FRONTEND]
    assert "product_owner" in service.agents_for_team_type(TeamType.PRODUCT)
    assert "business_analyst" in service.agents_for_team_type(TeamType.PRODUCT)
    backend = service.all_mappings()["BACKEND"]
    assert backend[0]["internal_agent"] == "backend_architect"
    assert backend[0]["execution_order"] == 1
