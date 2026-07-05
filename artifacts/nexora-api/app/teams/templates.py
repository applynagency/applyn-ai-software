import json
from dataclasses import dataclass
from pathlib import Path

from app.models.team import ResponsibilityPriority, TeamStatus, TeamType


@dataclass
class TemplateResponsibility:
    title: str
    description: str
    priority: ResponsibilityPriority = ResponsibilityPriority.MEDIUM


@dataclass
class TemplateTeam:
    name: str
    description: str
    team_type: TeamType
    status: TeamStatus = TeamStatus.ACTIVE
    responsibilities: list[TemplateResponsibility] | None = None


@dataclass
class TeamTemplate:
    slug: str
    name: str
    description: str
    industry: str
    teams: list[TemplateTeam]


CATALOG_PATH = Path(__file__).parent / "data" / "template_catalog.json"


def _parse_template(raw: dict) -> TeamTemplate:
    teams = []
    for team_data in raw.get("teams", []):
        responsibilities = [
            TemplateResponsibility(
                title=item["title"],
                description=item.get("description", ""),
                priority=ResponsibilityPriority(item.get("priority", "MEDIUM")),
            )
            for item in team_data.get("responsibilities", [])
        ]
        teams.append(
            TemplateTeam(
                name=team_data["name"],
                description=team_data.get("description", ""),
                team_type=TeamType(team_data["team_type"]),
                status=TeamStatus(team_data.get("status", "ACTIVE")),
                responsibilities=responsibilities,
            )
        )
    return TeamTemplate(
        slug=raw["slug"],
        name=raw["name"],
        description=raw.get("description", ""),
        industry=raw.get("industry", ""),
        teams=teams,
    )


def load_catalog_raw() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_templates() -> list[TeamTemplate]:
    catalog = load_catalog_raw()
    return [_parse_template(item) for item in catalog.get("templates", [])]


TEAM_TEMPLATES = load_templates()


def get_template_by_slug(slug: str) -> TeamTemplate | None:
    for template in TEAM_TEMPLATES:
        if template.slug == slug:
            return template
    return None


def get_template_definition(slug: str) -> dict | None:
    catalog = load_catalog_raw()
    for template in catalog.get("templates", []):
        if template["slug"] == slug:
            return template
    return None
