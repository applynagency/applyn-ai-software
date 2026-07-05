"""Sprint 34A — VM (SSH) deployment provider tests.

Covers:
- unit tests       (package build, compose/.env generation, target validation)
- deployment tests (successful SSH deploy, health pass/fail, command sequence)
- rollback tests   (revision/release swap, guards)
- tenancy tests    (cross-org isolation, VM target requirement via the API)
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.deployment.deployer import DeploymentDeployer
from app.deployment.vm_provider import VMDeploymentProvider
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
class FakeSSHSession:
    def __init__(self, *, current_release: str | None = None, fail_on=None):
        self.commands: list[str] = []
        self.files: dict[str, str] = {}
        self.closed = False
        self._current_release = current_release
        self._fail_on = tuple(fail_on or ())

    def run(self, command: str):
        self.commands.append(command)
        if command.startswith("readlink"):
            if self._current_release:
                return 0, f"/opt/applyn/myapp/releases/{self._current_release}\n", ""
            return 1, "", "no current symlink"
        for sub in self._fail_on:
            if sub in command:
                return 1, "", f"failed: {sub}"
        return 0, "ok", ""

    def put_file(self, remote_path: str, content: str):
        self.files[remote_path] = content

    def makedirs(self, remote_path: str):
        self.commands.append(f"mkdir -p {remote_path}")

    def close(self):
        self.closed = True


def _fsa_output() -> dict:
    return {
        "backend_package": {
            "generated_files": [
                {"path": "app/main.py", "content": "print('hi')\n"},
                {"path": "requirements.txt", "content": "fastapi\nuvicorn\n"},
            ]
        },
        "docker_assets": {"docker_configuration": {"backend": {"port": 8000}}},
        "environment_variables": [{"name": "DATABASE_URL", "value": "postgres://x"}],
    }


def _target(**overrides) -> dict:
    base = {
        "host": "203.0.113.10",
        "port": 22,
        "username": "deploy",
        "private_key": "-----FAKE KEY-----",
        "app_port": 8080,
        "deployment_path": "/opt/applyn/myapp",
        "container_name": "myapp",
    }
    base.update(overrides)
    return base


def _provider(session: FakeSSHSession, *, healthy: bool = True) -> VMDeploymentProvider:
    return VMDeploymentProvider(
        ssh_session_factory=lambda target: session,
        http_checker=lambda url: healthy,
    )


# --------------------------------------------------------------------------- #
# Unit tests
# --------------------------------------------------------------------------- #
def test_vm_provider_registered_in_deployer():
    assert DeploymentProvider.VM.value in DeploymentDeployer.supported_providers()


def test_vm_deploy_requires_host():
    provider = _provider(FakeSSHSession())
    with pytest.raises(ValueError, match="host is required"):
        provider.deploy(
            fullstack_assembly_output=_fsa_output(),
            approval_output={},
            app_name="myapp",
            environment="production",
            deployment_target={"username": "deploy", "private_key": "k"},
        )


def test_vm_deploy_requires_private_key():
    provider = _provider(FakeSSHSession())
    with pytest.raises(ValueError, match="private_key is required"):
        provider.deploy(
            fullstack_assembly_output=_fsa_output(),
            approval_output={},
            app_name="myapp",
            environment="production",
            deployment_target={"host": "h", "username": "deploy"},
        )


def test_vm_deploy_builds_compose_and_env():
    session = FakeSSHSession()
    provider = _provider(session)
    provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    compose_key = next(k for k in session.files if k.endswith("/docker-compose.yml"))
    env_key = next(k for k in session.files if k.endswith("/.env"))
    assert '"8080:8000"' in session.files[compose_key]
    assert "container_name: myapp" in session.files[compose_key]
    assert "DATABASE_URL=postgres://x" in session.files[env_key]


# --------------------------------------------------------------------------- #
# Deployment tests
# --------------------------------------------------------------------------- #
def test_vm_deploy_success_returns_deployed_and_live_url():
    session = FakeSSHSession(current_release="20231231120000")
    provider = _provider(session, healthy=True)
    output = provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    assert output.deployment_status == DeploymentStatus.DEPLOYED.value
    assert output.deployment_provider == DeploymentProvider.VM.value
    assert output.live_url == "http://203.0.113.10:8080"
    assert output.rollback_available is True
    assert session.closed is True


def test_vm_deploy_runs_compose_pull_and_up():
    session = FakeSSHSession()
    provider = _provider(session)
    provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    joined = "\n".join(session.commands)
    assert "docker compose pull" in joined
    assert "docker compose up -d" in joined
    assert "ln -sfn" in joined


def test_vm_deploy_metadata_has_required_fields_and_no_secret():
    session = FakeSSHSession()
    provider = _provider(session)
    output = provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    meta = output.deployment_metadata
    assert meta["server_ip"] == "203.0.113.10"
    assert meta["deployment_path"] == "/opt/applyn/myapp"
    assert meta["container_name"] == "myapp"
    assert meta["health_url"] == "http://203.0.113.10:8080/health"
    # The SSH private key must never be exposed in stored metadata.
    assert "private_key" not in meta
    assert "FAKE KEY" not in str(meta)


def test_vm_deploy_first_release_has_no_rollback():
    session = FakeSSHSession(current_release=None)
    provider = _provider(session)
    output = provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    assert output.rollback_available is False


def test_vm_deploy_unhealthy_marks_failed():
    session = FakeSSHSession(current_release="20231231120000")
    provider = _provider(session, healthy=False)
    output = provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    assert output.deployment_status == DeploymentStatus.FAILED.value
    assert output.live_url == ""


def test_vm_deploy_compose_failure_marks_failed():
    session = FakeSSHSession(fail_on=("up -d",))
    provider = _provider(session)
    output = provider.deploy(
        fullstack_assembly_output=_fsa_output(),
        approval_output={},
        app_name="myapp",
        environment="production",
        deployment_target=_target(),
    )
    assert output.deployment_status == DeploymentStatus.FAILED.value
    assert "error" in output.deployment_metadata


# --------------------------------------------------------------------------- #
# Rollback tests
# --------------------------------------------------------------------------- #
def _rollback_metadata(**overrides) -> dict:
    base = {
        "provider": "VM",
        "deployment_path": "/opt/applyn/myapp",
        "previous_release": "20231231120000",
        "health_url": "http://203.0.113.10:8080/health",
        "server_ip": "203.0.113.10",
    }
    base.update(overrides)
    return base


def test_vm_rollback_success():
    session = FakeSSHSession()
    provider = _provider(session, healthy=True)
    output, logs = provider.rollback(
        app_name="myapp",
        rollback_metadata=_rollback_metadata(),
        environment="production",
        deployment_target=_target(),
    )
    assert output.deployment_status == DeploymentStatus.ROLLED_BACK.value
    assert output.live_url == "http://203.0.113.10:8080"
    joined = "\n".join(session.commands)
    assert "releases/20231231120000" in joined
    assert "docker compose up -d" in joined
    assert len(logs) >= 1


def test_vm_rollback_requires_previous_release():
    provider = _provider(FakeSSHSession())
    with pytest.raises(ValueError, match="No previous release"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata=_rollback_metadata(previous_release=None),
            environment="production",
            deployment_target=_target(),
        )


def test_vm_rollback_requires_private_key():
    provider = _provider(FakeSSHSession())
    with pytest.raises(ValueError, match="private_key is required"):
        provider.rollback(
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target={"username": "deploy"},
        )


def test_vm_rollback_via_deployer_dispatch():
    session = FakeSSHSession()
    deployer = DeploymentDeployer()
    with patch.dict(
        "app.deployment.deployer.PROVIDER_REGISTRY",
        {DeploymentProvider.VM.value: _provider(session)},
        clear=False,
    ):
        output, _ = deployer.rollback(
            provider="VM",
            app_name="myapp",
            rollback_metadata=_rollback_metadata(),
            environment="production",
            deployment_target=_target(),
        )
    assert output.deployment_status == DeploymentStatus.ROLLED_BACK.value


# --------------------------------------------------------------------------- #
# Tenancy / API integration tests
# --------------------------------------------------------------------------- #
def _vm_output() -> DeploymentOutput:
    return DeploymentOutput(
        deployment_provider=DeploymentProvider.VM.value,
        deployment_status=DeploymentStatus.DEPLOYED.value,
        live_url="http://203.0.113.10:8080",
        deployment_logs=["connected", "docker compose up -d", "health 200"],
        rollback_available=True,
        deployment_metadata={
            "provider": "VM",
            "server_ip": "203.0.113.10",
            "deployment_path": "/opt/applyn/myapp",
            "container_name": "myapp",
            "health_url": "http://203.0.113.10:8080/health",
            "previous_release": "20231231120000",
            "previous_revision": "20231231120000",
            "target_revision": "20240101000000",
        },
    )


async def _setup_vm_requirement(client, tokens, slug: str):
    workspace = await create_workspace(client, tokens["access_token"], slug=f"{slug}-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug=f"{slug}-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    return requirement


async def test_vm_deploy_requires_deployment_target(client):
    _, tokens = await create_authenticated_user(
        client, email="vm-notarget@example.com", username="vmnotarget"
    )
    requirement = await _setup_vm_requirement(client, tokens, "vm-nt")
    response = await client.post(
        "/v1/agents/deployment/run",
        headers=auth_headers(tokens["access_token"]),
        json={"requirement_id": requirement["id"], "deployment_provider": "VM"},
    )
    assert response.status_code == 422
    assert "deployment_target" in response.text


async def test_vm_deploy_persists_vm_run(client):
    _, tokens = await create_authenticated_user(
        client, email="vm-ok@example.com", username="vmok"
    )
    requirement = await _setup_vm_requirement(client, tokens, "vm-ok")
    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(return_value=_vm_output()),
    ):
        response = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "VM",
                "deployment_target": {
                    "host": "203.0.113.10",
                    "username": "deploy",
                    "private_key": "-----FAKE KEY-----",
                    "app_port": 8080,
                },
            },
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["deployment_provider"] == "VM"
    assert body["status"] == DeploymentStatus.DEPLOYED.value
    assert body["live_url"] == "http://203.0.113.10:8080"
    # private key must not be echoed back anywhere in the response
    assert "FAKE KEY" not in response.text


async def test_vm_deployment_cross_org_isolation(client):
    # Org A owner creates a VM deployment.
    _, a_tokens = await create_authenticated_user(
        client, email="vm-orga@example.com", username="vmorga"
    )
    org_a = await create_organization(
        client, a_tokens["access_token"], name="VM Org A", slug="vm-org-a"
    )
    a_in_org = await switch_organization(client, a_tokens["access_token"], org_a["id"])
    requirement = await _setup_vm_requirement(client, a_in_org, "vm-iso")
    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(return_value=_vm_output()),
    ):
        created = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(a_in_org["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "VM",
                "deployment_target": {
                    "host": "203.0.113.10",
                    "username": "deploy",
                    "private_key": "-----FAKE KEY-----",
                },
            },
        )
    assert created.status_code == 201, created.text
    deployment_id = created.json()["id"]

    # Org B owner must not see or roll back Org A's VM deployment.
    _, b_tokens = await create_authenticated_user(
        client, email="vm-orgb@example.com", username="vmorgb"
    )
    org_b = await create_organization(
        client, b_tokens["access_token"], name="VM Org B", slug="vm-org-b"
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
        json={"deployment_target": {"host": "203.0.113.10", "username": "deploy", "private_key": "k"}},
    )
    assert rollback.status_code == 404


async def test_vm_rollback_requires_target_via_api(client):
    _, tokens = await create_authenticated_user(
        client, email="vm-rb-notarget@example.com", username="vmrbnotarget"
    )
    requirement = await _setup_vm_requirement(client, tokens, "vm-rbnt")
    with patch(
        "app.services.deployment.DeploymentAgent.run",
        new=AsyncMock(return_value=_vm_output()),
    ):
        created = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "deployment_provider": "VM",
                "deployment_target": {
                    "host": "203.0.113.10",
                    "username": "deploy",
                    "private_key": "-----FAKE KEY-----",
                },
            },
        )
    deployment_id = created.json()["id"]
    # Rollback without re-supplying SSH credentials must be rejected.
    response = await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422
    assert "deployment_target" in response.text
