"""Artifact registry provider registry."""

from __future__ import annotations

from app.delivery.artifacts.base import ArtifactRegistryProvider
from app.delivery.artifacts.providers import (
    ACRProvider,
    DockerHubProvider,
    ECRProvider,
    GARProvider,
    GHCRProvider,
    HarborProvider,
)
from app.delivery.types import ArtifactRegistryType

_REGISTRY: dict[ArtifactRegistryType, ArtifactRegistryProvider] = {
    ArtifactRegistryType.DOCKER_HUB: DockerHubProvider(),
    ArtifactRegistryType.GHCR: GHCRProvider(),
    ArtifactRegistryType.ACR: ACRProvider(),
    ArtifactRegistryType.ECR: ECRProvider(),
    ArtifactRegistryType.GAR: GARProvider(),
    ArtifactRegistryType.HARBOR: HarborProvider(),
}


def get_artifact_registry(provider: str | ArtifactRegistryType) -> ArtifactRegistryProvider:
    key = ArtifactRegistryType(provider) if isinstance(provider, str) else provider
    impl = _REGISTRY.get(key)
    if impl is None:
        raise ValueError(f"unsupported artifact registry: {provider}")
    return impl


def supported_artifact_registries() -> list[str]:
    return [p.value for p in ArtifactRegistryType]
