from app.models.organization import OrganizationRole

ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}
WRITE_ROLES = ADMIN_ROLES | {OrganizationRole.PROJECT_MANAGER, OrganizationRole.DEVELOPER}
READ_ROLES = WRITE_ROLES | {OrganizationRole.VIEWER}


def can_manage_organization(role: OrganizationRole) -> bool:
    return role in ADMIN_ROLES


def can_manage_members(role: OrganizationRole) -> bool:
    return role in ADMIN_ROLES


def can_assign_role(actor_role: OrganizationRole, target_role: OrganizationRole) -> bool:
    if target_role == OrganizationRole.OWNER:
        return actor_role == OrganizationRole.OWNER
    return actor_role in ADMIN_ROLES


def can_write_resources(role: OrganizationRole) -> bool:
    return role in WRITE_ROLES


def can_read_resources(role: OrganizationRole) -> bool:
    return role in READ_ROLES


TEAM_ADMIN_ROLES = ADMIN_ROLES
TEAM_WRITE_ROLES = ADMIN_ROLES | {OrganizationRole.PROJECT_MANAGER}
TEAM_READ_ROLES = TEAM_WRITE_ROLES | {OrganizationRole.DEVELOPER, OrganizationRole.VIEWER}


def can_manage_teams(role: OrganizationRole) -> bool:
    return role in TEAM_ADMIN_ROLES


def can_write_teams(role: OrganizationRole) -> bool:
    return role in TEAM_WRITE_ROLES


def can_read_teams(role: OrganizationRole) -> bool:
    return role in TEAM_READ_ROLES


WORKFLOW_ADMIN_ROLES = ADMIN_ROLES
WORKFLOW_WRITE_ROLES = ADMIN_ROLES | {OrganizationRole.PROJECT_MANAGER}
WORKFLOW_READ_ROLES = WORKFLOW_WRITE_ROLES | {OrganizationRole.DEVELOPER, OrganizationRole.VIEWER}


def can_manage_workflows(role: OrganizationRole) -> bool:
    return role in WORKFLOW_ADMIN_ROLES


def can_write_workflows(role: OrganizationRole) -> bool:
    return role in WORKFLOW_WRITE_ROLES


def can_read_workflows(role: OrganizationRole) -> bool:
    return role in WORKFLOW_READ_ROLES


AI_AGENT_ADMIN_ROLES = ADMIN_ROLES
AI_AGENT_WRITE_ROLES = ADMIN_ROLES | {OrganizationRole.PROJECT_MANAGER}
AI_AGENT_READ_ROLES = AI_AGENT_WRITE_ROLES | {OrganizationRole.DEVELOPER, OrganizationRole.VIEWER}


def can_manage_ai_agents(role: OrganizationRole) -> bool:
    return role in AI_AGENT_ADMIN_ROLES


def can_write_ai_agents(role: OrganizationRole) -> bool:
    return role in AI_AGENT_WRITE_ROLES


def can_read_ai_agents(role: OrganizationRole) -> bool:
    return role in AI_AGENT_READ_ROLES


# Sprint 37A — Custom AI Teams (customer-defined AI workforce). Independent of
# the internal AI Agent builder permissions above.
AI_TEAM_ADMIN_ROLES = ADMIN_ROLES
AI_TEAM_WRITE_ROLES = ADMIN_ROLES | {OrganizationRole.PROJECT_MANAGER, OrganizationRole.DEVELOPER}
AI_TEAM_READ_ROLES = AI_TEAM_WRITE_ROLES | {OrganizationRole.VIEWER}


def can_manage_ai_teams(role: OrganizationRole) -> bool:
    return role in AI_TEAM_ADMIN_ROLES


def can_write_ai_teams(role: OrganizationRole) -> bool:
    return role in AI_TEAM_WRITE_ROLES


def can_read_ai_teams(role: OrganizationRole) -> bool:
    return role in AI_TEAM_READ_ROLES
