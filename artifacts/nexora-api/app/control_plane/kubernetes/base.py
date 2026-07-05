"""Kubernetes cluster provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.control_plane.types import ClusterDistribution


@dataclass
class ClusterConnectionInfo:
    connected: bool
    api_endpoint: str | None
    version: str | None
    distribution: ClusterDistribution
    node_count: int = 0
    namespace_count: int = 0
    health: str = "UNKNOWN"
    message: str | None = None


@dataclass
class DiscoveredResource:
    kind: str
    namespace: str | None
    name: str
    uid: str
    labels: dict = field(default_factory=dict)
    annotations: dict = field(default_factory=dict)
    health: str = "UNKNOWN"
    metadata: dict = field(default_factory=dict)


class ClusterProvider(ABC):
    """Every Kubernetes distribution implements this interface."""

    distribution: ClusterDistribution

    @abstractmethod
    def connect(self, secret: dict) -> ClusterConnectionInfo:
        """Validate kubeconfig and return cluster metadata."""

    @abstractmethod
    def discover(self, secret: dict) -> list[DiscoveredResource]:
        """Live read-only discovery of cluster resources."""

    @abstractmethod
    def execute_read(self, secret: dict, action: str, params: dict) -> dict:
        """Non-mutating operations: logs, describe, top, events, rollout status."""

    @abstractmethod
    def execute_write(self, secret: dict, action: str, params: dict) -> dict:
        """Mutating operations — only called after approval."""
