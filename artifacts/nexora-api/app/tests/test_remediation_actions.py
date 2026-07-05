"""Tests for Sprint 41B — Approval-Based Remediation Actions.

After Sprint 41C, execution is real and approval requires the action to be bound
to a customer credential + target. These tests bind a Kubernetes credential and
patch the provider factory so the approval/execution flow runs without a live
cluster (credential resolution + audit remain real).
"""

import pytest

from app.services import remediation_actions as ra
from app.services import remediation_execution as rexec
from app.tests.conftest import auth_headers, create_authenticated_user


class _FakeK8sProvider:
    def remediation_rollback(self, **kw):
        return ("Deployment api rolled back to revision 41.", {"namespace": kw.get("namespace")})

    def restart(self, **kw):
        return ("Rolling restart triggered; pods are ready.", {})

    def scale(self, **kw):
        return ("Scaled deployment to target replicas.", {})


@pytest.fixture(autouse=True)
def _patch_k8s_provider(monkeypatch):
    monkeypatch.setitem(rexec.PROVIDER_FACTORIES, "KUBERNETES", lambda: _FakeK8sProvider())


_KUBECONFIG = "apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\n"


async def _k8s_credential(client, token):
    resp = await client.post(
        "/v1/credentials",
        headers=auth_headers(token),
        json={"provider": "KUBERNETES", "name": "prod-cluster", "secret": {"kubeconfig": _KUBECONFIG}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _bind(client, token, action_id, credential_id, **kw):
    body = {"credential_id": credential_id, "environment": "production",
            "namespace": "production", "application": "api", **kw}
    resp = await client.post(
        f"/v1/remediation-actions/{action_id}/bind", headers=auth_headers(token), json=body
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _team_agent(client, token, name="Ops"):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": name})
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "SRE",
                "role": "Operations",
                "instructions": "Investigate production incidents.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    return team, agent


async def _tool(client, token, provider):
    return (
        await client.post(
            "/v1/ai-tools",
            headers=auth_headers(token),
            json={"provider": provider, "name": f"{provider} tool"},
        )
    ).json()


async def _assign(client, token, agent_id, tool_id):
    resp = await client.post(
        f"/v1/ai-team-agents/{agent_id}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool_id},
    )
    assert resp.status_code in (200, 201), resp.text


async def _investigate(client, token, providers=("GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG")):
    team, agent = await _team_agent(client, token)
    for provider in providers:
        tool = await _tool(client, token, provider)
        await _assign(client, token, agent["id"], tool["id"])
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token),
            json={"team_id": team["id"], "prompt": "500 errors after the latest release."},
        )
    ).json()
    return inv


async def _actions(client, token, incident_id):
    resp = await client.get(
        f"/v1/incidents/{incident_id}/actions", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["actions"]


# ----------------------------------------------------------- unit
def test_plan_actions_maps_rollback_and_restart():
    recs = [
        {"id": "1", "recommendation_type": "Deployment", "title": "Rollback deployment v2.8.4", "risk_level": "HIGH"},
        {"id": "2", "recommendation_type": "Kubernetes", "title": "Restart affected pods", "risk_level": "MEDIUM"},
        {"id": "3", "recommendation_type": "Kubernetes", "title": "Scale replicas (increase) to absorb load", "risk_level": "MEDIUM"},
        {"id": "4", "recommendation_type": "Application", "title": "Review application error logs", "risk_level": "LOW"},
    ]
    specs = ra.plan_actions(recs)
    types = {s["action_type"] for s in specs}
    assert types == {"ROLLBACK_DEPLOYMENT", "RESTART_DEPLOYMENT", "SCALE_DEPLOYMENT"}
    rollback = next(s for s in specs if s["action_type"] == "ROLLBACK_DEPLOYMENT")
    assert rollback["provider"] == "KUBERNETES"
    assert rollback["risk_level"] == "HIGH"
    assert rollback["action_metadata"].get("version") == "v2.8.4"
    # Investigative recommendations never become executable actions.
    assert all(s["recommendation_id"] != "4" for s in specs)


def test_target_hints_from_context_prefers_service():
    hints = ra.RemediationActionService._target_hints_from_context(
        {"service": "payments-api", "environment": "staging"},
        None,
    )
    assert hints["application"] == "payments-api"
    assert hints["environment"] == "staging"
    assert hints["namespace"] == "staging"


# ----------------------------------------------------------- auto-bind
async def test_auto_bind_after_investigation(client):
    _, tokens = await create_authenticated_user(client, email="ab1@example.com", username="actab1")
    token = tokens["access_token"]
    cred = await _k8s_credential(client, token)
    team, agent = await _team_agent(client, token, "AutoBind")
    for provider in ("GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"):
        tool = await _tool(client, token, provider)
        await _assign(client, token, agent["id"], tool["id"])
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "prompt": "500 errors after the latest release.",
                "context": {"service": "api", "environment": "production"},
            },
        )
    ).json()
    actions = await _actions(client, token, inv["id"])
    rollback = next((a for a in actions if a["action_type"] == "ROLLBACK_DEPLOYMENT"), None)
    assert rollback is not None
    assert rollback["credential_id"] == cred
    assert rollback["bound"] is True
    assert rollback["application"] == "api"
    assert rollback["namespace"] == "production"


async def test_auto_bind_endpoint(client):
    _, tokens = await create_authenticated_user(client, email="ab2@example.com", username="actab2")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    action = actions[0]
    assert action["bound"] is False
    cred = await _k8s_credential(client, token)
    resp = await client.post(
        f"/v1/remediation-actions/{action['id']}/auto-bind",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["credential_id"] == cred
    assert body["bound"] is True


# ----------------------------------------------------------- generation
async def test_actions_generated_pending_approval(client):
    _, tokens = await create_authenticated_user(client, email="a1@example.com", username="acta1")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    assert actions
    assert any(a["action_type"] == "ROLLBACK_DEPLOYMENT" for a in actions)
    for a in actions:
        assert a["status"] == "PENDING_APPROVAL"
        assert a["provider"]
        assert a["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert a["approved_by"] is None
        assert a["execution_result"] is None


# ----------------------------------------------------------- approval + execution
async def test_approve_executes_and_records_history(client):
    _, tokens = await create_authenticated_user(client, email="a2@example.com", username="acta2")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    rollback = next(a for a in actions if a["action_type"] == "ROLLBACK_DEPLOYMENT")
    cred = await _k8s_credential(client, token)
    await _bind(client, token, rollback["id"], cred)

    resp = await client.post(
        f"/v1/remediation-actions/{rollback['id']}/approve",
        headers=auth_headers(token),
        json={"comments": "Approved by on-call."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["approved_by"] is not None
    assert body["approved_at"] is not None
    assert body["executed_at"] is not None
    assert body["execution_result"]

    # Approval history records the decision.
    hist = await client.get(
        f"/v1/remediation-actions/{rollback['id']}/approvals", headers=auth_headers(token)
    )
    assert hist.status_code == 200
    approvals = hist.json()["approvals"]
    assert len(approvals) == 1
    assert approvals[0]["status"] == "APPROVED"
    assert approvals[0]["comments"] == "Approved by on-call."


async def test_double_approval_returns_409(client):
    _, tokens = await create_authenticated_user(client, email="a3@example.com", username="acta3")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    action_id = actions[0]["id"]
    cred = await _k8s_credential(client, token)
    await _bind(client, token, action_id, cred)

    first = await client.post(
        f"/v1/remediation-actions/{action_id}/approve", headers=auth_headers(token), json={}
    )
    assert first.status_code == 200
    again = await client.post(
        f"/v1/remediation-actions/{action_id}/approve", headers=auth_headers(token), json={}
    )
    assert again.status_code == 409
    # And a rejection after a decision is also blocked.
    reject = await client.post(
        f"/v1/remediation-actions/{action_id}/reject", headers=auth_headers(token), json={}
    )
    assert reject.status_code == 409


async def test_reject_path(client):
    _, tokens = await create_authenticated_user(client, email="a4@example.com", username="acta4")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    action_id = actions[0]["id"]

    resp = await client.post(
        f"/v1/remediation-actions/{action_id}/reject",
        headers=auth_headers(token),
        json={"comments": "Not now."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"
    assert resp.json()["execution_result"] is None
    hist = (
        await client.get(
            f"/v1/remediation-actions/{action_id}/approvals", headers=auth_headers(token)
        )
    ).json()["approvals"]
    assert hist[0]["status"] == "REJECTED"


async def test_actions_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="aa@example.com", username="actaa")
    _, tokens_b = await create_authenticated_user(client, email="ab@example.com", username="actab")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    inv = await _investigate(client, token_a)
    actions = await _actions(client, token_a, inv["id"])
    action_id = actions[0]["id"]

    # Org B cannot see, approve, or reject org A's action.
    assert (
        await client.get(f"/v1/remediation-actions/{action_id}", headers=auth_headers(token_b))
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/remediation-actions/{action_id}/approve", headers=auth_headers(token_b), json={}
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/v1/incidents/{inv['id']}/actions", headers=auth_headers(token_b)
        )
    ).status_code == 404


async def test_actions_audit_logging(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="a5@example.com", username="acta5")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    actions = await _actions(client, token, inv["id"])
    cred = await _k8s_credential(client, token)
    await _bind(client, token, actions[0]["id"], cred)
    await client.post(
        f"/v1/remediation-actions/{actions[0]['id']}/approve",
        headers=auth_headers(token),
        json={},
    )
    async with AsyncSessionLocal() as session:
        events = {r.action for r in (await session.execute(select(AuditLog))).scalars().all()}
    assert "remediation_action_created" in events
    assert "remediation_action_approved" in events
    assert "remediation_action_started" in events
    assert "remediation_action_completed" in events


async def test_actions_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="a6@example.com", username="acta6")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    resp = await client.get(f"/v1/incidents/{inv['id']}/actions", headers=auth_headers(token))
    raw = resp.text.lower()
    for needle in ("password", "secret", "kubeconfig", "private_key", "access_key"):
        assert needle not in raw
