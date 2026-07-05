"""Sprint 34B — Kubernetes deployment provider tests.

Covers:
- deployment tests (manifest generation, namespace, apply, success/failure)
- health tests    (Deployment Available, Pods Ready, Ingress reachable gates)
- rollback tests  (SDK revision/ReplicaSet rollback path + guards, Sprint 36B)
- tenancy tests   (cross-org isolation, kubeconfig requirement via the API)
"""

import base64
from unittest.mock import AsyncMock, patch

import pytest

from app.deployment.deployer import DeploymentDeployer
from app.deployment.kubernetes_provider import KubernetesDeploymentProvider
from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    setup_deployment_pipeline,
    switch_organization,
)


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeK8sClient:
    def __init__(
        self,
        *,
        namespace_exists: bool = False,
        available: bool = True,
        ready: bool = True,
        fail_apply: str | None = None,
        no_previous_revision: bool = False,
        rollback_error: str | None = None,
        restored_revision: int = 1,
        current_revision: int = 2,
    ):
        self.applied: list[dict] = []
        self.namespaces_created: list[str] = []
        self.rolled_back: list[tuple] = []
        self.closed = False
        self._namespace_exists = namespace_exists
        self._available = available
        self._ready = ready
        self._fail_apply = fail_apply
        self._no_previous_revision = no_previous_revision
        self._rollback_error = rollback_error
        self._restored_revision = restored_revision
        self._current_revision = current_revision

    def ensure_namespace(self, namespace: str) -> bool:
        if self._namespace_exists:
            return False
        self.namespaces_created.append(namespace)
        return True

    def apply_manifest(self, manifest: dict) -> None:
        if self._fail_apply and manifest["kind"] == self._fail_apply:
            raise RuntimeError(f"apply failed for {manifest['kind']}")
        self.applied.append(manifest)

    def wait_available(self, namespace: str, name: str, timeout: int) -> bool:
        return self._available

    def pods_ready(self, namespace: str, name: str) -> bool:
        return self._ready

    def rollback_to_revision(
        self, namespace: str, name: str, target_revision: int | None = None
    ) -> tuple[int, int | None]:
        if self._rollback_error:
            raise RuntimeError(self._rollback_error)
        if self._no_previous_revision:
            raise ValueError("No previous revision available to roll back to")
        self.rolled_back.append((namespace, name, target_revision))
        return self._restored_revision, self._current_revision

    def close(self) -> None:
        self.closed = True


def _fsa_output() -> dict:
    return {
        "backend_package": {
            "generated_files": [{"path": "app/main.py", "content": "x = 1\n"}]
        },
        "docker_assets": {"docker_configuration": {"backend": {"port": 8000}}},
        "environment_variables": [
            {"name": "LOG_LEVEL", "value": "info"},
            {"name": "DATABASE_PASSWORD", "value": "s3cr3t"},
        ],
    }


def _target(**overrides) -> dict:
    base = {
        "kubeconfig": "apiVersion: v1\nclusters: []\ncontexts: []\nusers: []\n",
        "namespace": "applyn-prod",
        "cluster_name": "prod-cluster",
        "ingress_host": "myapp.example.com",
        "image": "registry.example.com/myapp:1.0",
        "app_port": 8000,
        "replicas": 3,
        "container_name": "myapp",
    }
    base.update(overrides)
    return base


def _provider(client: FakeK8sClient, *, healthy: bool = True) -> KubernetesDeploymentProvider:
    return KubernetesDeploymentProvider(
        client_factory=lambda target: client,
        http_checker=lambda url: healthy,
    )


def _deploy(provider: KubernetesDeploymentProvider, **overrides) -> DeploymentOutput:
    return provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(**overrides),
    )


# --------------------------------------------------------------------------- #
# Deployment tests
# --------------------------------------------------------------------------- #
def test_k8s_provider_registered():
    assert DeploymentProvider.KUBERNETES.value in DeploymentDeployer.supported_providers()


def test_k8s_deploy_requires_kubeconfig():
    provider = _provider(FakeK8sClient())
    with pytest.raises(ValueError, match="kubeconfig is required"):
        provider.deploy(
            fullstack_assembly_output=_fsa_output(),
            approval_output={},
            app_name="myapp",
            environment="production",
            deployment_target={"namespace": "x"},
        )


def test_k8s_deploy_generates_all_manifests():
    client = FakeK8sClient()
    output = _deploy(_provider(client))
    kinds = [m["kind"] for m in client.applied]
    assert kinds == [
        "ConfigMap",
        "Secret",
        "Deployment",
        "Service",
        "Ingress",
        "HorizontalPodAutoscaler",
    ]
    assert output.deployment_metadata["manifests_applied"] == kinds


def test_k8s_deploy_creates_namespace_when_absent():
    client = FakeK8sClient(namespace_exists=False)
    _deploy(_provider(client))
    assert client.namespaces_created == ["applyn-prod"]


def test_k8s_deploy_skips_namespace_when_present():
    client = FakeK8sClient(namespace_exists=True)
    _deploy(_provider(client))
    assert client.namespaces_created == []


def test_k8s_deploy_success_metadata():
    client = FakeK8sClient()
    output = _deploy(_provider(client, healthy=True))
    assert output.deployment_status == DeploymentStatus.DEPLOYED.value
    assert output.deployment_provider == DeploymentProvider.KUBERNETES.value
    assert output.live_url == "http://myapp.example.com"
    assert output.rollback_available is True
    meta = output.deployment_metadata
    assert meta["cluster"] == "prod-cluster"
    assert meta["namespace"] == "applyn-prod"
    assert meta["deployment_name"] == "myapp"
    assert meta["service_name"] == "myapp-svc"
    assert meta["ingress_url"] == "http://myapp.example.com"
    assert client.closed is True


def test_k8s_deploy_splits_secret_and_config_and_hides_kubeconfig():
    client = FakeK8sClient()
    output = _deploy(_provider(client))
    by_kind = {m["kind"]: m for m in client.applied}
    assert "LOG_LEVEL" in by_kind["ConfigMap"]["data"]
    secret_data = by_kind["Secret"]["data"]
    assert "DATABASE_PASSWORD" in secret_data
    assert base64.b64decode(secret_data["DATABASE_PASSWORD"]).decode() == "s3cr3t"
    # kubeconfig must never appear in any manifest or stored metadata.
    assert "clusters" not in str(client.applied)
    assert "kubeconfig" not in output.deployment_metadata


def test_k8s_deploy_hpa_bounds():
    client = FakeK8sClient()
    _deploy(_provider(client), replicas=3)
    hpa = next(m for m in client.applied if m["kind"] == "HorizontalPodAutoscaler")
    assert hpa["spec"]["minReplicas"] == 3
    assert hpa["spec"]["maxReplicas"] >= 3


# --------------------------------------------------------------------------- #
# Health tests
# --------------------------------------------------------------------------- #
def test_k8s_deploy_fails_when_not_available():
    client = FakeK8sClient(available=False)
    output = _deploy(_provider(client, healthy=True))
    assert output.deployment_status == DeploymentStatus.FAILED.value
    assert output.live_url == ""


def test_k8s_deploy_fails_when_pods_not_ready():
    client = FakeK8sClient(available=True, ready=False)
    output = _deploy(_provider(client, healthy=True))
    assert output.deployment_status == DeploymentStatus.FAILED.value


def test_k8s_deploy_fails_when_ingress_unreachable():
    client = FakeK8sClient(available=True, ready=True)
    output = _deploy(_provider(client, healthy=False))
    assert output.deployment_status == DeploymentStatus.FAILED.value
    assert output.live_url == ""


def test_k8s_deploy_fails_on_apply_error():
    client = FakeK8sClient(fail_apply="Deployment")
    output = _deploy(_provider(client))
    assert output.deployment_status == DeploymentStatus.FAILED.value
    assert "error" in output.deployment_metadata


# --------------------------------------------------------------------------- #
# Rollback tests
# --------------------------------------------------------------------------- #
def _rollback_metadata(**overrides) -> dict:
    base = {
        "provider": "KUBERNETES",
        "cluster": "prod-cluster",
        "namespace": "applyn-prod",
        "deployment_name": "myapp",
        "service_name": "myapp-svc",
        "ingress_url": "http://myapp.example.com",
    }
    base.update(overrides)
    return base


def test_k8s_rollback_success():
    client = FakeK8sClient(restored_revision=4, current_revision=5)
    provider = _provider(client, healthy=True)
    output, logs = provider.rollback(
        app_name="myapp",
        rollback_metadata=_rollback_metadata(),
        environment="production",
        deployment_target=_target(),
    )
    assert output.deployment_status == DeploymentStatus.ROLLED_BACK.value
    assert output.live_url == "http://myapp.example.com"
    # SDK revision rollback called (no kubectl); target_revision None => previous.
    assert client.rolled_back == [("applyn-prod", "myapp", None)]
    assert output.deployment_metadata["restored_revision"] == 4
    assert output.deployment_metadata["previous_revision"] == 5
    assert output.deployment_metadata["rollback_completed"] is True
    assert client.closed is True
    # health verification ran (Available -> Pods Ready -> Ingress reachable)
    assert any("Pods Ready after rollback" in line for line in logs)
    assert any("Rollback health: True" in line for line in logs)


def test_k8s_rollback_honours_explicit_target_revision():
    client = FakeK8sClient()
    provider = _provider(client, healthy=True)
    provider.rollback(
        app_name="myapp",
        rollback_metadata=_rollback_metadata(previous_revision=3),
        environment="production",
        deployment_target=_target(),
    )
    assert client.rolled_back == [("applyn-prod", "myapp", 3)]


def test_k8s_rollback_missing_previous_revision():
    client = FakeK8sClient(no_previous_revision=True)
    provider = _provider(client, healthy=True)
    with pytest.raises(ValueError, match="No previous revision"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target=_target(),
        )
    assert client.closed is True


def test_k8s_rollback_unhealthy_raises():
    # Restore succeeds but the rolled-back revision never becomes reachable.
    client = FakeK8sClient(available=True, ready=True)
    provider = _provider(client, healthy=False)
    with pytest.raises(RuntimeError, match="did not reach a healthy state"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target=_target(),
        )


def test_k8s_rollback_api_error_propagates():
    client = FakeK8sClient(rollback_error="patch_namespaced_deployment failed (403)")
    provider = _provider(client, healthy=True)
    with pytest.raises(RuntimeError, match="patch_namespaced_deployment failed"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target=_target(),
        )
    assert client.closed is True


def test_k8s_provider_has_no_subprocess_or_kubectl():
    import inspect

    import app.deployment.kubernetes_provider as kp

    source = inspect.getsource(kp)
    # No shell execution paths anywhere in the provider module.
    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert not hasattr(kp._KubernetesClient, "rollout_undo")
    assert hasattr(kp._KubernetesClient, "rollback_to_revision")


# --------------------------------------------------------------------------- #
# Real _KubernetesClient SDK revision-rollback logic (no cluster, SDK only)
# --------------------------------------------------------------------------- #
def _rs(revision: int, image: str, dep_uid: str = "dep-uid"):
    from types import SimpleNamespace

    return SimpleNamespace(
        metadata=SimpleNamespace(
            annotations={"deployment.kubernetes.io/revision": str(revision)},
            owner_references=[SimpleNamespace(uid=dep_uid)],
        ),
        spec=SimpleNamespace(
            template={
                "metadata": {"labels": {"app": "myapp", "pod-template-hash": f"h{revision}"}},
                "spec": {"containers": [{"name": "myapp", "image": image}]},
            }
        ),
    )


class _FakeApps:
    def __init__(self, deployment, replicasets):
        self._deployment = deployment
        self._replicasets = replicasets
        self.patched: list[tuple] = []

    def read_namespaced_deployment(self, name, namespace):
        return self._deployment

    def list_namespaced_replica_set(self, namespace, label_selector=None):
        from types import SimpleNamespace

        return SimpleNamespace(items=self._replicasets)

    def patch_namespaced_deployment(self, name, namespace, body):
        self.patched.append((name, namespace, body))


def _real_client(apps):
    from kubernetes.client import ApiClient

    from app.deployment.kubernetes_provider import _KubernetesClient

    c = object.__new__(_KubernetesClient)
    c._apps = apps
    c._api_client = ApiClient()
    return c


def _deployment(current_revision: int):
    from types import SimpleNamespace

    return SimpleNamespace(
        metadata=SimpleNamespace(
            uid="dep-uid",
            annotations={"deployment.kubernetes.io/revision": str(current_revision)},
        ),
        spec=SimpleNamespace(selector=SimpleNamespace(match_labels={"app": "myapp"})),
    )


def test_real_client_rolls_back_to_prior_revision_via_patch():
    apps = _FakeApps(
        _deployment(current_revision=3),
        [_rs(3, "myapp:3"), _rs(2, "myapp:2"), _rs(1, "myapp:1")],
    )
    client = _real_client(apps)
    restored, previous = client.rollback_to_revision("ns", "myapp")
    assert (restored, previous) == (2, 3)
    # Deployment patched with the previous revision's template, hash stripped.
    name, ns, body = apps.patched[0]
    template = body["spec"]["template"]
    assert template["spec"]["containers"][0]["image"] == "myapp:2"
    assert "pod-template-hash" not in template["metadata"]["labels"]
    assert "change-cause" in str(body["metadata"]["annotations"])


def test_real_client_honours_explicit_target_revision():
    apps = _FakeApps(
        _deployment(current_revision=3),
        [_rs(3, "myapp:3"), _rs(2, "myapp:2"), _rs(1, "myapp:1")],
    )
    client = _real_client(apps)
    restored, _ = client.rollback_to_revision("ns", "myapp", target_revision=1)
    assert restored == 1
    assert apps.patched[0][2]["spec"]["template"]["spec"]["containers"][0]["image"] == "myapp:1"


def test_real_client_raises_when_no_prior_revision():
    apps = _FakeApps(_deployment(current_revision=1), [_rs(1, "myapp:1")])
    client = _real_client(apps)
    with pytest.raises(ValueError, match="No previous revision"):
        client.rollback_to_revision("ns", "myapp")
    assert apps.patched == []


def test_k8s_rollback_requires_kubeconfig():
    provider = _provider(FakeK8sClient())
    with pytest.raises(ValueError, match="kubeconfig is required"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target={"namespace": "x"},
        )


def test_k8s_rollback_requires_metadata():
    provider = _provider(FakeK8sClient())
    with pytest.raises(ValueError, match="namespace/deployment_name"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata={"provider": "KUBERNETES"},
            environment="production",
            deployment_target=_target(),
        )


def test_k8s_rollback_via_deployer_dispatch():
    client = FakeK8sClient()
    deployer = DeploymentDeployer()
    with patch.dict(
        "app.deployment.deployer.PROVIDER_REGISTRY",
        {DeploymentProvider.KUBERNETES.value: _provider(client)},
        clear=False,
    ):
        output, _ = deployer.rollback(
            provider="KUBERNETES",
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target=_target(),
        )
    assert output.deployment_status == DeploymentStatus.ROLLED_BACK.value


# --------------------------------------------------------------------------- #
# Tenancy / API integration tests
# --------------------------------------------------------------------------- #
def _k8s_output() -> DeploymentOutput:
    return DeploymentOutput(
        deployment_provider=DeploymentProvider.KUBERNETES.value,
        deployment_status=DeploymentStatus.DEPLOYED.value,
        live_url="http://myapp.example.com",
        deployment_logs=["applied", "available", "ready", "reachable"],
        rollback_available=True,
        deployment_metadata={
            "provider": "KUBERNETES",
            "cluster": "prod-cluster",
            "namespace": "applyn-prod",
            "deployment_name": "myapp",
            "service_name": "myapp-svc",
            "ingress_url": "http://myapp.example.com",
        },
    )


async def _setup_requirement(client, tokens, slug: str):
    workspace = await create_workspace(client, tokens["access_token"], slug=f"{slug}-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug=f"{slug}-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    return requirement


async def test_k8s_deploy_requires_kubeconfig_via_api(client):
    _, tokens = await create_authenticated_user(
        client, email="k8s-nocfg@example.com", username="k8snocfg"
    )
    requirement = await _setup_requirement(client, tokens, "k8s-nc")
    response = await client.post(
        "/v1/agents/deployment/run",
        headers=auth_headers(tokens["access_token"]),
        json={"requirement_id": requirement["id"], "deployment_provider": "KUBERNETES"},
    )
    assert response.status_code == 422
    assert "kubeconfig" in response.text


async def test_k8s_deploy_persists_run(client):
    _, tokens = await create_authenticated_user(
        client, email="k8s-ok@example.com", username="k8sok"
    )
    requirement = await _setup_requirement(client, tokens, "k8s-ok")
    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(return_value=_k8s_output()),
    ):
        response = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "KUBERNETES",
                "deployment_target": {"kubeconfig": "apiVersion: v1\nclusters: []\n"},
            },
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["deployment_provider"] == "KUBERNETES"
    assert body["status"] == DeploymentStatus.DEPLOYED.value
    assert body["live_url"] == "http://myapp.example.com"
    assert "clusters" not in response.text or "kubeconfig" not in response.text


async def test_k8s_cross_org_isolation(client):
    _, a_tokens = await create_authenticated_user(
        client, email="k8s-orga@example.com", username="k8sorga"
    )
    org_a = await create_organization(
        client, a_tokens["access_token"], name="K8s Org A", slug="k8s-org-a"
    )
    a_in_org = await switch_organization(client, a_tokens["access_token"], org_a["id"])
    requirement = await _setup_requirement(client, a_in_org, "k8s-iso")
    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(return_value=_k8s_output()),
    ):
        created = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(a_in_org["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "KUBERNETES",
                "deployment_target": {"kubeconfig": "apiVersion: v1\nclusters: []\n"},
            },
        )
    assert created.status_code == 201, created.text
    deployment_id = created.json()["id"]

    _, b_tokens = await create_authenticated_user(
        client, email="k8s-orgb@example.com", username="k8sorgb"
    )
    org_b = await create_organization(
        client, b_tokens["access_token"], name="K8s Org B", slug="k8s-org-b"
    )
    b_in_org = await switch_organization(client, b_tokens["access_token"], org_b["id"])

    view = await client.get(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(b_in_org["access_token"]),
    )
    assert view.status_code == 404

    rollback = await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(b_in_org["access_token"]),
        json={"deployment_target": {"kubeconfig": "apiVersion: v1\n"}},
    )
    assert rollback.status_code == 404


async def test_k8s_rollback_requires_target_via_api(client):
    _, tokens = await create_authenticated_user(
        client, email="k8s-rb-nc@example.com", username="k8srbnc"
    )
    requirement = await _setup_requirement(client, tokens, "k8s-rbnc")
    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(return_value=_k8s_output()),
    ):
        created = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "KUBERNETES",
                "deployment_target": {"kubeconfig": "apiVersion: v1\nclusters: []\n"},
            },
        )
    deployment_id = created.json()["id"]
    response = await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422
    assert "kubeconfig" in response.text
