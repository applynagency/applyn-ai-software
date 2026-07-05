"""Sprint 56A.1 — ArchitectureDiagramService.

Generates documentation architecture diagrams (Mermaid) for each supported
integration. Each diagram describes Source Systems, Data Flow, Processing Layer,
Platform Components, and Outputs. Deterministic and read-only.
"""

from __future__ import annotations

from typing import Any


def _diagram(
    *, key: str, name: str, source_systems: list[str], processing_layer: list[str],
    platform_components: list[str], outputs: list[str], mermaid: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "source_systems": source_systems,
        "data_flow": [
            f"{name} → Nexora Collector",
            "Collector → Processing Layer",
            "Processing Layer → Platform Components",
            "Platform Components → Outputs",
        ],
        "processing_layer": processing_layer,
        "platform_components": platform_components,
        "outputs": outputs,
        "mermaid": mermaid,
    }


_PIPELINE = (
    "graph TD\n"
    "  {src} --> Collector[Nexora Collector]\n"
    "  Collector --> Discovery\n"
    "  Discovery --> ServiceMap[Service Map]\n"
    "  ServiceMap --> DependencyGraph[Dependency Graph]\n"
    "  DependencyGraph --> Monitoring\n"
    "  Monitoring --> Incidents"
)

_NOTIFY = (
    "graph TD\n"
    "  Alerts --> Router[Notification Router]\n"
    "  Incidents --> Router\n"
    "  Router --> {dst}"
)

DIAGRAMS: list[dict[str, Any]] = [
    _diagram(
        key="aws", name="AWS",
        source_systems=["EC2", "RDS", "CloudWatch", "Cost Explorer"],
        processing_layer=["Discovery", "Service Mapper", "Dependency Inference"],
        platform_components=["Monitoring", "Service Health", "Cost Optimization"],
        outputs=["Discovered resources", "Alerts", "Cost attribution"],
        mermaid=_PIPELINE.format(src="AWS"),
    ),
    _diagram(
        key="azure", name="Azure",
        source_systems=["Azure Resources", "Azure Monitor"],
        processing_layer=["Discovery", "Service Mapper", "Dependency Inference"],
        platform_components=["Monitoring", "Service Health"],
        outputs=["Discovered resources", "Alerts"],
        mermaid=_PIPELINE.format(src="Azure"),
    ),
    _diagram(
        key="kubernetes", name="Kubernetes",
        source_systems=["Deployments", "Pods", "Services"],
        processing_layer=["Discovery", "Workload Mapper", "Health Scorer"],
        platform_components=["Service Health", "Monitoring", "Dependency Graph"],
        outputs=["Discovered workloads", "Health scores"],
        mermaid=_PIPELINE.format(src="Kubernetes"),
    ),
    _diagram(
        key="github", name="GitHub",
        source_systems=["Commits", "Releases", "Deployments"],
        processing_layer=["Change Ingestion", "Change Correlation"],
        platform_components=["Incident Change Intelligence", "Change Failure Prediction", "Deployment Safety"],
        outputs=["Suspected changes", "Failure predictions"],
        mermaid=(
            "graph TD\n"
            "  GitHub --> ChangeIngestion[Change Ingestion]\n"
            "  ChangeIngestion --> ChangeCorrelation[Change Correlation]\n"
            "  ChangeCorrelation --> Incidents\n"
            "  ChangeCorrelation --> ChangeFailure[Change Failure Prediction]"
        ),
    ),
    _diagram(
        key="gitlab", name="GitLab",
        source_systems=["Merge Requests", "Commits", "Pipelines"],
        processing_layer=["Change Ingestion", "Change Correlation"],
        platform_components=["Incident Change Intelligence", "Change Failure Prediction"],
        outputs=["Suspected changes", "Failure predictions"],
        mermaid=(
            "graph TD\n"
            "  GitLab --> ChangeIngestion[Change Ingestion]\n"
            "  ChangeIngestion --> ChangeCorrelation[Change Correlation]\n"
            "  ChangeCorrelation --> Incidents\n"
            "  ChangeCorrelation --> ChangeFailure[Change Failure Prediction]"
        ),
    ),
    _diagram(
        key="slack", name="Slack",
        source_systems=["Nexora Alerts", "Nexora Incidents"],
        processing_layer=["Notification Router", "Severity Routing"],
        platform_components=["Slack App"],
        outputs=["Channel notifications"],
        mermaid=_NOTIFY.format(dst="Slack[Slack Channels]"),
    ),
    _diagram(
        key="microsoft-teams", name="Microsoft Teams",
        source_systems=["Nexora Alerts", "Nexora Incidents"],
        processing_layer=["Notification Router", "Severity Routing"],
        platform_components=["Teams Incoming Webhook"],
        outputs=["Channel notifications"],
        mermaid=_NOTIFY.format(dst="Teams[Teams Channels]"),
    ),
    _diagram(
        key="jira", name="Jira",
        source_systems=["Nexora Incidents", "Postmortem Action Items"],
        processing_layer=["Issue Mapper", "Priority Mapping"],
        platform_components=["Jira Integration"],
        outputs=["Jira issues", "Linked tickets"],
        mermaid=(
            "graph TD\n"
            "  Incidents --> IssueMapper[Issue Mapper]\n"
            "  ActionItems[Postmortem Action Items] --> IssueMapper\n"
            "  IssueMapper --> Jira[Jira Project]"
        ),
    ),
]

_INDEX = {d["key"]: d for d in DIAGRAMS}


class ArchitectureDiagramService:
    def list(self) -> dict[str, Any]:
        return {"items": DIAGRAMS, "total": len(DIAGRAMS)}

    def get(self, key: str) -> dict[str, Any] | None:
        return _INDEX.get(key)
