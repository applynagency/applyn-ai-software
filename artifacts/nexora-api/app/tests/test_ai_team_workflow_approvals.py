"""Tests for Sprint 38C — Human Approval Gates."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _team_with_agents(client, token):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Eng Team"})
    ).json()
    agents = []
    for nm, role in [("CTO", "Leadership"), ("QA Engineer", "Quality"), ("DevOps Engineer", "Ops")]:
        a = (
            await client.post(
                "/v1/ai-team-agents",
                headers=auth_headers(token),
                json={
                    "team_id": team["id"],
                    "name": nm,
                    "role": role,
                    "instructions": f"You are the {nm}. Be brief.",
                    "model": "claude-sonnet",
                    "temperature": 0.2,
                    "max_tokens": 200,
                    "is_active": True,
                },
            )
        ).json()
        agents.append(a)
    return team, agents


async def _workflow_with_gate(client, token, gate_index=0):
    team, agents = await _team_with_agents(client, token)
    steps = []
    for i, a in enumerate(agents):
        step = {"agent_id": a["id"], "step_order": i + 1}
        if i == gate_index:
            step["requires_approval"] = True
            step["approval_name"] = "CTO Approval"
            step["approver_role"] = "CTO"
        steps.append(step)
    wf = (
        await client.post(
            "/v1/ai-team-workflows",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "Production Release Workflow",
                "default_prompt": "Plan the production release.",
                "steps": steps,
            },
        )
    ).json()
    return wf, agents


async def test_step_persists_approval_config(client):
    _, tokens = await create_authenticated_user(
        client, email="ap1@example.com", username="ap1"
    )
    token = tokens["access_token"]
    wf, _ = await _workflow_with_gate(client, token)
    step0 = wf["steps"][0]
    assert step0["requires_approval"] is True
    assert step0["approval_name"] == "CTO Approval"
    assert step0["approver_role"] == "CTO"
    assert wf["steps"][1]["requires_approval"] is False


async def test_execution_pauses_at_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="ap2@example.com", username="ap2"
    )
    token = tokens["access_token"]
    wf, _ = await _workflow_with_gate(client, token)

    resp = await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Ship release 1.0"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "WAITING_FOR_APPROVAL"
    # Only the gated (first) step executed before pausing.
    assert [s["agent_name"] for s in body["steps"]] == ["CTO"]

    # A PENDING approval exists for the workflow.
    approvals = await client.get(
        f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token)
    )
    assert approvals.json()["total"] == 1
    ap = approvals.json()["items"][0]
    assert ap["status"] == "PENDING"
    assert ap["approval_name"] == "CTO Approval"

    # The run is WAITING_FOR_APPROVAL.
    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    assert runs.json()["items"][0]["status"] == "WAITING_FOR_APPROVAL"

    # Run-scoped approvals endpoint works too.
    run_id = body["run_id"]
    run_aps = await client.get(
        f"/v1/workflow-runs/{run_id}/approvals", headers=auth_headers(token)
    )
    assert run_aps.json()["total"] == 1


async def test_approve_resumes_and_completes(client):
    _, tokens = await create_authenticated_user(
        client, email="ap3@example.com", username="ap3"
    )
    token = tokens["access_token"]
    wf, _ = await _workflow_with_gate(client, token)
    exec_resp = (
        await client.post(
            f"/v1/ai-team-workflows/{wf['id']}/execute",
            headers=auth_headers(token),
            json={"prompt": "Ship release 1.0"},
        )
    ).json()
    assert exec_resp["status"] == "WAITING_FOR_APPROVAL"

    ap = (
        await client.get(
            f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token)
        )
    ).json()["items"][0]

    approve = await client.post(
        f"/v1/workflow-approvals/{ap['id']}/approve",
        headers=auth_headers(token),
        json={"comments": "Looks good, proceed."},
    )
    assert approve.status_code == 200, approve.text
    body = approve.json()
    assert body["status"] == "COMPLETED"
    # All three steps present after resume (CTO carried forward + QA + DevOps).
    assert [s["agent_name"] for s in body["steps"]] == [
        "CTO", "QA Engineer", "DevOps Engineer"
    ]

    # Approval marked APPROVED; run COMPLETED.
    got = await client.get(
        f"/v1/workflow-approvals/{ap['id']}", headers=auth_headers(token)
    )
    assert got.json()["status"] == "APPROVED"
    assert got.json()["approved_by"] is not None
    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    assert runs.json()["items"][0]["status"] == "COMPLETED"


async def test_reject_fails_run(client):
    _, tokens = await create_authenticated_user(
        client, email="ap4@example.com", username="ap4"
    )
    token = tokens["access_token"]
    wf, _ = await _workflow_with_gate(client, token)
    exec_resp = (
        await client.post(
            f"/v1/ai-team-workflows/{wf['id']}/execute",
            headers=auth_headers(token),
            json={"prompt": "Ship release 1.0"},
        )
    ).json()
    run_id = exec_resp["run_id"]
    ap = (
        await client.get(
            f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token)
        )
    ).json()["items"][0]

    reject = await client.post(
        f"/v1/workflow-approvals/{ap['id']}/reject",
        headers=auth_headers(token),
        json={"comments": "Security review failed."},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "REJECTED"

    runs = await client.get(
        f"/v1/ai-team-workflows/{wf['id']}/runs", headers=auth_headers(token)
    )
    run = runs.json()["items"][0]
    assert run["status"] == "FAILED"
    assert "Security review failed." in (run["error_message"] or "")


async def test_cannot_decide_twice(client):
    _, tokens = await create_authenticated_user(
        client, email="ap5@example.com", username="ap5"
    )
    token = tokens["access_token"]
    wf, _ = await _workflow_with_gate(client, token)
    await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Ship"},
    )
    ap = (
        await client.get(
            f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token)
        )
    ).json()["items"][0]
    first = await client.post(
        f"/v1/workflow-approvals/{ap['id']}/approve", headers=auth_headers(token), json={}
    )
    assert first.status_code == 200
    second = await client.post(
        f"/v1/workflow-approvals/{ap['id']}/reject", headers=auth_headers(token), json={}
    )
    assert second.status_code == 409


async def test_workflow_without_gate_completes(client):
    _, tokens = await create_authenticated_user(
        client, email="ap6@example.com", username="ap6"
    )
    token = tokens["access_token"]
    team, agents = await _team_with_agents(client, token)
    wf = (
        await client.post(
            "/v1/ai-team-workflows",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "No Gate",
                "default_prompt": "Go",
                "steps": [{"agent_id": a["id"], "step_order": i + 1} for i, a in enumerate(agents)],
            },
        )
    ).json()
    resp = await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Go"},
    )
    assert resp.json()["status"] == "COMPLETED"
    aps = await client.get(
        f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token)
    )
    assert aps.json()["total"] == 0


async def test_approval_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(
        client, email="apa@example.com", username="apaa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="apb@example.com", username="apbb"
    )
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    wf, _ = await _workflow_with_gate(client, token_a)
    exec_resp = (
        await client.post(
            f"/v1/ai-team-workflows/{wf['id']}/execute",
            headers=auth_headers(token_a),
            json={"prompt": "Ship"},
        )
    ).json()
    run_id = exec_resp["run_id"]
    ap = (
        await client.get(
            f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token_a)
        )
    ).json()["items"][0]

    assert (
        await client.get(f"/v1/workflow-approvals/{ap['id']}", headers=auth_headers(token_b))
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/workflow-approvals/{ap['id']}/approve", headers=auth_headers(token_b), json={}
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/workflow-approvals/{ap['id']}/reject", headers=auth_headers(token_b), json={}
        )
    ).status_code == 404
    assert (
        await client.get(f"/v1/workflow-runs/{run_id}/approvals", headers=auth_headers(token_b))
    ).status_code == 404
    assert (
        await client.get("/v1/workflow-approvals", headers=auth_headers(token_b))
    ).json()["total"] == 0


async def test_approval_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="ap7@example.com", username="ap7"
    )
    token = tokens["access_token"]
    wf, _ = await _workflow_with_gate(client, token)
    await client.post(
        f"/v1/ai-team-workflows/{wf['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Ship"},
    )
    ap = (
        await client.get(
            f"/v1/workflow-approvals?workflow_id={wf['id']}", headers=auth_headers(token)
        )
    ).json()["items"][0]
    await client.post(
        f"/v1/workflow-approvals/{ap['id']}/approve", headers=auth_headers(token), json={}
    )

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.resource_id == wf["id"])
            )
        ).scalars().all()
    actions = {r.action for r in rows}
    assert "workflow_approval_created" in actions
    assert "workflow_approved" in actions
    assert "workflow_resumed" in actions
