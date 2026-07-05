from dataclasses import dataclass, field

from app.models.workflow import WorkflowRuleType


@dataclass
class RuleDefinition:
    rule_type: WorkflowRuleType
    description: str
    default_configuration: dict = field(default_factory=dict)


RULE_DEFINITIONS: dict[WorkflowRuleType, RuleDefinition] = {
    WorkflowRuleType.HEALTHCARE_COMPLIANCE: RuleDefinition(
        rule_type=WorkflowRuleType.HEALTHCARE_COMPLIANCE,
        description="If Healthcare industry, compliance review stage is required.",
        default_configuration={"stage_name": "Compliance Review", "required": True},
    ),
    WorkflowRuleType.FINANCIAL_SECURITY: RuleDefinition(
        rule_type=WorkflowRuleType.FINANCIAL_SECURITY,
        description="If Financial Services, security review is required.",
        default_configuration={"stage_name": "Security Review", "required": True},
    ),
    WorkflowRuleType.FINANCIAL_RISK: RuleDefinition(
        rule_type=WorkflowRuleType.FINANCIAL_RISK,
        description="If Financial Services, risk review is required.",
        default_configuration={"stage_name": "Risk Review", "required": True},
    ),
    WorkflowRuleType.PRODUCTION_APPROVAL: RuleDefinition(
        rule_type=WorkflowRuleType.PRODUCTION_APPROVAL,
        description="If production deployment, approval is required.",
        default_configuration={"stage_type": "DEPLOYMENT", "approval_required": True},
    ),
}


class WorkflowRulesEngine:
    """Stores and validates workflow rules. Execution deferred to Sprint 5."""

    @staticmethod
    def list_available_rules() -> list[dict]:
        return [
            {
                "rule_type": definition.rule_type.value,
                "description": definition.description,
                "default_configuration": definition.default_configuration,
            }
            for definition in RULE_DEFINITIONS.values()
        ]

    @staticmethod
    def validate_rule(rule_type: WorkflowRuleType, configuration_json: dict) -> dict:
        definition = RULE_DEFINITIONS.get(rule_type)
        if not definition:
            return configuration_json
        merged = dict(definition.default_configuration)
        merged.update(configuration_json or {})
        return merged
