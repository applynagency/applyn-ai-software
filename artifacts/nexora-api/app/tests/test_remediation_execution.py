"""Tests for Sprint 41C — Real Approved Remediation Execution.

Covers the new provider operations (Kubernetes restart/scale, VM restart, AWS
ECS rollback/restart) at the provider level with injected fakes, plus the
end-to-end approval→execution path (binding required, credential resolution +
audit, status transitions, timeout, rejection, tenant isolation, no leakage).
Provider factories are patched so no live infrastructure is required, while
credential decryption/auditing stays real.
"""

import time

import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.repositories.incident import IncidentRemediationActionRepository
from app.services import remediation_execution as rexec
from app.tests.conftest import auth_headers, create_authenticated_user

_KUBECONFIG = "apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\n"


# ============================== provider-level units ======================= #
class _FakeK8sClient:
    def __init__(self):
        self.restarted = None
        self.scaled = None

    def restart_deployment(self, ns, name):
        self.restarted = (ns, name)

    def scale_deployment(self, ns, name, replicas):
        self.scaled = (ns, name, replicas)
        return 2

    def wait_available(self, ns, name, timeout):
        return True

    def pods_ready(self, ns, name):
        return True

    def close(self):
        pass


def test_k8s_provider_restart_and_scale():
    from app.deployment.kubernetes_provider import KubernetesDeploymentProvider

    fake = _FakeK8sClient()
    provider = KubernetesDeploymentProvider(client_factory=lambda target: fake)
    target = {"kubeconfig": _KUBECONFIG}

    result, meta = provider.restart(
        namespace="production", deployment_name="api", deployment_target=target
    )
    assert fake.restarted == ("production", "api")
    assert "restart" in result.lower()
    assert meta["deployment_name"] == "api"

    result, meta = provider.scale(
        namespace="production", deployment_name="api", replicas=5, deployment_target=target
    )
    assert fake.scaled == ("production", "api", 5)
    assert meta["previous_replicas"] == 2
    assert meta["target_replicas"] == 5


class _FakeSSH:
    def __init__(self):
        self.cmds = []

    def run(self, command):
        self.cmds.append(command)
        return 0, "", ""

    def close(self):
        pass


def test_vm_provider_restart_stack_and_service():
    from app.deployment.vm_provider import VMDeploymentProvider

    fake = _FakeSSH()
    provider = VMDeploymentProvider(ssh_session_factory=lambda t: fake)
    target = {"host": "1.2.3.4", "username": "deploy", "private_key": "KEY", "deployment_path": "/opt/app"}

    result, _ = provider.restart_stack(deployment_target=target)
    assert any("docker compose restart" in c for c in fake.cmds)
    assert "restarted" in result.lower()

    fake.cmds.clear()
    result, meta = provider.restart_service(service_name="api", deployment_target=target)
    assert any("systemctl restart api" in c for c in fake.cmds)
    assert meta["service_name"] == "api"


class _FakeEcs:
    def __init__(self):
        self.updated = None

    def describe_services(self, cluster, services):
        return {"services": [{"taskDefinition": "arn:aws:ecs:::task-definition/web:3"}]}

    def list_task_definitions(self, familyPrefix, sort, status):
        return {
            "taskDefinitionArns": [
                "arn:aws:ecs:::task-definition/web:3",
                "arn:aws:ecs:::task-definition/web:2",
            ]
        }

    def update_service(self, **kwargs):
        self.updated = kwargs


def test_aws_provider_rollback_and_restart():
    from app.deployment.aws_ecs_provider import AWSEcsRemediationProvider

    ecs = _FakeEcs()

    class _Sess:
        def client(self, name):
            assert name == "ecs"
            return ecs

    provider = AWSEcsRemediationProvider(session_factory=lambda secret: _Sess())
    target = {"access_key": "a", "secret_key": "b", "region": "us-east-1",
              "cluster": "prod", "service": "web"}

    result, meta = provider.rollback(deployment_target=target)
    assert meta["restored_task_definition"].endswith("web:2")
    assert ecs.updated["forceNewDeployment"] is True

    result, _ = provider.restart(deployment_target=target)
    assert ecs.updated["forceNewDeployment"] is True
    assert "restarted" in result.lower()


# ============================== end-to-end (API) =========================== #
class _FakeProvider:
    """Uniform fake covering every remediation method."""

    def __init__(self, *, fail=False, slow=False):
        self._fail = fail
        self._slow = slow

    def _run(self, label):
        if self._slow:
            time.sleep(1.0)
        if self._fail:
            raise RuntimeError("boom: kubeconfig=SUPERSECRET token=abcd")
        return (f"{label} completed.", {"detail": label})

    def remediation_rollback(self, **kw):
        return self._run("Rollback")

    def restart(self, **kw):
        return self._run("Restart")

    def scale(self, **kw):
        return self._run("Scale")

    def remediation_rollback_revision(self, **kw):
        return self._run("Azure rollback")

    def remediation_restart(self, **kw):
        return self._run("Azure restart")

    def rollback(self, **kw):
        return self._run("ECS rollback")

    def restart_stack(self, **kw):
        return self._run("Restart")

    def restart_service(self, **kw):
        return self._run("Restart")


def _patch_all(monkeypatch, **kwargs):
    for name in ("KUBERNETES", "AZURE", "AWS", "VM"):
        monkeypatch.setitem(rexec.PROVIDER_FACTORIES, name, lambda **_: _FakeProvider(**kwargs))


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops"})).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                  "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True},
        )
    ).json()
    return team, agent


async def _investigate(client, token):
    team, agent = await _team_agent(client, token)
    for provider in ("GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"):
        tool = (await client.post("/v1/ai-tools", headers=auth_headers(token),
                                  json={"provider": provider, "name": provider})).json()
        await client.post(f"/v1/ai-team-agents/{agent['id']}/tools", headers=auth_headers(token),
                          json={"tool_id": tool["id"]})
    return (
        await client.post("/v1/incidents/investigate", headers=auth_headers(token),
                          json={"team_id": team["id"], "prompt": "500s after release v2.8.4"})
    ).json()


async def _actions(client, token, incident_id):
    return (await client.get(f"/v1/incidents/{incident_id}/actions", headers=auth_headers(token))).json()["actions"]


async def _credential(client, token, provider, secret, name="cred"):
    resp = await client.post("/v1/credentials", headers=auth_headers(token),
                             json={"provider": provider, "name": name, "secret": secret})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


_SECRETS = {
    "KUBERNETES": {"kubeconfig": _KUBECONFIG},
    "AWS": {"access_key": "AKIA", "secret_key": "shhh", "region": "us-east-1"},
    "VM": {"host": "1.2.3.4", "username": "deploy", "private_key": "PRIVKEY"},
    "AZURE": {"subscription_id": "s", "tenant_id": "t", "client_id": "c", "client_secret": "x"},
}


async def _insert_action(org_id, investigation_id, provider, action_type):
    async with AsyncSessionLocal() as session:
        repo = IncidentRemediationActionRepository(session)
        action = await repo.create(
            organization_id=org_id,
            investigation_id=investigation_id,
            action_type=action_type,
            provider=provider,
            title=f"{action_type} on {provider}",
            risk_level="HIGH",
            status="PENDING_APPROVAL",
            action_metadata={},
        )
        await session.commit()
        return action.id


async def test_approve_requires_binding(client):
    _, tokens = await create_authenticated_user(client, email="x1@e.com", username="rx1")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    # Unbound action cannot be approved.
    resp = await client.post(
        f"/v1/remediation-actions/{actions[0]['id']}/approve", headers=auth_headers(token), json={}
    )
    assert resp.status_code == 422
    # Status is unchanged.
    again = await client.get(f"/v1/remediation-actions/{actions[0]['id']}", headers=auth_headers(token))
    assert again.json()["status"] == "PENDING_APPROVAL"


async def test_bind_provider_mismatch_and_cross_tenant(client):
    _, tok_a = await create_authenticated_user(client, email="x2@e.com", username="rx2")
    _, tok_b = await create_authenticated_user(client, email="x3@e.com", username="rx3")
    a, b = tok_a["access_token"], tok_b["access_token"]
    inv = await _investigate(client, a)
    actions = await _actions(client, a, inv["id"])
    action_id = actions[0]["id"]  # KUBERNETES action

    aws_cred = await _credential(client, a, "AWS", _SECRETS["AWS"])
    mismatch = await client.post(f"/v1/remediation-actions/{action_id}/bind", headers=auth_headers(a),
                                 json={"credential_id": aws_cred, "application": "api", "namespace": "prod"})
    assert mismatch.status_code == 422

    # Cross-tenant bind/approve → 404.
    k8s_cred = await _credential(client, a, "KUBERNETES", _SECRETS["KUBERNETES"])
    x = await client.post(f"/v1/remediation-actions/{action_id}/bind", headers=auth_headers(b),
                          json={"credential_id": k8s_cred, "application": "api", "namespace": "prod"})
    assert x.status_code == 404


@pytest.mark.parametrize(
    "provider,action_type,label",
    [
        ("KUBERNETES", "ROLLBACK_DEPLOYMENT", "Rollback"),
        ("KUBERNETES", "RESTART_DEPLOYMENT", "Restart"),
        ("KUBERNETES", "SCALE_DEPLOYMENT", "Scale"),
        ("AZURE", "ROLLBACK_REVISION", "Azure rollback"),
        ("AZURE", "RESTART_CONTAINER_APP", "Azure restart"),
        ("AWS", "ROLLBACK_ECS", "ECS rollback"),
        ("VM", "RESTART_COMPOSE_STACK", "Restart"),
    ],
)
async def test_real_execution_per_provider(client, monkeypatch, provider, action_type, label):
    _patch_all(monkeypatch)
    _, tokens = await create_authenticated_user(
        client, email=f"e{provider}{action_type}@e.com", username=f"u{provider}{action_type}"[:30]
    )
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    base = (await _actions(client, token, inv["id"]))[0]
    org_id = base["organization_id"]

    action_id = await _insert_action(org_id, inv["id"], provider, action_type)
    cred = await _credential(client, token, provider, _SECRETS[provider], name=f"{provider}-cred")
    tc = {"replicas": 4} if action_type == "SCALE_DEPLOYMENT" else {}
    bind = await client.post(
        f"/v1/remediation-actions/{action_id}/bind", headers=auth_headers(token),
        json={"credential_id": cred, "environment": "production", "namespace": "production",
              "application": "api", "target_config": tc},
    )
    assert bind.status_code == 200, bind.text
    assert bind.json()["bound"] is True

    resp = await client.post(f"/v1/remediation-actions/{action_id}/approve",
                             headers=auth_headers(token), json={"comments": "go"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert label in body["execution_result"]
    assert body["executed_at"] is not None


async def test_execution_audit_and_secret_usage(client, monkeypatch):
    _patch_all(monkeypatch)
    _, tokens = await create_authenticated_user(client, email="x4@e.com", username="rx4")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    action = (await _actions(client, token, inv["id"]))[0]
    cred = await _credential(client, token, "KUBERNETES", _SECRETS["KUBERNETES"])
    await client.post(f"/v1/remediation-actions/{action['id']}/bind", headers=auth_headers(token),
                      json={"credential_id": cred, "namespace": "production", "application": "api"})
    await client.post(f"/v1/remediation-actions/{action['id']}/approve", headers=auth_headers(token), json={})

    from app.models.credential import SecretAccessAudit

    async with AsyncSessionLocal() as session:
        events = {r.action for r in (await session.execute(select(AuditLog))).scalars().all()}
        secret_events = {
            r.event for r in (await session.execute(select(SecretAccessAudit))).scalars().all()
        }
    assert "remediation_execution_started" in events
    assert "remediation_execution_completed" in events
    assert "remediation_action_bound" in events
    # The customer credential resolution was audited in the secret-access log.
    assert "SECRET_USED" in secret_events


async def test_execution_failure_marks_failed_no_leak(client, monkeypatch):
    _patch_all(monkeypatch, fail=True)
    _, tokens = await create_authenticated_user(client, email="x5@e.com", username="rx5")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    action = (await _actions(client, token, inv["id"]))[0]
    cred = await _credential(client, token, "KUBERNETES", _SECRETS["KUBERNETES"])
    await client.post(f"/v1/remediation-actions/{action['id']}/bind", headers=auth_headers(token),
                      json={"credential_id": cred, "namespace": "production", "application": "api"})
    resp = await client.post(f"/v1/remediation-actions/{action['id']}/approve",
                             headers=auth_headers(token), json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["execution_result"] is None
    raw = resp.text.lower()
    for needle in ("supersecret", "kubeconfig", "token=abcd", "boom"):
        assert needle not in raw


async def test_execution_timeout_marks_failed(client, monkeypatch):
    _patch_all(monkeypatch, slow=True)
    monkeypatch.setattr(rexec.RemediationExecutor, "_timeout", property(lambda self: 0.2))
    _, tokens = await create_authenticated_user(client, email="x6@e.com", username="rx6")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    action = (await _actions(client, token, inv["id"]))[0]
    cred = await _credential(client, token, "KUBERNETES", _SECRETS["KUBERNETES"])
    await client.post(f"/v1/remediation-actions/{action['id']}/bind", headers=auth_headers(token),
                      json={"credential_id": cred, "namespace": "production", "application": "api"})
    resp = await client.post(f"/v1/remediation-actions/{action['id']}/approve",
                             headers=auth_headers(token), json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    assert "timed out" in (body["error_message"] or "").lower()
