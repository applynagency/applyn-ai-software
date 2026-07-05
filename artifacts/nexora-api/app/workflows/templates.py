import json
from dataclasses import dataclass, field
from pathlib import Path

from app.models.workflow import StageType, WorkflowRuleType, WorkflowStatus


@dataclass
class TemplateStageTeam:
    name: str
    team_type: str
    execution_order: int = 1
    is_required: bool = True


@dataclass
class TemplateStage:
    name: str
    sequence: int
    stage_type: StageType
    description: str = ""
    approval_required: bool = False
    teams: list[TemplateStageTeam] = field(default_factory=list)


@dataclass
class TemplateRule:
    rule_type: WorkflowRuleType
    configuration_json: dict


@dataclass
class WorkflowTemplate:
    slug: str
    name: str
    description: str
    industry: str
    workflow_name: str
    workflow_description: str
    workflow_status: WorkflowStatus
    stages: list[TemplateStage] = field(default_factory=list)
    rules: list[TemplateRule] = field(default_factory=list)


CATALOG_PATH = Path(__file__).parent / "data" / "template_catalog.json"


def load_catalog_raw() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_template(raw: dict) -> WorkflowTemplate:
    workflow_meta = raw.get("workflow", {})
    stages = []
    for stage_data in raw.get("stages", []):
        stages.append(
            TemplateStage(
                name=stage_data["name"],
                description=stage_data.get("description", ""),
                sequence=stage_data["sequence"],
                stage_type=StageType(stage_data["stage_type"]),
                approval_required=stage_data.get("approval_required", False),
                teams=[
                    TemplateStageTeam(
                        name=team["name"],
                        team_type=team["team_type"],
                        execution_order=team.get("execution_order", 1),
                        is_required=team.get("is_required", True),
                    )
                    for team in stage_data.get("teams", [])
                ],
            )
        )
    rules = [
        TemplateRule(
            rule_type=WorkflowRuleType(rule["rule_type"]),
            configuration_json=rule.get("configuration_json", {}),
        )
        for rule in raw.get("rules", [])
    ]
    return WorkflowTemplate(
        slug=raw["slug"],
        name=raw["name"],
        description=raw.get("description", ""),
        industry=raw.get("industry", ""),
        workflow_name=workflow_meta.get("name", raw["name"]),
        workflow_description=workflow_meta.get("description", ""),
        workflow_status=WorkflowStatus(workflow_meta.get("status", "ACTIVE")),
        stages=stages,
        rules=rules,
    )


def load_templates() -> list[WorkflowTemplate]:
    catalog = load_catalog_raw()
    return [_parse_template(item) for item in catalog.get("templates", [])]


WORKFLOW_TEMPLATES = load_templates()


def get_template_by_slug(slug: str) -> WorkflowTemplate | None:
    for template in WORKFLOW_TEMPLATES:
        if template.slug == slug:
            return template
    return None


def get_template_definition(slug: str) -> dict | None:
    catalog = load_catalog_raw()
    for template in catalog.get("templates", []):
        if template["slug"] == slug:
            return template
    return None
