from dataclasses import dataclass

from app.models.team import TeamType

TEAM_TYPE_AGENT_MAPPINGS: dict[TeamType, list[str]] = {
    TeamType.PRODUCT: [
        "product_owner",
        "business_analyst",
        "backend_architect",
        "backend_v1",
        "backend_v2",
        "backend_v3",
        "backend_code_review",
        "backend_execution",
        "uiux_designer",
        "frontend_architect",
        "frontend_v1",
        "frontend_v2",
        "frontend_v3",
        "frontend_code_review",
        "frontend_execution",
        "qa_architect",
        "unit_test_generator",
        "integration_test",
        "security_test",
        "performance_test",
        "qa_approval",
        "infrastructure_architect",
        "docker_agent",
        "cicd_agent",
        "kubernetes_agent",
        "observability_agent",
        "sre_approval_agent",
        "fullstack_assembly",
        "approval",
        "deployment",
    ],
    TeamType.UI_UX: ["uiux_designer", "design_reviewer"],
    TeamType.FRONTEND: [
        "frontend_architect",
        "frontend_v1",
        "frontend_v2",
        "frontend_v3",
        "frontend_code_review",
        "frontend_execution",
        "fullstack_assembly",
    ],
    TeamType.BACKEND: [
        "backend_architect",
        "backend_v1",
        "backend_v2",
        "backend_v3",
        "backend_code_review",
        "backend_execution",
    ],
    TeamType.QA: [
        "qa_architect",
        "unit_test_generator",
        "integration_test",
        "security_test",
        "performance_test",
        "qa_approval",
    ],
    TeamType.DEVOPS: [
        "infrastructure_architect",
        "docker_agent",
        "cicd_agent",
        "kubernetes_agent",
        "observability_agent",
        "sre_approval_agent",
    ],
    TeamType.DEPLOYMENT: ["fullstack_assembly", "approval", "deployment"],
    TeamType.SECURITY: ["security_analyst", "vulnerability_scanner"],
    TeamType.COMPLIANCE: ["compliance_reviewer", "audit_checker"],
    TeamType.CUSTOM: [],
}


@dataclass(frozen=True)
class AgentMappingSpec:
    internal_agent: str
    execution_order: int
    is_required: bool = True


class TeamMappingService:
    """Maps team types to ordered internal agent identifiers for workflow execution."""

    @staticmethod
    def agents_for_team_type(team_type: TeamType | str) -> list[str]:
        if isinstance(team_type, str):
            team_type = TeamType(team_type)
        return list(TEAM_TYPE_AGENT_MAPPINGS.get(team_type, []))

    @classmethod
    def mapping_specs_for_team_type(cls, team_type: TeamType | str) -> list[AgentMappingSpec]:
        return [
            AgentMappingSpec(
                internal_agent=agent,
                execution_order=index,
                is_required=True,
            )
            for index, agent in enumerate(cls.agents_for_team_type(team_type), start=1)
        ]

    @staticmethod
    def all_mappings() -> dict[str, list[dict]]:
        service = TeamMappingService()
        return {
            team_type.value: [
                {
                    "internal_agent": spec.internal_agent,
                    "execution_order": spec.execution_order,
                    "is_required": spec.is_required,
                }
                for spec in service.mapping_specs_for_team_type(team_type)
            ]
            for team_type in TeamType
        }
