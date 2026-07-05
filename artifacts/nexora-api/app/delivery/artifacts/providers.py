"""Artifact registry providers."""

from __future__ import annotations

from app.delivery.artifacts.base import _SimRegistryProvider


class DockerHubProvider(_SimRegistryProvider):
    def __init__(self) -> None:
        super().__init__("DOCKER_HUB")


class GHCRProvider(_SimRegistryProvider):
    def __init__(self) -> None:
        super().__init__("GHCR")


class ACRProvider(_SimRegistryProvider):
    def __init__(self) -> None:
        super().__init__("ACR")


class ECRProvider(_SimRegistryProvider):
    def __init__(self) -> None:
        super().__init__("ECR")


class GARProvider(_SimRegistryProvider):
    def __init__(self) -> None:
        super().__init__("GAR")


class HarborProvider(_SimRegistryProvider):
    def __init__(self) -> None:
        super().__init__("HARBOR")
