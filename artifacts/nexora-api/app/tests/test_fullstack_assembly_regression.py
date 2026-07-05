from app.models.fullstack_assembly import FullstackAssemblyRunStatus
from app.models.team import TeamType
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS, TeamMappingService
from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS
from app.tests.route_helpers import collect_route_paths


def test_fullstack_assembly_run_status_values():
    assert FullstackAssemblyRunStatus.PENDING.value == "PENDING"
    assert FullstackAssemblyRunStatus.RUNNING.value == "RUNNING"
    assert FullstackAssemblyRunStatus.COMPLETED.value == "COMPLETED"
    assert FullstackAssemblyRunStatus.FAILED.value == "FAILED"


def test_fullstack_assembly_models_importable():
    from app.models.fullstack_assembly import FullstackAssemblyArtifact, FullstackAssemblyRun

    assert FullstackAssemblyRun.__tablename__ == "fullstack_assembly_runs"
    assert FullstackAssemblyArtifact.__tablename__ == "fullstack_assembly_artifacts"


def test_fullstack_assembly_service_importable():
    from app.services.fullstack_assembly import FullStackAssemblyService

    assert FullStackAssemblyService.__name__ == "FullStackAssemblyService"


def test_fullstack_assembly_agent_importable():
    from app.agents.fullstack_assembly import FullStackAssemblyAgent

    assert FullStackAssemblyAgent.__name__ == "FullStackAssemblyAgent"


def test_fullstack_assembly_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/fullstack-assembly" in path for path in paths)


def test_frontend_team_has_seven_agents():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.FRONTEND]
    assert len(agents) == 7
    assert agents[-1] == "fullstack_assembly"


def test_product_team_ends_with_deployment():
    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert agents[-1] == "deployment"
    assert len(agents) == len(EXPECTED_PRODUCT_TEAM_AGENTS)


def test_deployment_team_includes_fullstack_assembly_first():
    agents = TeamMappingService.agents_for_team_type(TeamType.DEPLOYMENT)
    assert agents[0] == "fullstack_assembly"
