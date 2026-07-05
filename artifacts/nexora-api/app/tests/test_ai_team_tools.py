"""Tests for Sprint 39B — Agent Tool Integrations (read-only foundation)."""

from app.tests.conftest import auth_headers, create_authenticated_user


async def _agent(client, token, name="SRE", role="Operations"):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops Team"})
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": name,
                "role": role,
                "instructions": f"You are the {name}. Investigate read-only.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    return team, agent


async def _tool(client, token, provider="KUBERNETES", name="Prod Cluster"):
    return (
        await client.post(
            "/v1/ai-tools",
            headers=auth_headers(token),
            json={"provider": provider, "name": name, "description": "read-only"},
        )
    ).json()


async def test_tool_crud(client):
    _, tokens = await create_authenticated_user(client, email="t1@example.com", username="tool1")
    token = tokens["access_token"]

    created = await client.post(
        "/v1/ai-tools",
        headers=auth_headers(token),
        json={"provider": "kubernetes", "name": "Prod Cluster", "description": "k8s read-only"},
    )
    assert created.status_code == 201, created.text
    tool = created.json()
    assert tool["provider"] == "KUBERNETES"
    assert "get_pods" in tool["allowed_actions"]

    listed = await client.get("/v1/ai-tools", headers=auth_headers(token))
    assert listed.json()["total"] == 1

    fetched = await client.get(f"/v1/ai-tools/{tool['id']}", headers=auth_headers(token))
    assert fetched.status_code == 200

    updated = await client.put(
        f"/v1/ai-tools/{tool['id']}",
        headers=auth_headers(token),
        json={"is_active": False, "name": "Prod Cluster (paused)"},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = await client.delete(f"/v1/ai-tools/{tool['id']}", headers=auth_headers(token))
    assert deleted.status_code == 204
    assert (await client.get("/v1/ai-tools", headers=auth_headers(token))).json()["total"] == 0


async def test_invalid_provider_rejected(client):
    _, tokens = await create_authenticated_user(client, email="t2@example.com", username="tool2")
    token = tokens["access_token"]
    resp = await client.post(
        "/v1/ai-tools",
        headers=auth_headers(token),
        json={"provider": "MAINFRAME", "name": "x"},
    )
    assert resp.status_code == 422


async def test_tool_assignment(client):
    _, tokens = await create_authenticated_user(client, email="t3@example.com", username="tool3")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token)

    assigned = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["total"] == 1

    # Idempotent re-assign does not duplicate.
    again = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    assert again.json()["total"] == 1

    listed = await client.get(
        f"/v1/ai-team-agents/{agent['id']}/tools", headers=auth_headers(token)
    )
    assert listed.json()["total"] == 1

    unassigned = await client.delete(
        f"/v1/ai-team-agents/{agent['id']}/tools/{tool['id']}", headers=auth_headers(token)
    )
    assert unassigned.status_code == 204
    assert (
        await client.get(
            f"/v1/ai-team-agents/{agent['id']}/tools", headers=auth_headers(token)
        )
    ).json()["total"] == 0


async def test_tool_execution_read_only(client):
    _, tokens = await create_authenticated_user(client, email="t4@example.com", username="tool4")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token)
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )

    resp = await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "get_pods", "payload": {"namespace": "default"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["provider"] == "KUBERNETES"
    assert body["action"] == "get_pods"
    assert body["response_summary"]


async def test_execute_requires_assignment(client):
    _, tokens = await create_authenticated_user(client, email="t5@example.com", username="tool5")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token)
    # Not assigned -> 403.
    resp = await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "get_pods"},
    )
    assert resp.status_code == 403


async def test_forbidden_action_denied(client):
    _, tokens = await create_authenticated_user(client, email="t6@example.com", username="tool6")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token)
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    for action in ["delete_pods", "scale_deployment", "restart_pod", "apply_manifest", "exec_shell"]:
        resp = await client.post(
            f"/v1/ai-tools/{tool['id']}/execute",
            headers=auth_headers(token),
            json={"agent_id": agent["id"], "action": action},
        )
        assert resp.status_code in (403, 422), f"{action} -> {resp.status_code}"


async def test_postgres_select_only(client):
    _, tokens = await create_authenticated_user(client, email="t7@example.com", username="tool7")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token, provider="POSTGRESQL", name="Analytics DB")
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    ok = await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "select_query", "payload": {"sql": "SELECT count(*) FROM orders"}},
    )
    assert ok.status_code == 200, ok.text

    for sql in ["DELETE FROM orders", "UPDATE orders SET x=1", "DROP TABLE orders", "SELECT 1; DROP TABLE x"]:
        bad = await client.post(
            f"/v1/ai-tools/{tool['id']}/execute",
            headers=auth_headers(token),
            json={"agent_id": agent["id"], "action": "select_query", "payload": {"sql": sql}},
        )
        assert bad.status_code == 403, f"{sql} -> {bad.status_code}"


async def test_execution_history(client):
    _, tokens = await create_authenticated_user(client, email="t8@example.com", username="tool8")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token)
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    # One success, one denial — both recorded.
    await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "get_pods"},
    )
    await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "delete_pods"},
    )
    runs = await client.get(f"/v1/ai-tools/{tool['id']}/runs", headers=auth_headers(token))
    assert runs.status_code == 200
    data = runs.json()
    assert data["total"] == 2
    statuses = {r["status"] for r in data["items"]}
    assert "COMPLETED" in statuses
    assert "DENIED" in statuses


async def test_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="t9@example.com", username="tool9")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token, provider="GITHUB", name="Repos")
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    resp = await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={
            "agent_id": agent["id"],
            "action": "list_repositories",
            "payload": {"repo": "acme/app", "token": "ghp_supersecret", "password": "hunter2"},
        },
    )
    assert resp.status_code == 200, resp.text
    runs = await client.get(f"/v1/ai-tools/{tool['id']}/runs", headers=auth_headers(token))
    serialized = runs.text
    assert "ghp_supersecret" not in serialized
    assert "hunter2" not in serialized
    assert "redacted" in serialized.lower()


async def test_tool_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="ta@example.com", username="tia")
    _, tokens_b = await create_authenticated_user(client, email="tb@example.com", username="tib")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    tool = await _tool(client, token_a)

    assert (
        await client.get(f"/v1/ai-tools/{tool['id']}", headers=auth_headers(token_b))
    ).status_code == 404
    assert (
        await client.put(
            f"/v1/ai-tools/{tool['id']}",
            headers=auth_headers(token_b),
            json={"name": "hacked"},
        )
    ).status_code == 404
    assert (
        await client.delete(f"/v1/ai-tools/{tool['id']}", headers=auth_headers(token_b))
    ).status_code == 404
    # Cross-org cannot see it in their list.
    assert (await client.get("/v1/ai-tools", headers=auth_headers(token_b))).json()["total"] == 0


async def test_tool_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="t10@example.com", username="tool10")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token)
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "get_pods"},
    )
    await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "delete_pods"},
    )
    await client.delete(
        f"/v1/ai-team-agents/{agent['id']}/tools/{tool['id']}", headers=auth_headers(token)
    )

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AuditLog))).scalars().all()
    actions = {r.action for r in rows}
    assert "tool_created" in actions
    assert "tool_assigned" in actions
    assert "tool_executed" in actions
    assert "tool_execution_denied" in actions
    assert "tool_unassigned" in actions
