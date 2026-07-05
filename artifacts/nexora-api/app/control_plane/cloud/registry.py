"""Cloud provider registry — single lookup, no duplicated wiring."""

from __future__ import annotations

from app.control_plane.cloud.base import CloudProvider
from app.control_plane.cloud.providers import (
    AWSCloudProvider,
    AzureCloudProvider,
    DigitalOceanCloudProvider,
    GCPCloudProvider,
    OracleCloudProvider,
    VMwareCloudProvider,
)
from app.control_plane.types import CloudProviderType

_REGISTRY: dict[CloudProviderType, CloudProvider] = {
    CloudProviderType.AWS: AWSCloudProvider(),
    CloudProviderType.AZURE: AzureCloudProvider(),
    CloudProviderType.GCP: GCPCloudProvider(),
    CloudProviderType.DIGITALOCEAN: DigitalOceanCloudProvider(),
    CloudProviderType.ORACLE: OracleCloudProvider(),
    CloudProviderType.VMWARE: VMwareCloudProvider(),
}


def get_cloud_provider(provider: str | CloudProviderType) -> CloudProvider:
    key = CloudProviderType(provider) if isinstance(provider, str) else provider
    impl = _REGISTRY.get(key)
    if impl is None:
        raise ValueError(f"unsupported cloud provider: {provider}")
    return impl


def supported_cloud_providers() -> list[str]:
    return [p.value for p in CloudProviderType]
