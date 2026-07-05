from app.models.team import TeamType
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS, TeamMappingService
from app.tests.conftest import (
    EXPECTED_DEVOPS_TEAM_AGENTS,
    EXPECTED_PRODUCT_TEAM_AGENTS,
    create_authenticated_user,
    create_team,
)

NEW_DEVOPS_AGENTS = ["kubernetes_agent", "observability_agent", "sre_approval_agent"]


def test_devops_team_has_all_six_agents():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.DEVOPS]
    assert agents == [
        "infrastructure_architect",
        "docker_agent",
        "cicd_agent",
        "kubernetes_agent",
        "observability_agent",
        "sre_approval_agent",
    ]


def test_product_team_includes_new_devops_agents():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.PRODUCT]
    for agent in NEW_DEVOPS_AGENTS:
        assert agent in agents


def test_product_team_devops_order():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.PRODUCT]
    assert agents.index("cicd_agent") < agents.index("kubernetes_agent")
    assert agents.index("kubernetes_agent") < agents.index("observability_agent")
    assert agents.index("observability_agent") < agents.index("sre_approval_agent")
    assert agents.index("sre_approval_agent") < agents.index("fullstack_assembly")


def test_product_team_qa_before_devops():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.PRODUCT]
    assert agents.index("qa_approval") < agents.index("kubernetes_agent")


def test_mapping_service_devops_specs_ordered():
    specs = TeamMappingService.mapping_specs_for_team_type(TeamType.DEVOPS)
    names = [s.internal_agent for s in specs]
    assert names == EXPECTED_DEVOPS_TEAM_AGENTS
    orders = [s.execution_order for s in specs]
    assert orders == sorted(orders)


async def test_product_team_mapping_via_api(client):
    _, tokens = await create_authenticated_user(client, email="map-prod-devops@example.com", username="mapproddev")
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS
    for agent in NEW_DEVOPS_AGENTS:
        assert agent in agents


async def test_devops_team_mapping_via_api(client):
    _, tokens = await create_authenticated_user(client, email="map-devops-ops@example.com", username="mapdevops")
    team = await create_team(client, tokens["access_token"], team_type="DEVOPS")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_DEVOPS_TEAM_AGENTS
