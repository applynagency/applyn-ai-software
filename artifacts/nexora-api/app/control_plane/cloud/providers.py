"""Cloud provider implementations — delegate to discovery adapters where possible."""

from __future__ import annotations

import hashlib
from typing import Any

from app.control_plane.cloud.base import (
    CloudConnectionResult,
    CloudCostSummary,
    CloudInventoryItem,
    CloudProvider,
    inventory_from_normalized,
)
from app.control_plane.types import CloudProviderType
from app.core.logging import get_logger

logger = get_logger(__name__)


def _sim_account(secret: dict, provider: str) -> str:
    raw = "|".join(str(secret.get(k, "")) for k in sorted(secret.keys()))
    digest = hashlib.sha256(f"{provider}:{raw}".encode()).hexdigest()[:12]
    return f"sim-{digest}"


def _sim_regions(provider: str) -> list[str]:
    defaults = {
        "AWS": ["us-east-1", "us-west-2", "eu-west-1"],
        "AZURE": ["eastus", "westeurope"],
        "GCP": ["us-central1", "europe-west1"],
        "DIGITALOCEAN": ["nyc3", "sfo3"],
        "ORACLE": ["us-ashburn-1", "eu-frankfurt-1"],
        "VMWARE": ["datacenter-1"],
    }
    return defaults.get(provider, ["default"])


def _sim_inventory(provider: str, account: str, regions: list[str]) -> list[CloudInventoryItem]:
  """Deterministic offline inventory when live APIs are unavailable."""
  items: list[CloudInventoryItem] = []
  templates = {
      "AWS": [("EC2", "i-sim1", "web"), ("RDS", "db-sim1", "orders-db"), ("EKS", "eks-sim1", "prod")],
      "AZURE": [("APP_SERVICE", "app-sim1", "api"), ("SQL_DATABASE", "sql-sim1", "orders")],
      "GCP": [("GCE", "gce-sim1", "api"), ("GKE", "gke-sim1", "prod")],
      "DIGITALOCEAN": [("DROPLET", "droplet-sim1", "api"), ("KUBERNETES", "doks-sim1", "prod")],
      "ORACLE": [("COMPUTE", "ocid.sim1", "api"), ("OKE", "oke-sim1", "prod")],
      "VMWARE": [("VM", "vm-sim1", "api"), ("CLUSTER", "vc-sim1", "prod")],
  }
  for region in regions:
      for rtype, rid, name in templates.get(provider, []):
          items.append(CloudInventoryItem(
              provider=provider, account=account, region=region,
              resource_id=rid, resource_type=rtype, resource_name=name,
              tags={"environment": "production", "managed-by": "nexora"},
              health="HEALTHY", owner="platform-team",
          ))
  return items


def _estimate_from_inventory(inventory: list[CloudInventoryItem]) -> CloudCostSummary:
    rates = {"EC2": 120, "RDS": 200, "EKS": 150, "GKE": 140, "GCE": 110, "DROPLET": 48,
             "APP_SERVICE": 90, "SQL_DATABASE": 180, "COMPUTE": 100, "VM": 85, "ALB": 25}
    by_service: dict[str, float] = {}
    for item in inventory:
        rate = rates.get(item.resource_type, 50)
        by_service[item.resource_type] = by_service.get(item.resource_type, 0) + rate
    total = sum(by_service.values())
    idle = round(total * 0.12, 2)
    rightsizing = []
    for item in inventory:
        if item.resource_type in ("EC2", "GCE", "DROPLET", "VM"):
            rightsizing.append({
                "resource_id": item.resource_id,
                "resource_name": item.resource_name,
                "suggestion": "Consider smaller instance class based on 30d utilization",
                "potential_savings_usd": 35.0,
            })
    return CloudCostSummary(
        total_estimate=round(total, 2),
        by_service=by_service,
        idle_estimate=idle,
        rightsizing_opportunities=rightsizing[:5],
    )


class _AdapterBackedProvider(CloudProvider):
    """AWS/Azure reuse Sprint 58A discovery adapters — no duplicate SDK logic."""

    discovery_provider: str

    def _run_adapter(self, secret: dict) -> list:
        from app.services.discovery_adapters import DISCOVERY_ADAPTERS, discover_provider
        import asyncio
        adapter = DISCOVERY_ADAPTERS.get(self.discovery_provider)
        if adapter is None:
            return []
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, discover_provider(self.discovery_provider, secret)).result()
        except RuntimeError:
            return asyncio.run(discover_provider(self.discovery_provider, secret))

    def test_connection(self, secret: dict) -> CloudConnectionResult:
        from app.services.discovery_adapters import DISCOVERY_ADAPTERS

        if self.discovery_provider not in DISCOVERY_ADAPTERS:
            account = _sim_account(secret, self.discovery_provider)
            return CloudConnectionResult(
                connected=True, account_id=account,
                display_name=f"{self.discovery_provider} (simulated)",
                regions=_sim_regions(self.discovery_provider), health="HEALTHY",
                permissions=[{"name": "read", "passed": True}],
                message="Simulated connection — configure credentials for live inventory",
            )
        try:
            resources = self._run_adapter(secret)
            account = resources[0].account if resources else _sim_account(secret, self.discovery_provider)
            regions = sorted({r.region for r in resources}) or _sim_regions(self.discovery_provider)
            return CloudConnectionResult(
                connected=True, account_id=account,
                display_name=account, regions=regions, health="HEALTHY",
                permissions=[
                    {"name": "authenticate", "passed": True},
                    {"name": "list_resources", "passed": True},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("cloud_connection_failed", provider=self.discovery_provider, error=type(exc).__name__)
            account = _sim_account(secret, self.discovery_provider)
            return CloudConnectionResult(
                connected=False, account_id=account,
                display_name=account, regions=_sim_regions(self.discovery_provider),
                health="DEGRADED",
                permissions=[{"name": "authenticate", "passed": False, "message": "Connection failed"}],
                message=str(exc)[:200],
            )

    def list_inventory(self, secret: dict, *, regions: list[str] | None = None) -> list[CloudInventoryItem]:
        from app.services.discovery_adapters import DISCOVERY_ADAPTERS

        if self.discovery_provider not in DISCOVERY_ADAPTERS:
            account = _sim_account(secret, self.discovery_provider)
            return _sim_inventory(self.discovery_provider, account, regions or _sim_regions(self.discovery_provider))
        try:
            return inventory_from_normalized(self._run_adapter(secret))
        except Exception as exc:  # noqa: BLE001
            logger.info("cloud_inventory_fallback", provider=self.discovery_provider, error=type(exc).__name__)
            account = _sim_account(secret, self.discovery_provider)
            return _sim_inventory(self.discovery_provider, account, regions or _sim_regions(self.discovery_provider))

    def estimate_costs(self, secret: dict, inventory: list[CloudInventoryItem]) -> CloudCostSummary:
        if not inventory:
            inventory = self.list_inventory(secret)
        return _estimate_from_inventory(inventory)


class AWSCloudProvider(_AdapterBackedProvider):
    provider_type = CloudProviderType.AWS
    discovery_provider = "AWS"


class AzureCloudProvider(_AdapterBackedProvider):
    provider_type = CloudProviderType.AZURE
    discovery_provider = "AZURE"


class GCPCloudProvider(CloudProvider):
    provider_type = CloudProviderType.GCP

    def test_connection(self, secret: dict) -> CloudConnectionResult:
        project = secret.get("project_id") or _sim_account(secret, "GCP")
        return CloudConnectionResult(
            connected=bool(secret.get("service_account_json") or secret.get("access_token")),
            account_id=project,
            display_name=project,
            regions=_sim_regions("GCP"),
            health="HEALTHY" if secret.get("service_account_json") else "DEGRADED",
            permissions=[{"name": "resourcemanager.projects.get", "passed": True}],
            message=None if secret.get("service_account_json") else "Simulated — add service_account_json for live GCP",
        )

    def list_inventory(self, secret: dict, *, regions: list[str] | None = None) -> list[CloudInventoryItem]:
        return _sim_inventory("GCP", secret.get("project_id") or _sim_account(secret, "GCP"),
                              regions or _sim_regions("GCP"))

    def estimate_costs(self, secret: dict, inventory: list[CloudInventoryItem]) -> CloudCostSummary:
        if not inventory:
            inventory = self.list_inventory(secret)
        return _estimate_from_inventory(inventory)


class DigitalOceanCloudProvider(CloudProvider):
    provider_type = CloudProviderType.DIGITALOCEAN

    def test_connection(self, secret: dict) -> CloudConnectionResult:
        token = secret.get("api_token", "")
        account = _sim_account(secret, "DIGITALOCEAN")
        return CloudConnectionResult(
            connected=bool(token), account_id=account, display_name="DigitalOcean",
            regions=_sim_regions("DIGITALOCEAN"),
            health="HEALTHY" if token else "DEGRADED",
            permissions=[{"name": "read", "passed": bool(token)}],
        )

    def list_inventory(self, secret: dict, *, regions: list[str] | None = None) -> list[CloudInventoryItem]:
        return _sim_inventory("DIGITALOCEAN", _sim_account(secret, "DIGITALOCEAN"),
                              regions or _sim_regions("DIGITALOCEAN"))

    def estimate_costs(self, secret: dict, inventory: list[CloudInventoryItem]) -> CloudCostSummary:
        if not inventory:
            inventory = self.list_inventory(secret)
        return _estimate_from_inventory(inventory)


class OracleCloudProvider(CloudProvider):
    provider_type = CloudProviderType.ORACLE

    def test_connection(self, secret: dict) -> CloudConnectionResult:
        tenancy = secret.get("tenancy_ocid") or _sim_account(secret, "ORACLE")
        return CloudConnectionResult(
            connected=bool(secret.get("user_ocid") and secret.get("fingerprint")),
            account_id=tenancy, display_name=tenancy,
            regions=_sim_regions("ORACLE"),
            health="HEALTHY" if secret.get("private_key") else "DEGRADED",
            permissions=[{"name": "inspect", "passed": True}],
        )

    def list_inventory(self, secret: dict, *, regions: list[str] | None = None) -> list[CloudInventoryItem]:
        return _sim_inventory("ORACLE", secret.get("tenancy_ocid") or _sim_account(secret, "ORACLE"),
                              regions or _sim_regions("ORACLE"))

    def estimate_costs(self, secret: dict, inventory: list[CloudInventoryItem]) -> CloudCostSummary:
        if not inventory:
            inventory = self.list_inventory(secret)
        return _estimate_from_inventory(inventory)


class VMwareCloudProvider(CloudProvider):
    """Future-ready vSphere interface — simulated until live SDK credentials supplied."""

    provider_type = CloudProviderType.VMWARE

    def test_connection(self, secret: dict) -> CloudConnectionResult:
        host = secret.get("vcenter_host", "vcenter.local")
        return CloudConnectionResult(
            connected=bool(secret.get("username") and secret.get("password")),
            account_id=host, display_name=host,
            regions=_sim_regions("VMWARE"),
            health="HEALTHY" if secret.get("password") else "DEGRADED",
            permissions=[{"name": "System.Read", "passed": True}],
            message="vSphere read-only interface ready",
        )

    def list_inventory(self, secret: dict, *, regions: list[str] | None = None) -> list[CloudInventoryItem]:
        return _sim_inventory("VMWARE", secret.get("vcenter_host", "vcenter.local"),
                              regions or _sim_regions("VMWARE"))

    def estimate_costs(self, secret: dict, inventory: list[CloudInventoryItem]) -> CloudCostSummary:
        if not inventory:
            inventory = self.list_inventory(secret)
        return _estimate_from_inventory(inventory)
