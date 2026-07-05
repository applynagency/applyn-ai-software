from app.models.approval import ApprovalRunStatus, WorkflowApprovalStatus
from app.models.team import TeamType
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS, TeamMappingService
from app.tests.route_helpers import collect_route_paths


def test_approval_run_status_values():
    assert ApprovalRunStatus.PENDING.value == "PENDING"
    assert ApprovalRunStatus.RUNNING.value == "RUNNING"
    assert ApprovalRunStatus.COMPLETED.value == "COMPLETED"
    assert ApprovalRunStatus.FAILED.value == "FAILED"


def test_approval_models_importable():
    from app.models.approval import ApprovalArtifact, ApprovalRun

    assert ApprovalRun.__tablename__ == "approval_runs"
    assert ApprovalArtifact.__tablename__ == "approval_artifacts"


def test_approval_service_importable():
    from app.services.approval import ApprovalWorkflowService

    assert ApprovalWorkflowService.__name__ == "ApprovalWorkflowService"


def test_approval_agent_importable():
    from app.agents.approval import ApprovalWorkflowAgent

    assert ApprovalWorkflowAgent.__name__ == "ApprovalWorkflowAgent"


def test_approval_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/agents/approval" in path for path in paths)


def test_approval_decisions_api_router_registered():
    from app.api.v1.router import api_router

    paths = collect_route_paths(api_router)
    assert any("/approval/" in path for path in paths)


def test_frontend_team_has_seven_agents():
    agents = TEAM_TYPE_AGENT_MAPPINGS[TeamType.FRONTEND]
    assert len(agents) == 7
    assert agents[-1] == "fullstack_assembly"


def test_product_team_ends_with_deployment():
    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert agents[-1] == "deployment"
    assert len(agents) == len(TEAM_TYPE_AGENT_MAPPINGS[TeamType.PRODUCT])


def test_deployment_team_includes_approval_after_fullstack_assembly():
    agents = TeamMappingService.agents_for_team_type(TeamType.DEPLOYMENT)
    assert agents == ["fullstack_assembly", "approval", "deployment"]


def test_workflow_approval_status_under_review_default():
    assert WorkflowApprovalStatus.UNDER_REVIEW.value == "UNDER_REVIEW"
