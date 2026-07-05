from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.workspace import Workspace
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository
from app.tenancy.permissions import (
    can_read_ai_agents,
    can_read_resources,
    can_read_workflows,
    can_write_resources,
)


def ensure_same_organization(
    resource_org_id: str, org_id: str, resource_type: str, resource_id: str
) -> None:
    if resource_org_id != org_id:
        raise NotFoundError(resource_type, resource_id)


async def ensure_org_membership(
    session: AsyncSession, organization_id: str, user_id: str, *, superuser: bool = False
):
    if superuser:
        return
    member_repo = OrganizationMemberRepository(session)
    membership = await member_repo.get_membership(organization_id, user_id)
    if not membership:
        raise ForbiddenError("You are not a member of this organization")
    return membership


async def ensure_workspace_in_org(
    session: AsyncSession, workspace: Workspace, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(workspace.organization_id, org_id, "Workspace", workspace.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def ensure_workspace_write(
    session: AsyncSession, workspace: Workspace, org_context: OrgContext
) -> None:
    await ensure_workspace_in_org(session, workspace, org_context)
    if org_context.user.is_superuser:
        return
    if org_context.role and not can_write_resources(org_context.role):
        raise ForbiddenError()


async def get_workspace_for_org(
    session: AsyncSession, workspace_id: str, org_context: OrgContext
) -> Workspace:
    workspace_repo = WorkspaceRepository(session)
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Workspace", workspace_id)
    await ensure_workspace_in_org(session, workspace, org_context)
    return workspace


async def get_project_for_org(
    session: AsyncSession, project_id: str, org_context: OrgContext
):
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id)
    if not project:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Project", project_id)
    workspace_repo = WorkspaceRepository(session)
    workspace = await workspace_repo.get_by_id(project.workspace_id)
    if not workspace:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Workspace", project.workspace_id)
    await ensure_workspace_in_org(session, workspace, org_context)
    return project


async def get_requirement_for_org(
    session: AsyncSession, requirement_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.requirement import RequirementRepository

    req_repo = RequirementRepository(session)
    requirement = await req_repo.get_by_id(requirement_id)
    if not requirement:
        raise NotFoundError("Requirement", requirement_id)
    await get_project_for_org(session, requirement.project_id, org_context)
    return requirement


async def ensure_team_in_org(session: AsyncSession, team, org_context: OrgContext) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(team.organization_id, org_id, "Team", team.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_team_for_org(session: AsyncSession, team_id: str, org_context: OrgContext):
    from app.core.exceptions import NotFoundError
    from app.repositories.team import TeamRepository

    team_repo = TeamRepository(session)
    team = await team_repo.get_with_details(team_id)
    if not team:
        raise NotFoundError("Team", team_id)
    await ensure_team_in_org(session, team, org_context)
    return team


async def ensure_workflow_in_org(session: AsyncSession, workflow, org_context: OrgContext) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(workflow.organization_id, org_id, "Workflow", workflow.id)
    if org_context.role and not can_read_workflows(org_context.role):
        raise ForbiddenError()


async def get_workflow_for_org(
    session: AsyncSession, workflow_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.workflow import WorkflowRepository

    workflow_repo = WorkflowRepository(session)
    workflow = await workflow_repo.get_with_details(workflow_id)
    if not workflow:
        raise NotFoundError("Workflow", workflow_id)
    await ensure_workflow_in_org(session, workflow, org_context)
    return workflow


async def get_stage_for_org(session: AsyncSession, stage_id: str, org_context: OrgContext):
    from app.core.exceptions import NotFoundError
    from app.repositories.workflow import WorkflowStageRepository

    stage_repo = WorkflowStageRepository(session)
    stage = await stage_repo.get_with_details(stage_id)
    if not stage:
        raise NotFoundError("WorkflowStage", stage_id)
    await get_workflow_for_org(session, stage.workflow_id, org_context)
    return stage


async def ensure_workflow_execution_in_org(
    session: AsyncSession, execution, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(execution.organization_id, org_id, "WorkflowExecution", execution.id)
    if org_context.role and not can_read_workflows(org_context.role):
        raise ForbiddenError()


async def get_workflow_execution_for_org(
    session: AsyncSession, execution_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.workflow_execution import WorkflowExecutionRepository

    execution_repo = WorkflowExecutionRepository(session)
    execution = await execution_repo.get_with_details(execution_id)
    if not execution:
        raise NotFoundError("WorkflowExecution", execution_id)
    await ensure_workflow_execution_in_org(session, execution, org_context)
    return execution


async def ensure_ai_agent_in_org(session: AsyncSession, agent, org_context: OrgContext) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(agent.organization_id, org_id, "AIAgent", agent.id)
    if org_context.role and not can_read_ai_agents(org_context.role):
        raise ForbiddenError()


async def get_ai_agent_for_org(session: AsyncSession, agent_id: str, org_context: OrgContext):
    from app.core.exceptions import NotFoundError
    from app.repositories.ai_agent import AIAgentRepository

    agent_repo = AIAgentRepository(session)
    agent = await agent_repo.get_with_details(agent_id)
    if not agent:
        raise NotFoundError("AIAgent", agent_id)
    await ensure_ai_agent_in_org(session, agent, org_context)
    return agent


async def ensure_ai_team_in_org(session: AsyncSession, team, org_context: OrgContext) -> None:
    from app.tenancy.permissions import can_read_ai_teams

    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(team.organization_id, org_id, "AITeam", team.id)
    if org_context.role and not can_read_ai_teams(org_context.role):
        raise ForbiddenError()


async def get_ai_team_for_org(session: AsyncSession, team_id: str, org_context: OrgContext):
    from app.core.exceptions import NotFoundError
    from app.repositories.ai_team import AITeamRepository

    team_repo = AITeamRepository(session)
    team = await team_repo.get_with_agents(team_id)
    if not team:
        raise NotFoundError("AITeam", team_id)
    await ensure_ai_team_in_org(session, team, org_context)
    return team


async def ensure_ai_team_agent_in_org(session: AsyncSession, agent, org_context: OrgContext) -> None:
    from app.tenancy.permissions import can_read_ai_teams

    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(agent.organization_id, org_id, "AITeamAgent", agent.id)
    if org_context.role and not can_read_ai_teams(org_context.role):
        raise ForbiddenError()


async def get_ai_team_agent_for_org(session: AsyncSession, agent_id: str, org_context: OrgContext):
    from app.core.exceptions import NotFoundError
    from app.repositories.ai_team import AITeamAgentRepository

    agent_repo = AITeamAgentRepository(session)
    agent = await agent_repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundError("AITeamAgent", agent_id)
    await ensure_ai_team_agent_in_org(session, agent, org_context)
    return agent


async def ensure_business_analyst_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BusinessAnalystRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_business_analyst_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.business_analyst import BusinessAnalystRunRepository

    run_repo = BusinessAnalystRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BusinessAnalystRun", run_id)
    await ensure_business_analyst_run_in_org(session, run, org_context)
    return run


async def ensure_backend_architect_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BackendArchitectRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_backend_architect_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.backend_architect import BackendArchitectRunRepository

    run_repo = BackendArchitectRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BackendArchitectRun", run_id)
    await ensure_backend_architect_run_in_org(session, run, org_context)
    return run


async def ensure_qa_architect_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "QAArchitectRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_qa_architect_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.qa_architect import QAArchitectRunRepository

    run_repo = QAArchitectRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("QAArchitectRun", run_id)
    await ensure_qa_architect_run_in_org(session, run, org_context)
    return run


async def ensure_unit_test_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "UnitTestRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_unit_test_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.unit_test import UnitTestRunRepository

    run_repo = UnitTestRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("UnitTestRun", run_id)
    await ensure_unit_test_run_in_org(session, run, org_context)
    return run


async def ensure_integration_test_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "IntegrationTestRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_integration_test_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.integration_test import IntegrationTestRunRepository

    run_repo = IntegrationTestRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("IntegrationTestRun", run_id)
    await ensure_integration_test_run_in_org(session, run, org_context)
    return run


async def ensure_security_test_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "SecurityTestRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_security_test_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.security_test import SecurityTestRunRepository

    run_repo = SecurityTestRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("SecurityTestRun", run_id)
    await ensure_security_test_run_in_org(session, run, org_context)
    return run


async def ensure_performance_test_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "PerformanceTestRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_performance_test_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.performance_test import PerformanceTestRunRepository

    run_repo = PerformanceTestRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("PerformanceTestRun", run_id)
    await ensure_performance_test_run_in_org(session, run, org_context)
    return run


async def ensure_qa_approval_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "QAApprovalRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_qa_approval_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.qa_approval import QAApprovalRunRepository

    run_repo = QAApprovalRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("QAApprovalRun", run_id)
    await ensure_qa_approval_run_in_org(session, run, org_context)
    return run


async def ensure_backend_v1_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BackendV1Run", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_backend_v1_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.backend_v1 import BackendV1RunRepository

    run_repo = BackendV1RunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BackendV1Run", run_id)
    await ensure_backend_v1_run_in_org(session, run, org_context)
    return run


async def ensure_backend_v2_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BackendV2Run", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_backend_v2_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.backend_v2 import BackendV2RunRepository

    run_repo = BackendV2RunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BackendV2Run", run_id)
    await ensure_backend_v2_run_in_org(session, run, org_context)
    return run


async def ensure_backend_v3_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BackendV3Run", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_backend_v3_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.backend_v3 import BackendV3RunRepository

    run_repo = BackendV3RunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BackendV3Run", run_id)
    await ensure_backend_v3_run_in_org(session, run, org_context)
    return run


async def ensure_backend_code_review_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BackendCodeReviewRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_backend_code_review_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.backend_code_review import BackendCodeReviewRunRepository

    run_repo = BackendCodeReviewRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BackendCodeReviewRun", run_id)
    await ensure_backend_code_review_run_in_org(session, run, org_context)
    return run


async def ensure_uiux_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "UIUXRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_uiux_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.uiux_designer import UIUXRunRepository

    run_repo = UIUXRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("UIUXRun", run_id)
    await ensure_uiux_run_in_org(session, run, org_context)
    return run


async def ensure_frontend_architect_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FrontendArchitectRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_frontend_architect_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.frontend_architect import FrontendArchitectRunRepository

    run_repo = FrontendArchitectRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FrontendArchitectRun", run_id)
    await ensure_frontend_architect_run_in_org(session, run, org_context)
    return run


async def ensure_frontend_v1_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FrontendV1Run", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_frontend_v1_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.frontend_v1 import FrontendV1RunRepository

    run_repo = FrontendV1RunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FrontendV1Run", run_id)
    await ensure_frontend_v1_run_in_org(session, run, org_context)
    return run


async def ensure_frontend_v2_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FrontendV2Run", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_frontend_v2_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.frontend_v2 import FrontendV2RunRepository

    run_repo = FrontendV2RunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FrontendV2Run", run_id)
    await ensure_frontend_v2_run_in_org(session, run, org_context)
    return run


async def ensure_frontend_v3_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FrontendV3Run", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_frontend_v3_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.frontend_v3 import FrontendV3RunRepository

    run_repo = FrontendV3RunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FrontendV3Run", run_id)
    await ensure_frontend_v3_run_in_org(session, run, org_context)
    return run


async def ensure_frontend_code_review_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FrontendCodeReviewRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_frontend_code_review_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.frontend_code_review import FrontendCodeReviewRunRepository

    run_repo = FrontendCodeReviewRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FrontendCodeReviewRun", run_id)
    await ensure_frontend_code_review_run_in_org(session, run, org_context)
    return run


async def ensure_backend_execution_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "BackendExecutionRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_backend_execution_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.backend_execution import BackendExecutionRunRepository

    run_repo = BackendExecutionRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("BackendExecutionRun", run_id)
    await ensure_backend_execution_run_in_org(session, run, org_context)
    return run


async def ensure_frontend_execution_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FrontendExecutionRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_frontend_execution_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.frontend_execution import FrontendExecutionRunRepository

    run_repo = FrontendExecutionRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FrontendExecutionRun", run_id)
    await ensure_frontend_execution_run_in_org(session, run, org_context)
    return run


async def ensure_fullstack_assembly_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "FullstackAssemblyRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_fullstack_assembly_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.fullstack_assembly import FullstackAssemblyRunRepository

    run_repo = FullstackAssemblyRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("FullstackAssemblyRun", run_id)
    await ensure_fullstack_assembly_run_in_org(session, run, org_context)
    return run


async def ensure_approval_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "ApprovalRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_approval_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.approval import ApprovalRunRepository

    run_repo = ApprovalRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("ApprovalRun", run_id)
    await ensure_approval_run_in_org(session, run, org_context)
    return run


async def ensure_deployment_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "DeploymentRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_deployment_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.deployment import DeploymentRunRepository

    run_repo = DeploymentRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("DeploymentRun", run_id)
    await ensure_deployment_run_in_org(session, run, org_context)
    return run


async def ensure_regeneration_run_in_org(session: AsyncSession, run, org_context: OrgContext) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "RegenerationRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_regeneration_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.lifecycle import RegenerationRunRepository

    run_repo = RegenerationRunRepository(session)
    run = await run_repo.get_with_artifacts(run_id)
    if not run:
        raise NotFoundError("RegenerationRun", run_id)
    await ensure_regeneration_run_in_org(session, run, org_context)
    return run


async def ensure_infrastructure_architect_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "InfrastructureArchitectRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_infrastructure_architect_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.infrastructure_architect import InfrastructureArchitectRunRepository

    run_repo = InfrastructureArchitectRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("InfrastructureArchitectRun", run_id)
    await ensure_infrastructure_architect_run_in_org(session, run, org_context)
    return run


async def ensure_docker_agent_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "DockerAgentRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_docker_agent_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.docker_agent import DockerAgentRunRepository

    run_repo = DockerAgentRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("DockerAgentRun", run_id)
    await ensure_docker_agent_run_in_org(session, run, org_context)
    return run


async def ensure_cicd_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "CicdRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_cicd_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.cicd_agent import CicdRunRepository

    run_repo = CicdRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("CicdRun", run_id)
    await ensure_cicd_run_in_org(session, run, org_context)
    return run


async def ensure_kubernetes_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "KubernetesRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_kubernetes_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.kubernetes_agent import KubernetesRunRepository

    run_repo = KubernetesRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("KubernetesRun", run_id)
    await ensure_kubernetes_run_in_org(session, run, org_context)
    return run


async def ensure_observability_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "ObservabilityRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_observability_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.observability_agent import ObservabilityRunRepository

    run_repo = ObservabilityRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("ObservabilityRun", run_id)
    await ensure_observability_run_in_org(session, run, org_context)
    return run


async def ensure_sre_approval_run_in_org(
    session: AsyncSession, run, org_context: OrgContext
) -> None:
    if org_context.user.is_superuser:
        return
    org_id = org_context.requires_organization
    ensure_same_organization(run.organization_id, org_id, "SreApprovalRun", run.id)
    if org_context.role and not can_read_resources(org_context.role):
        raise ForbiddenError()


async def get_sre_approval_run_for_org(
    session: AsyncSession, run_id: str, org_context: OrgContext
):
    from app.core.exceptions import NotFoundError
    from app.repositories.sre_approval import SreApprovalRunRepository

    run_repo = SreApprovalRunRepository(session)
    run = await run_repo.get_with_artifact(run_id)
    if not run:
        raise NotFoundError("SreApprovalRun", run_id)
    await ensure_sre_approval_run_in_org(session, run, org_context)
    return run
