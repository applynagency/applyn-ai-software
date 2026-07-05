"""Sprint 33B — Real Azure Container Apps deployment provider.

This module replaces the simulated deployment layer with a real implementation
that:

1. Builds a container image from the assembled application source using
   **Azure Container Registry Build Tasks** (no local Docker daemon required).
2. Pushes the image to Azure Container Registry (ACR).
3. Creates or updates an **Azure Container App** with the new image, injecting
   environment variables and the application's startup port.
4. Performs real HTTP health verification against the live ingress URL.
5. Returns a real ``live_url``, the real Container Apps **revision** name, and
   rollback metadata (previous / target revision) for revision-based rollback.

The provider keeps the existing ``BaseDeploymentProvider`` contract. When the
required Azure configuration is not present (local / CI / test environments),
it transparently delegates to the deterministic simulated provider so that all
existing behaviour, APIs, and tests are preserved.

All ``azure-*`` SDK imports are performed lazily inside methods so importing
this module never fails when the SDKs are not installed.
"""

from __future__ import annotations

import gzip
import io
import re
import tarfile
import time
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.deployment.deployer import AzureAppServiceProvider, BaseDeploymentProvider
from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput

logger = get_logger(__name__)

REQUIRED_SETTINGS = (
    "AZURE_SUBSCRIPTION_ID",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "ACR_NAME",
    "ACR_LOGIN_SERVER",
    "CONTAINER_APPS_ENVIRONMENT",
)

# Service-principal auth fields a customer Azure credential must carry. When all
# four are present in the (decrypted) deployment_target, the deploy authenticates
# as that customer instead of the global platform service principal.
AZURE_AUTH_FIELDS = ("subscription_id", "tenant_id", "client_id", "client_secret")

_DEFAULT_PORT = 8000


def azure_deployment_configured() -> bool:
    """True when every credential/resource required for a real deploy is set."""
    return all(getattr(settings, name, None) for name in REQUIRED_SETTINGS)


@dataclass
class AzureDeployConfig:
    """Resolved, per-deployment Azure authentication + target resources.

    ``source`` records whether the values came from the customer credential
    (``"customer"``) or the global platform settings (``"platform"``). Only
    non-secret identifiers from this object are ever persisted/logged; the
    ``client_secret`` is used transiently to build the SDK credential and is
    never written to a deployment run, log line, or audit record.
    """

    subscription_id: str
    tenant_id: str
    client_id: str
    client_secret: str
    resource_group: str
    region: str
    acr_name: str | None
    acr_login_server: str | None
    container_apps_environment: str | None
    app_base_domain: str | None
    source: str


def _target_has_azure_credentials(target: dict | None) -> bool:
    t = target or {}
    return all(t.get(field) for field in AZURE_AUTH_FIELDS)


def resolve_azure_config(deployment_target: dict | None) -> AzureDeployConfig | None:
    """Resolve the Azure config for a deploy.

    Priority:
    1. Customer credential supplied via ``deployment_target`` (BYOI) — uses the
       customer's service principal; target resources (resource group, ACR,
       Container Apps environment, region, base domain) come from the credential
       when present, otherwise fall back to the platform defaults.
    2. Global platform service principal (``settings.AZURE_*``) when fully
       configured and no customer credential was supplied.
    3. ``None`` — neither is available, so the caller uses the simulated provider.
    """
    target = deployment_target or {}
    if _target_has_azure_credentials(target):
        return AzureDeployConfig(
            subscription_id=target["subscription_id"],
            tenant_id=target["tenant_id"],
            client_id=target["client_id"],
            client_secret=target["client_secret"],
            resource_group=target.get("resource_group") or settings.AZURE_RESOURCE_GROUP,
            region=target.get("region") or settings.AZURE_REGION,
            acr_name=target.get("acr_name") or settings.ACR_NAME,
            acr_login_server=target.get("acr_login_server") or settings.ACR_LOGIN_SERVER,
            container_apps_environment=(
                target.get("container_apps_environment")
                or settings.CONTAINER_APPS_ENVIRONMENT
            ),
            app_base_domain=target.get("app_base_domain") or settings.APP_BASE_DOMAIN,
            source="customer",
        )
    if azure_deployment_configured():
        return AzureDeployConfig(
            subscription_id=settings.AZURE_SUBSCRIPTION_ID,
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            client_secret=settings.AZURE_CLIENT_SECRET,
            resource_group=settings.AZURE_RESOURCE_GROUP,
            region=settings.AZURE_REGION,
            acr_name=settings.ACR_NAME,
            acr_login_server=settings.ACR_LOGIN_SERVER,
            container_apps_environment=settings.CONTAINER_APPS_ENVIRONMENT,
            app_base_domain=settings.APP_BASE_DOMAIN,
            source="platform",
        )
    return None


def _slugify(app_name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", (app_name or "application").lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "application"


def _mask(value: str | None) -> str:
    """Mask an identifier for logging (keeps only the last 4 characters)."""
    if not value:
        return "****"
    return f"****{value[-4:]}"


class AzureContainerAppsProvider(BaseDeploymentProvider):
    """Deploys applications to Azure Container Apps via ACR Build Tasks.

    Falls back to the simulated :class:`AzureAppServiceProvider` whenever the
    Azure environment is not fully configured, preserving the existing
    contract and deterministic test behaviour.
    """

    def __init__(self) -> None:
        # Simulated provider used as the deterministic fallback (and in tests).
        self._simulated = AzureAppServiceProvider()

    # ------------------------------------------------------------------ #
    # Public contract
    # ------------------------------------------------------------------ #
    def deploy(
        self,
        *,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
        deployment_target: dict | None = None,
    ) -> DeploymentOutput:
        # Sprint 36A: prefer the customer credential supplied via credential_id
        # (resolved into deployment_target) over the global platform settings.
        config = resolve_azure_config(deployment_target)
        if config is None:
            logger.info("azure_container_apps_fallback_simulated", reason="not_configured")
            return self._simulated.deploy(
                fullstack_assembly_output=fullstack_assembly_output,
                approval_output=approval_output,
                app_name=app_name,
                environment=environment,
            )
        logger.info("azure_container_apps_real_deploy", auth_source=config.source)
        return self._real_deploy(
            config=config,
            fullstack_assembly_output=fullstack_assembly_output,
            approval_output=approval_output,
            app_name=app_name,
            environment=environment,
        )

    def rollback(
        self,
        *,
        app_name: str,
        rollback_metadata: dict,
        environment: str,
        deployment_target: dict | None = None,
    ) -> tuple[DeploymentOutput, list[str]]:
        config = resolve_azure_config(deployment_target)
        if config is None:
            return self._simulated.rollback(
                app_name=app_name,
                rollback_metadata=rollback_metadata,
                environment=environment,
            )
        return self._real_rollback(
            config=config,
            app_name=app_name,
            rollback_metadata=rollback_metadata,
            environment=environment,
        )

    # ------------------------------------------------------------------ #
    # Sprint 41C — approval-gated remediation operations.
    # These use the CUSTOMER service principal only (no platform fallback):
    # remediation must never act with platform credentials.
    # ------------------------------------------------------------------ #
    def remediation_rollback_revision(
        self,
        *,
        container_app_name: str,
        deployment_target: dict | None = None,
        previous_revision: str | None = None,
    ) -> tuple[str, dict]:
        if not _target_has_azure_credentials(deployment_target):
            raise ValueError("A customer Azure credential is required for remediation")
        config = resolve_azure_config(deployment_target)
        if not container_app_name:
            raise ValueError("application (container app name) is required")
        credential, _ = self._credential(config)
        from azure.mgmt.appcontainers import ContainerAppsAPIClient

        client = ContainerAppsAPIClient(credential, config.subscription_id)
        rg = config.resource_group
        current = getattr(
            client.container_apps.get(rg, container_app_name), "latest_revision_name", None
        )
        target_revision = previous_revision
        if not target_revision:
            revs = list(client.container_apps_revisions.list_revisions(rg, container_app_name))
            actives = [r for r in revs if getattr(r, "name", None) and r.name != current]
            actives.sort(key=lambda r: getattr(r, "created_time", None) or 0, reverse=True)
            target_revision = actives[0].name if actives else None
        if not target_revision:
            raise ValueError("No previous Container App revision available to roll back to")
        logs: list[str] = []
        self._activate_revision(
            credential=credential,
            config=config,
            container_app_name=container_app_name,
            target_revision=target_revision,
            previous_revision=current or "",
            logs=logs,
        )
        return (
            f"Container App {container_app_name} rolled back to revision {target_revision}.",
            {"restored_revision": target_revision, "previous_revision": current},
        )

    def remediation_restart(
        self, *, container_app_name: str, deployment_target: dict | None = None
    ) -> tuple[str, dict]:
        if not _target_has_azure_credentials(deployment_target):
            raise ValueError("A customer Azure credential is required for remediation")
        config = resolve_azure_config(deployment_target)
        if not container_app_name:
            raise ValueError("application (container app name) is required")
        credential, _ = self._credential(config)
        from azure.mgmt.appcontainers import ContainerAppsAPIClient

        client = ContainerAppsAPIClient(credential, config.subscription_id)
        rg = config.resource_group
        revision = getattr(
            client.container_apps.get(rg, container_app_name), "latest_revision_name", None
        )
        if not revision:
            raise ValueError("No active revision found to restart")
        client.container_apps_revisions.restart_revision(rg, container_app_name, revision)
        return (
            f"Container App {container_app_name} restarted (revision {revision}).",
            {"restarted_revision": revision},
        )

    # ------------------------------------------------------------------ #
    # Real deployment flow
    # ------------------------------------------------------------------ #
    def _real_deploy(
        self,
        *,
        config: AzureDeployConfig,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
    ) -> DeploymentOutput:
        logs: list[str] = []
        slug = _slugify(app_name)
        container_app_name = f"{slug}-{environment}"[:32].strip("-")
        image_tag = uuid.uuid4().hex[:12]
        repository = slug

        logs.append(
            f"Authenticating to Azure with {config.source} service principal "
            f"(subscription {_mask(config.subscription_id)})"
        )
        logs.append(f"Preparing build context for {app_name} ({environment})")
        context = self._build_context(fullstack_assembly_output)
        logs.append(
            f"Build context ready: {len(context['files'])} files, "
            f"target port {context['port']}"
        )

        try:
            self._require_resources(config)
            image_ref = f"{config.acr_login_server}/{repository}:{image_tag}"
            credential, subscription_id = self._credential(config)

            self._acr_build_and_push(
                credential=credential,
                config=config,
                context_files=context["files"],
                image_name=f"{repository}:{image_tag}",
                logs=logs,
            )
            logs.append(f"Image pushed to ACR: {image_ref}")

            previous_revision, fqdn, new_revision = self._create_or_update_container_app(
                credential=credential,
                config=config,
                container_app_name=container_app_name,
                image_ref=image_ref,
                env_vars=context["env_vars"],
                target_port=context["port"],
                logs=logs,
            )

            live_url = self._compose_live_url(fqdn, container_app_name, config)
            logs.append(f"Container App revision active: {new_revision}")
            logs.append(f"Live URL: {live_url}")

            healthy = self._wait_for_health(live_url, context["health_path"], logs)
        except Exception as exc:  # noqa: BLE001 — surfaced as FAILED deployment
            logger.error("azure_container_apps_deploy_failed", error=str(exc))
            logs.append(f"Deployment failed: {exc}")
            return DeploymentOutput(
                deployment_provider=DeploymentProvider.AZURE.value,
                deployment_status=DeploymentStatus.FAILED.value,
                live_url="",
                deployment_logs=logs,
                rollback_available=False,
                deployment_metadata={
                    "provider": DeploymentProvider.AZURE.value,
                    "service_type": "container-apps",
                    "app_name": app_name,
                    "environment": environment,
                    "auth_source": config.source,
                    "error": str(exc),
                },
            )

        status = (
            DeploymentStatus.DEPLOYED.value if healthy else DeploymentStatus.FAILED.value
        )
        if healthy:
            logs.append(f"Health check passed — application available at {live_url}")
        else:
            logs.append("Health check did not return HTTP 200 within timeout")

        return DeploymentOutput(
            deployment_provider=DeploymentProvider.AZURE.value,
            deployment_status=status,
            live_url=live_url if healthy else "",
            deployment_logs=logs,
            rollback_available=healthy and bool(previous_revision),
            deployment_metadata={
                "provider": DeploymentProvider.AZURE.value,
                "service_type": "container-apps",
                "app_name": app_name,
                "container_app_name": container_app_name,
                "environment": environment,
                "region": config.region,
                "resource_group": config.resource_group,
                "image": image_ref,
                "revision": new_revision,
                "target_revision": new_revision,
                "previous_revision": previous_revision or "",
                "container_apps_environment": config.container_apps_environment,
                "auth_source": config.source,
                "approval_recommendation": approval_output.get("recommendation"),
            },
        )

    def _real_rollback(
        self,
        *,
        config: AzureDeployConfig,
        app_name: str,
        rollback_metadata: dict,
        environment: str,
    ) -> tuple[DeploymentOutput, list[str]]:
        logs: list[str] = []
        container_app_name = (
            rollback_metadata.get("container_app_name")
            or f"{_slugify(app_name)}-{environment}"[:32].strip("-")
        )
        target_revision = rollback_metadata.get("previous_revision") or ""
        current_revision = rollback_metadata.get("target_revision") or ""

        if not target_revision:
            raise ValueError("No previous revision recorded for rollback")

        logs.append(
            f"Rolling back {container_app_name} to revision {target_revision} "
            f"({config.source} credentials)"
        )

        credential, subscription_id = self._credential(config)
        fqdn = self._activate_revision(
            credential=credential,
            config=config,
            container_app_name=container_app_name,
            target_revision=target_revision,
            previous_revision=current_revision,
            logs=logs,
        )
        live_url = self._compose_live_url(fqdn, container_app_name, config)
        logs.append(f"Rollback complete — previous version active at {live_url}")

        output = DeploymentOutput(
            deployment_provider=DeploymentProvider.AZURE.value,
            deployment_status=DeploymentStatus.ROLLED_BACK.value,
            live_url=live_url,
            deployment_logs=logs,
            rollback_available=False,
            deployment_metadata={
                "provider": DeploymentProvider.AZURE.value,
                "service_type": "container-apps",
                "rollback_completed": True,
                "restored_revision": target_revision,
                "deactivated_revision": current_revision,
                "container_app_name": container_app_name,
            },
        )
        return output, logs

    # ------------------------------------------------------------------ #
    # Build context
    # ------------------------------------------------------------------ #
    def _build_context(self, fsa_output: dict) -> dict:
        """Assemble a flat {path: content} build context from the assembly output.

        The backend package is used as the primary deployable unit (it exposes a
        health endpoint and a Dockerfile). A Dockerfile is synthesised if the
        package does not ship one.
        """
        backend_pkg = fsa_output.get("backend_package") or {}
        generated_files = backend_pkg.get("generated_files") or []

        docker_assets = fsa_output.get("docker_assets") or {}
        docker_cfg = (docker_assets.get("docker_configuration") or {}).get("backend") or {}
        startup_cfg = (fsa_output.get("startup_configuration") or {}).get("backend") or {}
        health_cfg = (fsa_output.get("health_checks") or {}).get("backend") or {}

        port = (
            docker_cfg.get("port")
            or startup_cfg.get("port")
            or health_cfg.get("port")
            or _DEFAULT_PORT
        )
        health_path = health_cfg.get("path") or settings.DEPLOYMENT_HEALTH_PATH

        files: dict[str, str] = {}
        for item in generated_files:
            path = item.get("path") if isinstance(item, dict) else None
            if path:
                files[path] = item.get("content", "")

        if "requirements.txt" not in files:
            backend_v3_reqs = backend_pkg.get("requirements_txt")
            if backend_v3_reqs:
                files["requirements.txt"] = backend_v3_reqs

        if "Dockerfile" not in files:
            files["Dockerfile"] = self._default_dockerfile(port, startup_cfg.get("command"))

        env_vars: dict[str, str] = {}
        for item in fsa_output.get("environment_variables") or []:
            name = item.get("name") if isinstance(item, dict) else None
            if name:
                env_vars[name] = str(item.get("value", "")) if isinstance(item, dict) else ""
        env_vars.setdefault("PORT", str(port))

        return {
            "files": files,
            "port": int(port),
            "health_path": health_path,
            "env_vars": env_vars,
        }

    def _default_dockerfile(self, port: int, command: str | None) -> str:
        start = command or f"uvicorn app.main:app --host 0.0.0.0 --port {port}"
        cmd_list = ", ".join(f'"{part}"' for part in start.split())
        return (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY . .\n"
            f"EXPOSE {port}\n"
            f"CMD [{cmd_list}]\n"
        )

    def _make_tarball(self, files: dict[str, str]) -> bytes:
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w") as tar:
            for path, content in files.items():
                data = content.encode("utf-8")
                info = tarfile.TarInfo(name=path)
                info.size = len(data)
                info.mtime = int(time.time())
                tar.addfile(info, io.BytesIO(data))
        return gzip.compress(raw.getvalue())

    def _compose_live_url(
        self, fqdn: str | None, container_app_name: str, config: AzureDeployConfig
    ) -> str:
        if fqdn:
            return f"https://{fqdn}"
        if config.app_base_domain:
            return f"https://{container_app_name}.{config.app_base_domain}"
        return ""

    def _require_resources(self, config: AzureDeployConfig) -> None:
        """Ensure the target Azure resources are known before a real deploy.

        Auth alone is not enough; a real Container Apps deploy needs an ACR and a
        Container Apps environment. When a customer credential omits them (and no
        platform default exists) we fail with a clear, customer-safe message
        instead of attempting an unconfigured deploy.
        """
        missing = [
            label
            for label, value in (
                ("Azure Container Registry name", config.acr_name),
                ("Azure Container Registry login server", config.acr_login_server),
                ("Container Apps environment", config.container_apps_environment),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Azure deployment is missing required resources: "
                + ", ".join(missing)
                + ". Add them to your Azure credential to deploy."
            )

    # ------------------------------------------------------------------ #
    # Azure SDK interactions (lazy imports)
    # ------------------------------------------------------------------ #
    def _credential(self, config: AzureDeployConfig):
        from azure.identity import ClientSecretCredential

        credential = ClientSecretCredential(
            tenant_id=config.tenant_id,
            client_id=config.client_id,
            client_secret=config.client_secret,
        )
        return credential, config.subscription_id

    def _acr_build_and_push(
        self,
        *,
        credential,
        config: AzureDeployConfig,
        context_files: dict[str, str],
        image_name: str,
        logs: list[str],
    ) -> None:
        """Build & push an image using ACR Build Tasks (server-side build)."""
        import urllib.request

        from azure.mgmt.containerregistry import ContainerRegistryManagementClient
        from azure.mgmt.containerregistry.models import (
            DockerBuildRequest,
            PlatformProperties,
        )

        client = ContainerRegistryManagementClient(credential, config.subscription_id)

        logs.append("Requesting ACR source upload URL")
        upload = client.registries.get_build_source_upload_url(
            config.resource_group, config.acr_name
        )

        tarball = self._make_tarball(context_files)
        logs.append(f"Uploading build context ({len(tarball)} bytes) to ACR")
        request = urllib.request.Request(
            upload.upload_url,
            data=tarball,
            method="PUT",
            headers={
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": "application/gzip",
            },
        )
        urllib.request.urlopen(request, timeout=120).read()

        logs.append("Scheduling ACR Build Task (docker build + push)")
        build_request = DockerBuildRequest(
            image_names=[image_name],
            is_push_enabled=True,
            source_location=upload.relative_path,
            docker_file_path="Dockerfile",
            platform=PlatformProperties(os="Linux", architecture="amd64"),
        )
        poller = client.registries.begin_schedule_run(
            config.resource_group, config.acr_name, build_request
        )
        run = poller.result()
        status = getattr(run, "status", None)
        logs.append(f"ACR build status: {status}")
        if status and str(status).lower() != "succeeded":
            raise RuntimeError(f"ACR build did not succeed (status={status})")

    def _create_or_update_container_app(
        self,
        *,
        credential,
        config: AzureDeployConfig,
        container_app_name: str,
        image_ref: str,
        env_vars: dict[str, str],
        target_port: int,
        logs: list[str],
    ) -> tuple[str | None, str | None, str | None]:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.mgmt.appcontainers import ContainerAppsAPIClient
        from azure.mgmt.appcontainers.models import (
            Configuration,
            Container,
            ContainerApp,
            EnvironmentVar,
            Ingress,
            RegistryCredentials,
            Scale,
            Secret,
            Template,
        )

        client = ContainerAppsAPIClient(credential, config.subscription_id)
        rg = config.resource_group

        previous_revision: str | None = None
        try:
            existing = client.container_apps.get(rg, container_app_name)
            previous_revision = getattr(existing, "latest_revision_name", None)
            logs.append(f"Existing Container App found (revision {previous_revision})")
        except ResourceNotFoundError:
            logs.append("Creating new Container App")

        managed_env_id = (
            f"/subscriptions/{config.subscription_id}/resourceGroups/{rg}"
            f"/providers/Microsoft.App/managedEnvironments/"
            f"{config.container_apps_environment}"
        )

        container_env = [EnvironmentVar(name=k, value=v) for k, v in env_vars.items()]

        container_app = ContainerApp(
            location=config.region,
            managed_environment_id=managed_env_id,
            configuration=Configuration(
                active_revisions_mode="Multiple",
                ingress=Ingress(
                    external=True,
                    target_port=target_port,
                    transport="auto",
                ),
                secrets=[Secret(name="acr-password", value=config.client_secret)],
                registries=[
                    RegistryCredentials(
                        server=config.acr_login_server,
                        username=config.client_id,
                        password_secret_ref="acr-password",
                    )
                ],
            ),
            template=Template(
                containers=[
                    Container(
                        name=container_app_name,
                        image=image_ref,
                        env=container_env,
                    )
                ],
                scale=Scale(min_replicas=1, max_replicas=3),
            ),
        )

        logs.append(f"Applying Container App definition with image {image_ref}")
        poller = client.container_apps.begin_create_or_update(
            rg, container_app_name, container_app
        )
        result = poller.result()

        fqdn = None
        if result.configuration and result.configuration.ingress:
            fqdn = result.configuration.ingress.fqdn
        new_revision = getattr(result, "latest_revision_name", None)

        # Shift 100% traffic to the freshly created revision.
        if new_revision:
            self._set_traffic(client, rg, container_app_name, new_revision, logs)

        return previous_revision, fqdn, new_revision

    def _set_traffic(
        self, client, rg: str, container_app_name: str, revision_name: str, logs: list[str]
    ) -> None:
        from azure.mgmt.appcontainers.models import TrafficWeight

        app = client.container_apps.get(rg, container_app_name)
        app.configuration.ingress.traffic = [
            TrafficWeight(revision_name=revision_name, weight=100, latest_revision=False)
        ]
        client.container_apps.begin_update(rg, container_app_name, app).result()
        logs.append(f"Routed 100% traffic to revision {revision_name}")

    def _activate_revision(
        self,
        *,
        credential,
        config: AzureDeployConfig,
        container_app_name: str,
        target_revision: str,
        previous_revision: str,
        logs: list[str],
    ) -> str | None:
        from azure.mgmt.appcontainers import ContainerAppsAPIClient

        client = ContainerAppsAPIClient(credential, config.subscription_id)
        rg = config.resource_group

        logs.append(f"Activating revision {target_revision}")
        client.container_apps_revisions.activate_revision(
            rg, container_app_name, target_revision
        )

        self._set_traffic(client, rg, container_app_name, target_revision, logs)

        if previous_revision and previous_revision != target_revision:
            try:
                client.container_apps_revisions.deactivate_revision(
                    rg, container_app_name, previous_revision
                )
                logs.append(f"Deactivated revision {previous_revision}")
            except Exception as exc:  # noqa: BLE001 — best effort
                logs.append(f"Could not deactivate {previous_revision}: {exc}")

        app = client.container_apps.get(rg, container_app_name)
        if app.configuration and app.configuration.ingress:
            return app.configuration.ingress.fqdn
        return None

    # ------------------------------------------------------------------ #
    # Health verification
    # ------------------------------------------------------------------ #
    def _wait_for_health(self, live_url: str, health_path: str, logs: list[str]) -> bool:
        import httpx

        if not live_url:
            return False

        target = live_url.rstrip("/") + (
            health_path if health_path.startswith("/") else f"/{health_path}"
        )
        timeout = settings.DEPLOYMENT_TIMEOUT_SECONDS
        interval = max(1, settings.DEPLOYMENT_HEALTH_POLL_INTERVAL_SECONDS)
        deadline = time.monotonic() + timeout

        logs.append(f"Polling health endpoint {target} (timeout {timeout}s)")
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            try:
                response = httpx.get(target, timeout=10, follow_redirects=True)
                if response.status_code == 200:
                    logs.append(f"Health check returned 200 after {attempt} attempt(s)")
                    return True
            except Exception:  # noqa: BLE001 — app still starting up
                pass
            time.sleep(interval)
        return False
