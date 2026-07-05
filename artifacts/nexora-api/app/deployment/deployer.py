from abc import ABC, abstractmethod

from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput

DEPLOYER_VERSION = "1.0.0"


class BaseDeploymentProvider(ABC):
    @abstractmethod
    def deploy(
        self,
        *,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
        deployment_target: dict | None = None,
    ) -> DeploymentOutput:
        raise NotImplementedError


class AzureAppServiceProvider(BaseDeploymentProvider):
    """Azure App Service deployment provider (simulated deterministic deploy)."""

    def deploy(
        self,
        *,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
        deployment_target: dict | None = None,
    ) -> DeploymentOutput:
        manifest = fullstack_assembly_output.get("application_manifest") or {}
        docker_assets = fullstack_assembly_output.get("docker_assets") or {}
        deployment_assets = fullstack_assembly_output.get("deployment_assets") or {}

        slug = app_name.replace("_", "-").lower()
        live_url = f"https://{slug}.applyn.app"

        logs = [
            f"Initializing Azure App Service deployment for {app_name}",
            f"Environment: {environment}",
            "Validating approval package and assembly artifacts",
            "Provisioning Azure App Service plan (simulated)",
            "Uploading container image from assembly docker assets",
            "Configuring environment variables",
            "Starting App Service instance",
            f"Health check passed — application available at {live_url}",
        ]

        rollback_metadata = {
            "provider": DeploymentProvider.AZURE.value,
            "previous_revision": "rev-001",
            "target_revision": "rev-002",
            "rollback_command": f"az webapp deployment slot swap --name {slug} --resource-group applyn-rg",
        }

        return DeploymentOutput(
            deployment_provider=DeploymentProvider.AZURE.value,
            deployment_status=DeploymentStatus.DEPLOYED.value,
            live_url=live_url,
            deployment_logs=logs,
            rollback_available=True,
            deployment_metadata={
                "provider": DeploymentProvider.AZURE.value,
                "service_type": "app-service",
                "app_name": app_name,
                "environment": environment,
                "region": "eastus",
                "resource_group": "applyn-rg",
                "deployment_strategy": (manifest.get("deployment") or {}).get(
                    "strategy", "docker-compose"
                ),
                "docker_configured": bool(docker_assets),
                "kubernetes_assets": bool(deployment_assets.get("kubernetes")),
                "approval_recommendation": approval_output.get("recommendation"),
                "assembly_status": (approval_output.get("approval_summary") or {}).get(
                    "review_summary", {}
                ).get("assembly_status"),
            },
        )

    def rollback(
        self,
        *,
        app_name: str,
        rollback_metadata: dict,
        environment: str,
        deployment_target: dict | None = None,
    ) -> tuple[DeploymentOutput, list[str]]:
        slug = app_name.replace("_", "-").lower()
        live_url = f"https://{slug}-rollback.applyn.app"

        logs = [
            f"Starting rollback for {app_name} in {environment}",
            f"Reverting to revision {rollback_metadata.get('previous_revision', 'rev-001')}",
            "Swapping deployment slot (simulated)",
            f"Rollback complete — previous version available at {live_url}",
        ]

        output = DeploymentOutput(
            deployment_provider=DeploymentProvider.AZURE.value,
            deployment_status=DeploymentStatus.ROLLED_BACK.value,
            live_url=live_url,
            deployment_logs=logs,
            rollback_available=False,
            deployment_metadata={
                "provider": DeploymentProvider.AZURE.value,
                "rollback_completed": True,
                "restored_revision": rollback_metadata.get("previous_revision", "rev-001"),
            },
        )
        return output, logs


# Sprint 33B: the AZURE provider now performs a real Azure Container Apps
# deployment when the environment is configured, and transparently falls back to
# the deterministic simulated provider otherwise.
#
# The registry is populated lazily (rather than at import time) to avoid a
# circular import: ``azure_container_apps`` imports ``BaseDeploymentProvider``
# and ``AzureAppServiceProvider`` from this module.
PROVIDER_REGISTRY: dict[str, "BaseDeploymentProvider"] = {}


def _ensure_registry() -> dict[str, "BaseDeploymentProvider"]:
    if not PROVIDER_REGISTRY:
        from app.deployment.azure_container_apps import AzureContainerAppsProvider
        from app.deployment.kubernetes_provider import KubernetesDeploymentProvider
        from app.deployment.vm_provider import VMDeploymentProvider

        PROVIDER_REGISTRY[DeploymentProvider.AZURE.value] = AzureContainerAppsProvider()
        PROVIDER_REGISTRY[DeploymentProvider.VM.value] = VMDeploymentProvider()
        PROVIDER_REGISTRY[DeploymentProvider.KUBERNETES.value] = KubernetesDeploymentProvider()
    return PROVIDER_REGISTRY


class DeploymentDeployer:
    """Orchestrates deployment across cloud providers."""

    def deploy(
        self,
        *,
        provider: str,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
        deployment_target: dict | None = None,
    ) -> DeploymentOutput:
        registry = _ensure_registry()
        if provider not in registry:
            raise ValueError(f"Unsupported deployment provider: {provider}")

        provider_impl = registry[provider]
        return provider_impl.deploy(
            fullstack_assembly_output=fullstack_assembly_output,
            approval_output=approval_output,
            app_name=app_name,
            environment=environment,
            deployment_target=deployment_target,
        )

    def rollback(
        self,
        *,
        provider: str,
        app_name: str,
        rollback_metadata: dict,
        environment: str,
        deployment_target: dict | None = None,
    ) -> tuple[DeploymentOutput, list[str]]:
        registry = _ensure_registry()
        if provider not in registry:
            raise ValueError(f"Unsupported deployment provider: {provider}")

        provider_impl = registry[provider]
        if not hasattr(provider_impl, "rollback"):
            raise ValueError(f"Rollback not implemented for provider: {provider}")
        return provider_impl.rollback(
            app_name=app_name,
            rollback_metadata=rollback_metadata,
            environment=environment,
            deployment_target=deployment_target,
        )

    @staticmethod
    def get_deployer_version() -> str:
        return DEPLOYER_VERSION

    @staticmethod
    def supported_providers() -> list[str]:
        return list(_ensure_registry().keys())
