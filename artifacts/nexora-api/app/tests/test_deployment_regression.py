from app.models.deployment import DeploymentStatus
from app.models.team import TeamType
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS, TeamMappingService
from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS
from app.tests.route_helpers import collect_route_paths


def test_deployment_run_status_values():
    assert DeploymentStatus.PENDING.value == "PENDING"
    assert DeploymentStatus.QUEUED.value == "QUEUED"
    assert DeploymentStatus.DEPLOYING.value == "DEPLOYING"
    assert DeploymentStatus.DEPLOYED.value == "DEPLOYED"
    assert DeploymentStatus.FAILED.value == "FAILED"
    assert DeploymentStatus.ROLLBACK_IN_PROGRESS.value == "ROLLBACK_IN_PROGRESS"
    assert DeploymentStatus.ROLLED_BACK.value == "ROLLED_BACK"


def test_deployment_models_importable():
    from app.models.deployment import DeploymentArtifact, DeploymentLog, DeploymentRun

    assert DeploymentRun.__tablename__ == "deployment_runs"
    assert DeploymentArtifact.__tablename__ == "deployment_artifacts"
    assert DeploymentLog.__tablename__ == "deployment_logs"


def test_deployment_service_importable():
    from app.services.deployment import DeploymentService

    assert DeploymentService.__name__ == "DeploymentService"


def test_deployment_agent_importable():
    from app.agents.deployment import DeploymentAgent

    assert DeploymentAgent.__name__ == "DeploymentAgent"


def test_deployment_agent_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/deployment" in path for path in paths)


def test_deployments_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/deployments" in path for path in paths)


def test_frontend_team_has_seven_agents():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.FRONTEND]
    assert len(agents) == 7
    assert agents[-1] == "fullstack_assembly"


def test_product_team_ends_with_deployment():
    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert agents[-1] == "deployment"
    assert len(agents) == len(EXPECTED_PRODUCT_TEAM_AGENTS)


def test_deployment_team_includes_approval_before_deployment():
    agents = TeamMappingService.agents_for_team_type(TeamType.DEPLOYMENT)
    assert agents == ["fullstack_assembly", "approval", "deployment"]


def test_deployment_deployer_importable():
    from app.deployment.deployer import DeploymentDeployer

    assert DeploymentDeployer.get_deployer_version() == "1.0.0"
