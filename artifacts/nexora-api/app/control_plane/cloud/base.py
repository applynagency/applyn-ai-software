"""Cloud provider abstraction — one interface, no duplicated provider logic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.control_plane.types import CloudProviderType


@dataclass
class CloudConnectionResult:
    connected: bool
    account_id: str
    display_name: str
    regions: list[str] = field(default_factory=list)
    health: str = "UNKNOWN"
    permissions: list[dict] = field(default_factory=list)
    message: str | None = None


@dataclass
class CloudInventoryItem:
    provider: str
    account: str
    region: str
    resource_id: str
    resource_type: str
    resource_name: str
    tags: dict = field(default_factory=dict)
    health: str = "UNKNOWN"
    owner: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class CloudCostSummary:
    currency: str = "USD"
    period_days: int = 30
    total_estimate: float = 0.0
    by_service: dict[str, float] = field(default_factory=dict)
    idle_estimate: float = 0.0
    rightsizing_opportunities: list[dict] = field(default_factory=list)


class CloudProvider(ABC):
    """Every cloud vendor implements this interface."""

    provider_type: CloudProviderType

    @abstractmethod
    def test_connection(self, secret: dict) -> CloudConnectionResult:
        """Validate credentials, regions, and permissions."""

    @abstractmethod
    def list_inventory(self, secret: dict, *, regions: list[str] | None = None) -> list[CloudInventoryItem]:
        """Read-only resource inventory."""

    @abstractmethod
    def estimate_costs(self, secret: dict, inventory: list[CloudInventoryItem]) -> CloudCostSummary:
        """Heuristic cost visibility (not billing integration)."""

    def validate_permissions(self, secret: dict) -> list[dict]:
        """Optional permission matrix; default derives from connection test."""
        result = self.test_connection(secret)
        return result.permissions


def inventory_from_normalized(resources: list) -> list[CloudInventoryItem]:
    """Map discovery adapter NormalizedResource rows to control-plane inventory."""
    items: list[CloudInventoryItem] = []
    for r in resources:
        d = r.to_dict() if hasattr(r, "to_dict") else r
        items.append(CloudInventoryItem(
            provider=d.get("provider", ""),
            account=d.get("account", ""),
            region=d.get("region", ""),
            resource_id=d.get("resource_id", ""),
            resource_type=d.get("resource_type", ""),
            resource_name=d.get("resource_name", ""),
            tags=d.get("tags") or {},
            health=d.get("health", "UNKNOWN"),
            owner=d.get("owner"),
            metadata=d.get("metadata") or {},
        ))
    return items
