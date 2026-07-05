"""Source provider registry."""

from __future__ import annotations

from app.delivery.source.base import SourceProvider
from app.delivery.source.azure_devops_live import AzureDevOpsSourceProvider
from app.delivery.source.bitbucket_live import BitbucketSourceProvider
from app.delivery.source.github import GitHubSourceProvider
from app.delivery.source.gitlab_live import GitLabSourceProvider
from app.delivery.source.providers import GiteaSourceProvider
from app.delivery.types import SourceProviderType

_REGISTRY: dict[SourceProviderType, SourceProvider] = {
    SourceProviderType.GITHUB: GitHubSourceProvider(),
    SourceProviderType.GITLAB: GitLabSourceProvider(),
    SourceProviderType.AZURE_DEVOPS: AzureDevOpsSourceProvider(),
    SourceProviderType.BITBUCKET: BitbucketSourceProvider(),
    SourceProviderType.GITEA: GiteaSourceProvider(),
}

_CREDENTIAL_MAP = {
    "GITHUB": SourceProviderType.GITHUB,
    "GITLAB": SourceProviderType.GITLAB,
    "AZURE_DEVOPS": SourceProviderType.AZURE_DEVOPS,
    "BITBUCKET": SourceProviderType.BITBUCKET,
    "GITEA": SourceProviderType.GITEA,
}


def get_source_provider(provider: str | SourceProviderType) -> SourceProvider:
    key = SourceProviderType(provider) if isinstance(provider, str) else provider
    impl = _REGISTRY.get(key)
    if impl is None:
        raise ValueError(f"unsupported source provider: {provider}")
    return impl


def source_provider_for_credential(credential_provider: str) -> SourceProviderType | None:
    return _CREDENTIAL_MAP.get(credential_provider.upper())


def supported_source_providers() -> list[str]:
    return [p.value for p in SourceProviderType]
