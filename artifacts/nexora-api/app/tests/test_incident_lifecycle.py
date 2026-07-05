"""Tests for Sprint 58A.4 — Complete Incident Lifecycle.

Covers the validated state machine, acknowledgement, assignment/reassignment,
escalation, human collaboration (comments/tasks), war-room auto-launch, the
postmortem auto-generate + edit flow, the remediation control set
(retry/override/pause/resume), the unified command center, and tenant isolation.
"""

import pytest

from app.services import incident_state_machine as sm
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


async def _investigate(client, token, prompt="500 errors after the latest release."):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token),
                              json={"name": "Ops"})).json()
    agent = (await client.post(
        "/v1/ai-team-agents", headers=auth_headers(token),
        json={"team_id": team["id"], "name": "SRE", "role": "Operations",
              "instructions": "Investigate production incidents.",
              "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300,
              "is_active": True})).json()
    for provider in ("GITHUB", "KUBERNETES", "PROMETHEUS"):
        tool = (await client.post("/v1/ai-tools", headers=auth_headers(token),
                                  json={"provider": provider, "name": f"{provider} tool"})).json()
        await client.post(f"/v1/ai-team-agents/{agent['id']}/tools",
                          headers=auth_headers(token), json={"tool_id": tool["id"]})
    resp = await client.post(
        "/v1/incidents/investigate", headers=auth_headers(token),
        json={"team_id": team["id"], "prompt": prompt})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _transition(client, token, incident_id, status_, note=None):
    return await client.post(
        f"/v1/incidents/{incident_id}/transition", headers=auth_headers(token),
        json={"status": status_, "note": note})


# --------------------------------------------------------------- unit: state machine
def test_state_machine_allows_expected_transitions():
    assert sm.can_transition("OPEN", "ACKNOWLEDGED")
    assert sm.can_transition("ACKNOWLEDGED", "INVESTIGATING")
    assert sm.can_transition("INVESTIGATING", "MITIGATING")
    assert sm.can_transition("MITIGATING", "RESOLVED")
    assert sm.can_transition("RESOLVED", "CLOSED")
    # Re-open paths.
    assert sm.can_transition("RESOLVED", "INVESTIGATING")
    assert sm.can_transition("CLOSED", "INVESTIGATING")


def test_state_machine_rejects_invalid_transitions():
    assert not sm.can_transition("OPEN", "RESOLVED")
    assert not sm.can_transition("OPEN", "MITIGATING")
    assert not sm.can_transition("CLOSED", "RESOLVED")
    assert not sm.can_transition("RESOLVED", "ACKNOWLEDGED")
    assert sm.assignment_state_for("MITIGATING") == "INVESTIGATING"
    assert sm.assignment_state_for("RESOLVED") == "RESOLVED"


# --------------------------------------------------------------- lifecycle e2e
async def test_full_lifecycle_open_to_closed(client):
    _, tokens = await create_authenticated_user(client, email="lc1@example.com", username="lc1")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    assert inv["lifecycle_status"] == "OPEN"

    for nxt in ("ACKNOWLEDGED", "INVESTIGATING", "MITIGATING", "RESOLVED", "CLOSED"):
        resp = await _transition(client, token, inv["id"], nxt)
        assert resp.status_code == 200, resp.text
        assert resp.json()["lifecycle_status"] == nxt

    detail = (await client.get(f"/v1/incidents/{inv['id']}", headers=auth_headers(token))).json()
    assert detail["lifecycle_status"] == "CLOSED"
    assert detail["acknowledged_at"] is not None
    assert detail["resolved_at"] is not None
    assert detail["closed_at"] is not None


async def test_invalid_transition_rejected(client):
    _, tokens = await create_authenticated_user(client, email="lc2@example.com", username="lc2")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    # OPEN -> RESOLVED is not allowed.
    resp = await _transition(client, token, inv["id"], "RESOLVED")
    assert resp.status_code == 409
    # Same-state transition is rejected.
    resp = await _transition(client, token, inv["id"], "OPEN")
    assert resp.status_code == 409
    # Unknown state is a 400.
    resp = await _transition(client, token, inv["id"], "BOGUS")
    assert resp.status_code == 400


async def test_every_transition_recorded_on_timeline(client):
    _, tokens = await create_authenticated_user(client, email="lc3@example.com", username="lc3")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    await _transition(client, token, inv["id"], "ACKNOWLEDGED")
    await _transition(client, token, inv["id"], "INVESTIGATING", note="paging SRE")
    events = (await client.get(f"/v1/incidents/{inv['id']}/events",
                               headers=auth_headers(token))).json()
    state_changes = [e for e in events if e["event_type"] == "STATE_CHANGE"]
    assert len(state_changes) >= 2
    assert any(e["to_status"] == "INVESTIGATING" and e["message"] == "paging SRE"
               for e in state_changes)


async def test_acknowledge_endpoint(client):
    _, tokens = await create_authenticated_user(client, email="lc4@example.com", username="lc4")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    resp = await client.post(f"/v1/incidents/{inv['id']}/acknowledge",
                             headers=auth_headers(token), json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["lifecycle_status"] == "ACKNOWLEDGED"
    assert body["acknowledged_at"] is not None


async def test_assign_and_reassign(client):
    user, tokens = await create_authenticated_user(client, email="lc5@example.com", username="lc5")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    resp = await client.post(f"/v1/incidents/{inv['id']}/assign", headers=auth_headers(token),
                             json={"assignee_id": user["id"], "note": "taking it"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["assignee_id"] == user["id"]
    events = (await client.get(f"/v1/incidents/{inv['id']}/events",
                               headers=auth_headers(token))).json()
    assert any(e["event_type"] == "ASSIGNMENT" for e in events)


async def test_escalate_sets_state_and_event(client):
    _, tokens = await create_authenticated_user(client, email="lc6@example.com", username="lc6")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    resp = await client.post(f"/v1/incidents/{inv['id']}/escalate", headers=auth_headers(token),
                             json={"reason": "customer impact rising"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["lifecycle_status"] == "ESCALATED"
    events = (await client.get(f"/v1/incidents/{inv['id']}/events",
                               headers=auth_headers(token))).json()
    assert any(e["event_type"] == "ESCALATION" for e in events)


async def test_comments_thread(client):
    _, tokens = await create_authenticated_user(client, email="lc7@example.com", username="lc7")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    resp = await client.post(f"/v1/incidents/{inv['id']}/comments", headers=auth_headers(token),
                             json={"body": "Looking into the DB pool."})
    assert resp.status_code == 201, resp.text
    comments = (await client.get(f"/v1/incidents/{inv['id']}/comments",
                                 headers=auth_headers(token))).json()
    assert len(comments) == 1
    assert comments[0]["body"] == "Looking into the DB pool."


async def test_tasks_crud(client):
    user, tokens = await create_authenticated_user(client, email="lc8@example.com", username="lc8")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    created = (await client.post(f"/v1/incidents/{inv['id']}/tasks", headers=auth_headers(token),
                                 json={"title": "Add alert", "assignee_id": user["id"]})).json()
    assert created["status"] == "TODO"
    upd = await client.patch(
        f"/v1/incidents/{inv['id']}/tasks/{created['id']}", headers=auth_headers(token),
        json={"status": "DONE"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["status"] == "DONE"
    assert upd.json()["completed_at"] is not None
    tasks = (await client.get(f"/v1/incidents/{inv['id']}/tasks",
                              headers=auth_headers(token))).json()
    assert len(tasks) == 1


async def test_war_room_auto_launches_on_investigating(client):
    _, tokens = await create_authenticated_user(client, email="lc9@example.com", username="lc9")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    before = (await client.get("/v1/war-rooms", headers=auth_headers(token))).json()
    await _transition(client, token, inv["id"], "ACKNOWLEDGED")
    await _transition(client, token, inv["id"], "INVESTIGATING")
    after = (await client.get("/v1/war-rooms", headers=auth_headers(token))).json()
    assert len(after) == len(before) + 1
    room = next(r for r in after if r.get("incident_id") == inv["id"])
    assert room is not None
    # A second INVESTIGATING transition does not duplicate the war room.
    await _transition(client, token, inv["id"], "MITIGATING")
    await _transition(client, token, inv["id"], "INVESTIGATING")
    again = (await client.get("/v1/war-rooms", headers=auth_headers(token))).json()
    assert len([r for r in again if r.get("incident_id") == inv["id"]]) == 1


async def test_postmortem_autogenerates_on_resolve_and_is_editable(client):
    _, tokens = await create_authenticated_user(client, email="lc10@example.com", username="lc10")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    await _transition(client, token, inv["id"], "ACKNOWLEDGED")
    await _transition(client, token, inv["id"], "RESOLVED")

    cc = (await client.get(f"/v1/incidents/{inv['id']}/command-center",
                           headers=auth_headers(token))).json()
    assert cc["postmortem"] is not None
    pm_id = cc["postmortem"]["id"]

    patched = await client.patch(f"/v1/postmortems/{pm_id}", headers=auth_headers(token),
                                 json={"lessons_learned": "Add a canary gate."})
    assert patched.status_code == 200, patched.text
    assert patched.json()["lessons_learned"] == "Add a canary gate."
    assert patched.json()["status"] == "EDITED"
    assert patched.json()["version"] >= 2

    # Still exportable.
    export = await client.get(f"/v1/postmortems/{pm_id}/export?format=markdown",
                              headers=auth_headers(token))
    assert export.status_code == 200


async def test_command_center_aggregates_everything(client):
    _, tokens = await create_authenticated_user(client, email="lc11@example.com", username="lc11")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    await client.post(f"/v1/incidents/{inv['id']}/comments", headers=auth_headers(token),
                      json={"body": "On it."})
    await client.post(f"/v1/incidents/{inv['id']}/tasks", headers=auth_headers(token),
                      json={"title": "Verify rollback"})
    cc = (await client.get(f"/v1/incidents/{inv['id']}/command-center",
                           headers=auth_headers(token))).json()
    assert cc["incident"]["id"] == inv["id"]
    assert "ACKNOWLEDGED" in cc["available_transitions"]
    assert len(cc["comments"]) == 1
    assert len(cc["tasks"]) == 1
    assert isinstance(cc["remediation_actions"], list)
    assert isinstance(cc["steps"], list)
    assert cc["business_impact"] is not None


# --------------------------------------------------------------- remediation controls
async def _bound_action(client, token, inv_id):
    actions = (await client.get(f"/v1/incidents/{inv_id}/actions",
                                headers=auth_headers(token))).json()["actions"]
    action = next(a for a in actions if a["action_type"] == "ROLLBACK_DEPLOYMENT")
    cred = (await client.post("/v1/credentials", headers=auth_headers(token),
                              json={"provider": "KUBERNETES", "name": "prod",
                                    "secret": {"kubeconfig": _KUBECONFIG}})).json()["id"]
    await client.post(f"/v1/remediation-actions/{action['id']}/bind", headers=auth_headers(token),
                      json={"credential_id": cred, "environment": "production",
                            "namespace": "production", "application": "api"})
    return action["id"]


async def test_remediation_pause_resume(client):
    _, tokens = await create_authenticated_user(client, email="rc1@example.com", username="rc1")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    action_id = await _bound_action(client, token, inv["id"])

    paused = await client.post(f"/v1/remediation-actions/{action_id}/pause",
                               headers=auth_headers(token), json={})
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "PAUSED"
    # A paused action cannot be approved.
    blocked = await client.post(f"/v1/remediation-actions/{action_id}/approve",
                                headers=auth_headers(token), json={})
    assert blocked.status_code == 409
    resumed = await client.post(f"/v1/remediation-actions/{action_id}/resume",
                                headers=auth_headers(token), json={})
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "PENDING_APPROVAL"


async def test_remediation_override_after_reject(client):
    _, tokens = await create_authenticated_user(client, email="rc2@example.com", username="rc2")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    action_id = await _bound_action(client, token, inv["id"])
    await client.post(f"/v1/remediation-actions/{action_id}/reject",
                      headers=auth_headers(token), json={"comments": "later"})
    # Override requires a justification.
    no_reason = await client.post(f"/v1/remediation-actions/{action_id}/override",
                                  headers=auth_headers(token), json={})
    assert no_reason.status_code == 400
    overridden = await client.post(f"/v1/remediation-actions/{action_id}/override",
                                   headers=auth_headers(token),
                                   json={"comments": "Sev1 — must roll back now."})
    assert overridden.status_code == 200, overridden.text
    assert overridden.json()["status"] == "COMPLETED"


async def test_remediation_retry_after_failure(client, monkeypatch):
    _, tokens = await create_authenticated_user(client, email="rc3@example.com", username="rc3")
    token = tokens["access_token"]
    inv = await _investigate(client, token)
    action_id = await _bound_action(client, token, inv["id"])

    # Force the first execution to fail, then succeed on retry.
    calls = {"n": 0}

    class _Flaky:
        def remediation_rollback(self, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise rexec.RemediationExecutionError("transient cluster error")
            return ("rolled back", {})

    monkeypatch.setitem(rexec.PROVIDER_FACTORIES, "KUBERNETES", lambda: _Flaky())

    approved = await client.post(f"/v1/remediation-actions/{action_id}/approve",
                                 headers=auth_headers(token), json={})
    assert approved.status_code == 200
    assert approved.json()["status"] == "FAILED"

    retried = await client.post(f"/v1/remediation-actions/{action_id}/retry",
                                headers=auth_headers(token), json={})
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "COMPLETED"


async def test_lifecycle_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="iso-a@example.com", username="isoa")
    _, tokens_b = await create_authenticated_user(client, email="iso-b@example.com", username="isob")
    token_a, token_b = tokens_a["access_token"], tokens_b["access_token"]
    inv = await _investigate(client, token_a)
    # Org B cannot drive org A's incident.
    assert (await _transition(client, token_b, inv["id"], "ACKNOWLEDGED")).status_code == 404
    assert (await client.get(f"/v1/incidents/{inv['id']}/command-center",
                             headers=auth_headers(token_b))).status_code == 404
    assert (await client.post(f"/v1/incidents/{inv['id']}/comments", headers=auth_headers(token_b),
                              json={"body": "x"})).status_code == 404
