"""Kubernetes distribution registry."""

from __future__ import annotations

from app.control_plane.kubernetes.base import ClusterConnectionInfo, ClusterProvider, DiscoveredResource
from app.control_plane.kubernetes import discovery, operations
from app.control_plane.types import ClusterDistribution


class _VanillaClusterProvider(ClusterProvider):
    """All distributions share the Kubernetes API — metadata differs only."""

    def __init__(self, distribution: ClusterDistribution) -> None:
        self.distribution = distribution

    def connect(self, secret: dict) -> ClusterConnectionInfo:
        if not secret.get("kubeconfig"):
            return ClusterConnectionInfo(
                connected=False, api_endpoint=None, version="v1.29.0",
                distribution=self.distribution, node_count=3, namespace_count=5,
                health="DEGRADED", message="Simulated cluster — attach kubeconfig",
            )
        try:
            from app.control_plane.kubernetes.client import open_client
            bundle = open_client(secret)
            try:
                ver = bundle.version.get_code().git_version
                nodes = len(bundle.core.list_node(limit=100).items)
                namespaces = len(bundle.core.list_namespace(limit=100).items)
                return ClusterConnectionInfo(
                    connected=True, api_endpoint=bundle.cluster_name, version=ver,
                    distribution=self.distribution, node_count=nodes,
                    namespace_count=namespaces, health="HEALTHY",
                )
            finally:
                bundle.cleanup()
        except Exception as exc:  # noqa: BLE001
            return ClusterConnectionInfo(
                connected=False, api_endpoint=None, version=None,
                distribution=self.distribution, health="UNREACHABLE",
                message=str(exc)[:200],
            )

    def discover(self, secret: dict) -> list[DiscoveredResource]:
        from app.control_plane.kubernetes.discovery import discover_cluster_sync
        return discover_cluster_sync(secret, cluster_name=self.distribution.value)

    def execute_read(self, secret: dict, action: str, params: dict) -> dict:
        import asyncio
        return asyncio.run(operations.execute_read(secret, action, params))

    def execute_write(self, secret: dict, action: str, params: dict) -> dict:
        import asyncio
        return asyncio.run(operations.execute_write(secret, action, params))


_REGISTRY: dict[ClusterDistribution, ClusterProvider] = {
    d: _VanillaClusterProvider(d) for d in ClusterDistribution
}


def get_cluster_provider(distribution: str | ClusterDistribution) -> ClusterProvider:
    key = ClusterDistribution(distribution) if isinstance(distribution, str) else distribution
    return _REGISTRY[key]


def supported_distributions() -> list[str]:
    return [d.value for d in ClusterDistribution]
