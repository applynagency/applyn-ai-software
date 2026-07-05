import json
from dataclasses import dataclass, field
from pathlib import Path

from app.models.ai_agent import AIAgentInputType, AIAgentOutputType, AIAgentStatus
from app.models.team import ResponsibilityPriority


@dataclass
class TemplateInput:
    input_name: str
    input_type: AIAgentInputType
    required: bool = True


@dataclass
class TemplateOutput:
    output_name: str
    output_type: AIAgentOutputType


@dataclass
class TemplateResponsibility:
    title: str
    description: str = ""
    priority: ResponsibilityPriority = ResponsibilityPriority.MEDIUM


@dataclass
class AIAgentTemplate:
    slug: str
    name: str
    description: str
    category: str
    agent_name: str
    agent_description: str
    agent_goal: str
    agent_status: AIAgentStatus
    prompt_template: str
    inputs: list[TemplateInput] = field(default_factory=list)
    outputs: list[TemplateOutput] = field(default_factory=list)
    responsibilities: list[TemplateResponsibility] = field(default_factory=list)


CATALOG_PATH = Path(__file__).parent / "data" / "template_catalog.json"


def load_catalog_raw() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_template(raw: dict) -> AIAgentTemplate:
    agent_meta = raw.get("agent", {})
    return AIAgentTemplate(
        slug=raw["slug"],
        name=raw["name"],
        description=raw.get("description", ""),
        category=raw.get("category", ""),
        agent_name=agent_meta.get("name", raw["name"]),
        agent_description=agent_meta.get("description", ""),
        agent_goal=agent_meta.get("goal", ""),
        agent_status=AIAgentStatus(agent_meta.get("status", "ACTIVE")),
        prompt_template=agent_meta.get("prompt_template", ""),
        inputs=[
            TemplateInput(
                input_name=item["input_name"],
                input_type=AIAgentInputType(item["input_type"]),
                required=item.get("required", True),
            )
            for item in raw.get("inputs", [])
        ],
        outputs=[
            TemplateOutput(
                output_name=item["output_name"],
                output_type=AIAgentOutputType(item["output_type"]),
            )
            for item in raw.get("outputs", [])
        ],
        responsibilities=[
            TemplateResponsibility(
                title=item["title"],
                description=item.get("description", ""),
                priority=ResponsibilityPriority(item.get("priority", "MEDIUM")),
            )
            for item in raw.get("responsibilities", [])
        ],
    )


def load_templates() -> list[AIAgentTemplate]:
    catalog = load_catalog_raw()
    return [_parse_template(item) for item in catalog.get("templates", [])]


AI_AGENT_TEMPLATES = load_templates()


def get_template_by_slug(slug: str) -> AIAgentTemplate | None:
    for template in AI_AGENT_TEMPLATES:
        if template.slug == slug:
            return template
    return None


def get_template_definition(slug: str) -> dict | None:
    catalog = load_catalog_raw()
    for template in catalog.get("templates", []):
        if template["slug"] == slug:
            return template
    return None
