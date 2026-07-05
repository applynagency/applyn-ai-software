"""Additional CI/CD pipeline providers."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.github_actions import _sim_pipelines, _sim_runs


class _SimPipelineProvider(PipelineProvider):
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        repo = repository or "nexora/service"
        return [
            PipelineInfo(f"{self.provider.lower()}-{p.external_id}", p.name, repo, self.provider)
            for p in _sim_pipelines(repo)
        ]

    def list_runs(self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20) -> list[PipelineRunInfo]:
        return _sim_runs(pipeline)


class GitLabCIProvider(_SimPipelineProvider):
    def __init__(self) -> None:
        super().__init__("GITLAB_CI")


class AzurePipelinesProvider(_SimPipelineProvider):
    def __init__(self) -> None:
        super().__init__("AZURE_PIPELINES")


class JenkinsProvider(_SimPipelineProvider):
    def __init__(self) -> None:
        super().__init__("JENKINS")


class CircleCIProvider(_SimPipelineProvider):
    def __init__(self) -> None:
        super().__init__("CIRCLECI")


class DroneProvider(_SimPipelineProvider):
    def __init__(self) -> None:
        super().__init__("DRONE")


class ArgoWorkflowsProvider(_SimPipelineProvider):
    def __init__(self) -> None:
        super().__init__("ARGO_WORKFLOWS")
