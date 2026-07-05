"""Sprint 34B — Kubernetes deployment provider.

Deploys a generated application into a customer-managed Kubernetes cluster:

1. Accepts a ``kubeconfig`` (used transiently; never persisted).
2. Generates manifests: Namespace, ConfigMap, Secret, Deployment, Service,
   Ingress, and a HorizontalPodAutoscaler (HPA).
3. Creates the target namespace if it does not exist.
4. Applies the manifests via the Kubernetes Python SDK.
5. Verifies health: Deployment Available -> Pods Ready -> Ingress reachable.
6. Rollback is fully SDK-driven (Sprint 36B): it inspects the Deployment's
   ReplicaSet revision history, selects the previous revision, patches the
   Deployment's pod template back to that revision's ReplicaSet template, waits
   for the rollout to complete, and re-verifies health. No ``kubectl`` binary,
   shell, or subprocess is involved.

Only non-secret metadata (cluster, namespace, deployment/service names,
ingress_url) is stored on the deployment run.

``kubernetes`` / ``yaml`` are accessed lazily so importing this module never
fails when they are absent. The cluster client and HTTP checker are injectable
to enable testing without a real cluster.
"""

from __future__ import annotations

import base64
import re
import time
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.deployment.deployer import BaseDeploymentProvider
from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput

logger = get_logger(__name__)

_DEFAULT_CONTAINER_PORT = 8000
_SECRET_HINTS = ("SECRET", "PASSWORD", "TOKEN", "KEY", "CREDENTIAL", "PRIVATE")


def _slugify(app_name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", (app_name or "application").lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "application"


def _is_secret(name: str) -> bool:
    upper = name.upper()
    return any(hint in upper for hint in _SECRET_HINTS)


class _KubernetesClient:
    """Default cluster client backed entirely by the Kubernetes Python SDK."""

    def __init__(self, kubeconfig: str) -> None:
        import os
        import tempfile

        import yaml
        from kubernetes import client, config

        fd, self._kubeconfig_path = tempfile.mkstemp(suffix=".kubeconfig")
        with os.fdopen(fd, "w") as handle:
            handle.write(kubeconfig)
        # Validate it parses as YAML early.
        yaml.safe_load(kubeconfig)

        api_client = config.new_client_from_config(config_file=self._kubeconfig_path)
        self._api_client = api_client
        self._apps = client.AppsV1Api(api_client)
        self._core = client.CoreV1Api(api_client)
        self._net = client.NetworkingV1Api(api_client)
        self._autoscaling = client.AutoscalingV2Api(api_client)

    def ensure_namespace(self, namespace: str) -> bool:
        from kubernetes.client.exceptions import ApiException

        try:
            self._core.read_namespace(namespace)
            return False
        except ApiException as exc:
            if exc.status == 404:
                self._core.create_namespace({"metadata": {"name": namespace}})
                return True
            raise

    def apply_manifest(self, manifest: dict) -> None:
        from kubernetes.client.exceptions import ApiException

        kind = manifest["kind"]
        namespace = manifest["metadata"]["namespace"]
        name = manifest["metadata"]["name"]
        create, replace = self._dispatch(kind)
        try:
            create(namespace, manifest)
        except ApiException as exc:
            if exc.status == 409:
                replace(name, namespace, manifest)
            else:
                raise

    def _dispatch(self, kind: str):
        mapping = {
            "ConfigMap": (
                self._core.create_namespaced_config_map,
                self._core.replace_namespaced_config_map,
            ),
            "Secret": (
                self._core.create_namespaced_secret,
                self._core.replace_namespaced_secret,
            ),
            "Service": (
                self._core.create_namespaced_service,
                self._core.replace_namespaced_service,
            ),
            "Deployment": (
                self._apps.create_namespaced_deployment,
                self._apps.replace_namespaced_deployment,
            ),
            "Ingress": (
                self._net.create_namespaced_ingress,
                self._net.replace_namespaced_ingress,
            ),
            "HorizontalPodAutoscaler": (
                self._autoscaling.create_namespaced_horizontal_pod_autoscaler,
                self._autoscaling.replace_namespaced_horizontal_pod_autoscaler,
            ),
        }
        create_fn, replace_fn = mapping[kind]

        def create(namespace: str, body: dict) -> None:
            create_fn(namespace=namespace, body=body)

        def replace(name: str, namespace: str, body: dict) -> None:
            replace_fn(name=name, namespace=namespace, body=body)

        return create, replace

    def wait_available(self, namespace: str, name: str, timeout: int) -> bool:
        deadline = time.monotonic() + timeout
        interval = max(1, settings.DEPLOYMENT_HEALTH_POLL_INTERVAL_SECONDS)
        while time.monotonic() < deadline:
            status = self._apps.read_namespaced_deployment_status(name, namespace)
            spec_replicas = (status.spec.replicas or 1) if status.spec else 1
            available = (status.status.available_replicas or 0) if status.status else 0
            if available >= spec_replicas:
                return True
            time.sleep(interval)
        return False

    def pods_ready(self, namespace: str, name: str) -> bool:
        status = self._apps.read_namespaced_deployment_status(name, namespace)
        spec_replicas = (status.spec.replicas or 1) if status.spec else 1
        ready = (status.status.ready_replicas or 0) if status.status else 0
        return ready >= spec_replicas

    _REVISION_ANNOTATION = "deployment.kubernetes.io/revision"

    def _revision_history(self, namespace: str, name: str):
        """Return ``(deployment, [(revision:int, replicaset), ...])`` newest first.

        Only ReplicaSets owned by the Deployment that carry a revision
        annotation are considered — this is exactly the history ``kubectl
        rollout`` reads, obtained here purely through the API.
        """
        deployment = self._apps.read_namespaced_deployment(name, namespace)
        match_labels = {}
        if deployment.spec and deployment.spec.selector:
            match_labels = deployment.spec.selector.match_labels or {}
        label_selector = ",".join(f"{k}={v}" for k, v in match_labels.items()) or None

        rs_list = self._apps.list_namespaced_replica_set(
            namespace, label_selector=label_selector
        )
        dep_uid = deployment.metadata.uid if deployment.metadata else None

        revisions: list[tuple[int, object]] = []
        for rs in rs_list.items:
            owners = (rs.metadata.owner_references or []) if rs.metadata else []
            if dep_uid and not any(o.uid == dep_uid for o in owners):
                continue
            annotations = (rs.metadata.annotations or {}) if rs.metadata else {}
            raw = annotations.get(self._REVISION_ANNOTATION)
            if raw is None:
                continue
            try:
                revisions.append((int(raw), rs))
            except (TypeError, ValueError):
                continue

        revisions.sort(key=lambda item: item[0], reverse=True)
        return deployment, revisions

    def current_revision(self, namespace: str, name: str) -> int | None:
        deployment, revisions = self._revision_history(namespace, name)
        annotations = (deployment.metadata.annotations or {}) if deployment.metadata else {}
        raw = annotations.get(self._REVISION_ANNOTATION)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        return revisions[0][0] if revisions else None

    def rollback_to_revision(
        self, namespace: str, name: str, target_revision: int | None = None
    ) -> tuple[int, int | None]:
        """Roll a Deployment back to a previous ReplicaSet revision via the API.

        Equivalent to ``kubectl rollout undo`` but implemented with the Python
        SDK only: it locates the target revision's ReplicaSet, then patches the
        Deployment's pod template back to that ReplicaSet's template (which the
        controller resolves to the existing ReplicaSet, restoring it).

        Returns ``(restored_revision, previous_current_revision)``. Raises
        ``ValueError`` when no suitable previous revision exists.
        """
        deployment, revisions = self._revision_history(namespace, name)
        if not revisions:
            raise ValueError("No ReplicaSet revision history found for deployment")

        annotations = (deployment.metadata.annotations or {}) if deployment.metadata else {}
        current = None
        raw = annotations.get(self._REVISION_ANNOTATION)
        if raw is not None:
            try:
                current = int(raw)
            except (TypeError, ValueError):
                current = None
        if current is None:
            current = revisions[0][0]

        target_rs = None
        restored_revision = None
        if target_revision is not None:
            want = int(target_revision)
            for revision, rs in revisions:
                if revision == want:
                    target_rs, restored_revision = rs, revision
                    break
        else:
            for revision, rs in revisions:
                if revision < current:
                    target_rs, restored_revision = rs, revision
                    break

        if target_rs is None:
            raise ValueError("No previous revision available to roll back to")

        template = self._api_client.sanitize_for_serialization(target_rs.spec.template)
        labels = (template.get("metadata") or {}).get("labels") or {}
        labels.pop("pod-template-hash", None)
        body = {
            "metadata": {
                "annotations": {
                    "kubernetes.io/change-cause": (
                        f"Rolled back to revision {restored_revision} via Kubernetes API"
                    )
                }
            },
            "spec": {"template": template},
        }
        self._apps.patch_namespaced_deployment(name, namespace, body)
        return restored_revision, current

    def restart_deployment(self, namespace: str, name: str) -> None:
        """Trigger a rolling restart (equivalent to ``kubectl rollout restart``).

        Patches the pod template's ``restartedAt`` annotation; the controller
        then rolls all pods. SDK-only — no kubectl/shell.
        """
        import datetime as _dt

        stamp = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": stamp,
                        }
                    }
                }
            }
        }
        self._apps.patch_namespaced_deployment(name, namespace, body)

    def scale_deployment(self, namespace: str, name: str, replicas: int) -> int:
        """Patch the Deployment replica count and return the previous value."""
        deployment = self._apps.read_namespaced_deployment(name, namespace)
        previous = (deployment.spec.replicas or 0) if deployment.spec else 0
        self._apps.patch_namespaced_deployment(
            name, namespace, {"spec": {"replicas": int(replicas)}}
        )
        return previous

    def close(self) -> None:
        import os

        try:
            os.remove(self._kubeconfig_path)
        except OSError:
            pass


class KubernetesDeploymentProvider(BaseDeploymentProvider):
    """Deploys applications into a customer-managed Kubernetes cluster."""

    def __init__(
        self,
        client_factory: Callable[[str], Any] | None = None,
        http_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._http_checker = http_checker

    # ------------------------------------------------------------------ #
    # Contract
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
        target = self._validate_target(deployment_target)

        slug = _slugify(app_name)
        namespace = target.get("namespace") or f"applyn-{environment}"
        deployment_name = target.get("container_name") or slug
        service_name = f"{deployment_name}-svc"
        ingress_name = f"{deployment_name}-ingress"
        app_port = int(target.get("app_port") or self._container_port(fullstack_assembly_output))
        replicas = int(target.get("replicas") or 2)
        image = target.get("image") or f"{slug}:latest"
        ingress_host = target.get("ingress_host") or f"{slug}.{settings.APP_BASE_DOMAIN or 'apps.local'}"
        cluster = target.get("cluster_name") or "customer-cluster"
        ingress_url = f"http://{ingress_host}"

        manifests = self._build_manifests(
            fsa_output=fullstack_assembly_output,
            namespace=namespace,
            deployment_name=deployment_name,
            service_name=service_name,
            ingress_name=ingress_name,
            ingress_host=ingress_host,
            image=image,
            app_port=app_port,
            replicas=replicas,
        )

        logs: list[str] = [
            f"Connecting to cluster '{cluster}'",
            f"Environment: {environment}",
            f"Target namespace: {namespace}",
        ]

        try:
            client = self._connect(target)
            try:
                created = client.ensure_namespace(namespace)
                logs.append(
                    f"Namespace {'created' if created else 'already exists'}: {namespace}"
                )
                for manifest in manifests:
                    client.apply_manifest(manifest)
                    logs.append(f"Applied {manifest['kind']}/{manifest['metadata']['name']}")

                available = client.wait_available(
                    namespace, deployment_name, settings.DEPLOYMENT_TIMEOUT_SECONDS
                )
                logs.append(f"Deployment Available: {available}")
                ready = client.pods_ready(namespace, deployment_name) if available else False
                logs.append(f"Pods Ready: {ready}")
            finally:
                client.close()
        except Exception as exc:  # noqa: BLE001 — surfaced as FAILED deployment
            logger.error("kubernetes_deploy_failed", cluster=cluster, error=str(exc))
            logs.append(f"Deployment failed: {exc}")
            return DeploymentOutput(
                deployment_provider=DeploymentProvider.KUBERNETES.value,
                deployment_status=DeploymentStatus.FAILED.value,
                live_url="",
                deployment_logs=logs,
                rollback_available=False,
                deployment_metadata={
                    "provider": DeploymentProvider.KUBERNETES.value,
                    "cluster": cluster,
                    "namespace": namespace,
                    "deployment_name": deployment_name,
                    "service_name": service_name,
                    "ingress_url": ingress_url,
                    "error": str(exc),
                },
            )

        reachable = self._check_health(f"{ingress_url}/health") if (available and ready) else False
        logs.append(f"Ingress reachable: {reachable}")
        healthy = available and ready and reachable
        status = (
            DeploymentStatus.DEPLOYED.value if healthy else DeploymentStatus.FAILED.value
        )

        return DeploymentOutput(
            deployment_provider=DeploymentProvider.KUBERNETES.value,
            deployment_status=status,
            live_url=ingress_url if healthy else "",
            deployment_logs=logs,
            rollback_available=healthy,
            deployment_metadata={
                "provider": DeploymentProvider.KUBERNETES.value,
                "cluster": cluster,
                "namespace": namespace,
                "deployment_name": deployment_name,
                "service_name": service_name,
                "ingress_url": ingress_url,
                "image": image,
                "replicas": replicas,
                "manifests_applied": [m["kind"] for m in manifests],
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
        namespace = rollback_metadata.get("namespace")
        deployment_name = rollback_metadata.get("deployment_name")
        ingress_url = rollback_metadata.get("ingress_url")

        if not namespace or not deployment_name:
            raise ValueError("namespace/deployment_name missing from rollback metadata")

        target = self._validate_target(deployment_target)

        # Optional explicit revision (kubectl --to-revision style); when absent
        # we roll back to the most recent revision below the current one.
        raw_revision = rollback_metadata.get("previous_revision")
        target_revision: int | None
        try:
            target_revision = int(raw_revision) if raw_revision not in (None, "") else None
        except (TypeError, ValueError):
            target_revision = None

        logs: list[str] = [
            f"Rolling back deployment/{deployment_name} in namespace {namespace} "
            "via the Kubernetes API (SDK, no kubectl)",
        ]
        client = self._connect(target)
        try:
            restored_revision, from_revision = client.rollback_to_revision(
                namespace, deployment_name, target_revision
            )
            logs.append(
                f"Restored previous ReplicaSet revision {restored_revision} "
                f"(was revision {from_revision})"
            )
            logs.append("Patched Deployment pod template to the previous revision")
            available = client.wait_available(
                namespace, deployment_name, settings.DEPLOYMENT_TIMEOUT_SECONDS
            )
            logs.append(f"Deployment Available after rollback: {available}")
            ready = client.pods_ready(namespace, deployment_name) if available else False
            logs.append(f"Pods Ready after rollback: {ready}")
        finally:
            client.close()

        reachable = self._check_health(f"{ingress_url}/health") if ingress_url else True
        healthy = available and ready and reachable
        logs.append(f"Rollback health: {healthy}")

        # A rollback that does not return to a healthy state is a failed
        # rollback: surface it so the caller marks the run FAILED rather than
        # silently reporting success.
        if not healthy:
            raise RuntimeError(
                "Rollback did not reach a healthy state "
                f"(available={available}, ready={ready}, reachable={reachable})"
            )

        output = DeploymentOutput(
            deployment_provider=DeploymentProvider.KUBERNETES.value,
            deployment_status=DeploymentStatus.ROLLED_BACK.value,
            live_url=ingress_url if healthy else "",
            deployment_logs=logs,
            rollback_available=False,
            deployment_metadata={
                "provider": DeploymentProvider.KUBERNETES.value,
                "rollback_completed": True,
                "namespace": namespace,
                "deployment_name": deployment_name,
                "restored_revision": restored_revision,
                "previous_revision": from_revision,
            },
        )
        return output, logs

    # ------------------------------------------------------------------ #
    # Sprint 41C — approval-gated remediation operations (rollback/restart/scale).
    # All return a uniform ``(customer_safe_result, rollback_metadata)`` tuple.
    # ------------------------------------------------------------------ #
    def remediation_rollback(
        self,
        *,
        namespace: str,
        deployment_name: str,
        deployment_target: dict | None = None,
        previous_revision: int | str | None = None,
        ingress_url: str | None = None,
    ) -> tuple[str, dict]:
        """Reuse the Sprint 36B SDK rollback and return a uniform result tuple."""
        meta = {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "previous_revision": previous_revision,
            "ingress_url": ingress_url,
        }
        output, _logs = self.rollback(
            app_name=deployment_name or "application",
            rollback_metadata=meta,
            environment="production",
            deployment_target=deployment_target,
        )
        md = output.deployment_metadata or {}
        restored = md.get("restored_revision")
        result = (
            f"Deployment {deployment_name} rolled back to revision {restored}."
            if restored is not None
            else "Deployment rolled back to the previous revision."
        )
        return result, {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "restored_revision": restored,
            "previous_revision": md.get("previous_revision"),
        }

    def restart(
        self, *, namespace: str, deployment_name: str, deployment_target: dict | None = None
    ) -> tuple[str, dict]:
        if not namespace or not deployment_name:
            raise ValueError("namespace and deployment_name are required")
        target = self._validate_target(deployment_target)
        client = self._connect(target)
        try:
            client.restart_deployment(namespace, deployment_name)
            available = client.wait_available(
                namespace, deployment_name, settings.DEPLOYMENT_TIMEOUT_SECONDS
            )
            ready = client.pods_ready(namespace, deployment_name) if available else False
        finally:
            client.close()
        if not (available and ready):
            raise RuntimeError(
                f"Restart did not reach a healthy state (available={available}, ready={ready})"
            )
        result = (
            f"Rolling restart triggered for deployment/{deployment_name} "
            f"in namespace {namespace}; pods are ready."
        )
        return result, {"namespace": namespace, "deployment_name": deployment_name}

    def scale(
        self,
        *,
        namespace: str,
        deployment_name: str,
        replicas: int,
        deployment_target: dict | None = None,
    ) -> tuple[str, dict]:
        if not namespace or not deployment_name:
            raise ValueError("namespace and deployment_name are required")
        if replicas is None or int(replicas) < 0:
            raise ValueError("replicas must be a non-negative integer")
        target = self._validate_target(deployment_target)
        client = self._connect(target)
        try:
            previous = client.scale_deployment(namespace, deployment_name, int(replicas))
            available = client.wait_available(
                namespace, deployment_name, settings.DEPLOYMENT_TIMEOUT_SECONDS
            )
        finally:
            client.close()
        result = (
            f"Scaled deployment/{deployment_name} in namespace {namespace} "
            f"from {previous} to {int(replicas)} replicas."
        )
        return result, {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "previous_replicas": previous,
            "target_replicas": int(replicas),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _validate_target(self, deployment_target: dict | None) -> dict:
        target = dict(deployment_target or {})
        if not target.get("kubeconfig"):
            raise ValueError("deployment_target.kubeconfig is required for Kubernetes deployment")
        return target

    def _connect(self, target: dict):
        if self._client_factory is not None:
            return self._client_factory(target)
        return _KubernetesClient(target["kubeconfig"])

    def _container_port(self, fsa_output: dict) -> int:
        docker_cfg = (
            (fsa_output.get("docker_assets") or {}).get("docker_configuration") or {}
        ).get("backend") or {}
        startup_cfg = (fsa_output.get("startup_configuration") or {}).get("backend") or {}
        health_cfg = (fsa_output.get("health_checks") or {}).get("backend") or {}
        return int(
            docker_cfg.get("port")
            or startup_cfg.get("port")
            or health_cfg.get("port")
            or _DEFAULT_CONTAINER_PORT
        )

    def _split_env(self, fsa_output: dict) -> tuple[dict[str, str], dict[str, str]]:
        config_data: dict[str, str] = {}
        secret_data: dict[str, str] = {}
        for item in fsa_output.get("environment_variables") or []:
            name = item.get("name") if isinstance(item, dict) else None
            if not name:
                continue
            value = str(item.get("value", "")) if isinstance(item, dict) else ""
            if _is_secret(name):
                secret_data[name] = base64.b64encode(value.encode()).decode()
            else:
                config_data[name] = value
        return config_data, secret_data

    def _build_manifests(
        self,
        *,
        fsa_output: dict,
        namespace: str,
        deployment_name: str,
        service_name: str,
        ingress_name: str,
        ingress_host: str,
        image: str,
        app_port: int,
        replicas: int,
    ) -> list[dict]:
        config_data, secret_data = self._split_env(fsa_output)
        config_name = f"{deployment_name}-config"
        secret_name = f"{deployment_name}-secret"
        hpa_name = f"{deployment_name}-hpa"
        labels = {"app": deployment_name, "managed-by": "applyn"}

        config_map = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": config_name, "namespace": namespace, "labels": labels},
            "data": config_data or {"APPLYN_MANAGED": "true"},
        }
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": secret_name, "namespace": namespace, "labels": labels},
            "type": "Opaque",
            "data": secret_data,
        }
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": deployment_name, "namespace": namespace, "labels": labels},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": deployment_name}},
                "template": {
                    "metadata": {"labels": {"app": deployment_name}},
                    "spec": {
                        "containers": [
                            {
                                "name": deployment_name,
                                "image": image,
                                "ports": [{"containerPort": app_port}],
                                "envFrom": [
                                    {"configMapRef": {"name": config_name}},
                                    {"secretRef": {"name": secret_name}},
                                ],
                                "readinessProbe": {
                                    "httpGet": {"path": "/health", "port": app_port},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 10,
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": app_port},
                                    "initialDelaySeconds": 15,
                                    "periodSeconds": 20,
                                },
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "500m", "memory": "512Mi"},
                                },
                            }
                        ]
                    },
                },
            },
        }
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": service_name, "namespace": namespace, "labels": labels},
            "spec": {
                "selector": {"app": deployment_name},
                "ports": [{"port": 80, "targetPort": app_port, "protocol": "TCP"}],
                "type": "ClusterIP",
            },
        }
        ingress = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": ingress_name,
                "namespace": namespace,
                "labels": labels,
                "annotations": {"kubernetes.io/ingress.class": "nginx"},
            },
            "spec": {
                "rules": [
                    {
                        "host": ingress_host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": service_name,
                                            "port": {"number": 80},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
        }
        hpa = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": hpa_name, "namespace": namespace, "labels": labels},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": deployment_name,
                },
                "minReplicas": replicas,
                "maxReplicas": max(replicas + 2, replicas * 3, 4),
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {"type": "Utilization", "averageUtilization": 70},
                        },
                    }
                ],
            },
        }
        return [config_map, secret, deployment, service, ingress, hpa]

    def _check_health(self, url: str) -> bool:
        if self._http_checker is not None:
            return self._http_checker(url)
        return self._poll_http(url)

    def _poll_http(self, url: str) -> bool:
        import httpx

        if not url:
            return False
        timeout = settings.DEPLOYMENT_TIMEOUT_SECONDS
        interval = max(1, settings.DEPLOYMENT_HEALTH_POLL_INTERVAL_SECONDS)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = httpx.get(url, timeout=10, follow_redirects=True)
                if response.status_code == 200:
                    return True
            except Exception:  # noqa: BLE001 — ingress still propagating
                pass
            time.sleep(interval)
        return False
