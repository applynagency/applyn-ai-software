"""Pipeline provider registry."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineProvider
from app.delivery.pipelines.github_actions import GitHubActionsProvider
from app.delivery.pipelines.azure_devops_live import AzurePipelinesProvider
from app.delivery.pipelines.bitbucket_live import BitbucketPipelinesProvider
from app.delivery.pipelines.circleci_live import CircleCIProvider
from app.delivery.pipelines.gitlab_live import GitLabCIProvider
from app.delivery.pipelines.jenkins_live import JenkinsProvider
from app.delivery.pipelines.providers import (
    ArgoWorkflowsProvider,
    DroneProvider,
)
from app.delivery.types import PipelineProviderType

_REGISTRY: dict[PipelineProviderType, PipelineProvider] = {
    PipelineProviderType.GITHUB_ACTIONS: GitHubActionsProvider(),
    PipelineProviderType.GITLAB_CI: GitLabCIProvider(),
    PipelineProviderType.AZURE_PIPELINES: AzurePipelinesProvider(),
    PipelineProviderType.JENKINS: JenkinsProvider(),
    PipelineProviderType.CIRCLECI: CircleCIProvider(),
    PipelineProviderType.BITBUCKET_PIPELINES: BitbucketPipelinesProvider(),
    PipelineProviderType.DRONE: DroneProvider(),
    PipelineProviderType.ARGO_WORKFLOWS: ArgoWorkflowsProvider(),
}


def get_pipeline_provider(provider: str | PipelineProviderType) -> PipelineProvider:
    key = PipelineProviderType(provider) if isinstance(provider, str) else provider
    impl = _REGISTRY.get(key)
    if impl is None:
        raise ValueError(f"unsupported pipeline provider: {provider}")
    return impl


def supported_pipeline_providers() -> list[str]:
    return [p.value for p in PipelineProviderType]
