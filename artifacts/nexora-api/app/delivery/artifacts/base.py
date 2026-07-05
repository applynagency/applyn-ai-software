"""Artifact registry provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RegistryRepository:
    name: str
    uri: str
    image_count: int = 0
    visibility: str = "private"


@dataclass
class RegistryImage:
    repository: str
    tag: str
    digest: str
    size_bytes: int
    pushed_at: str
    vulnerabilities: dict = field(default_factory=dict)


class ArtifactRegistryProvider(ABC):
    provider: str

    @abstractmethod
    def list_repositories(self, secret: dict) -> list[RegistryRepository]:
        ...

    @abstractmethod
    def list_images(self, secret: dict, repository: str) -> list[RegistryImage]:
        ...

    def scan_summary(self, secret: dict, repository: str, tag: str) -> dict:
        return {"critical": 0, "high": 1, "medium": 2, "low": 5}


def _sim_repos(provider: str) -> list[RegistryRepository]:
    return [
        RegistryRepository(f"nexora/checkout-api", f"{provider.lower()}.io/nexora/checkout-api", 12),
        RegistryRepository(f"nexora/payment-service", f"{provider.lower()}.io/nexora/payment-service", 8),
    ]


def _sim_images(repo: str) -> list[RegistryImage]:
    return [
        RegistryImage(repo, "1.4.2", "sha256:abc123", 145_000_000, "2026-06-30T09:00:00Z",
                      {"critical": 0, "high": 0, "medium": 1, "low": 3}),
        RegistryImage(repo, "latest", "sha256:def456", 148_000_000, "2026-06-29T18:00:00Z",
                      {"critical": 0, "high": 1, "medium": 2, "low": 4}),
    ]


class _SimRegistryProvider(ArtifactRegistryProvider):
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def list_repositories(self, secret: dict) -> list[RegistryRepository]:
        return _sim_repos(self.provider)

    def list_images(self, secret: dict, repository: str) -> list[RegistryImage]:
        return _sim_images(repository)
