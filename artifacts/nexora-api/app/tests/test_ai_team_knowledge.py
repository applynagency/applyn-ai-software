"""Tests for Sprint 37D — Team Knowledge Base (RAG)."""

from app.tests.conftest import auth_headers, create_authenticated_user

SECRET_DOC = (
    "Operations Runbook. The secret deployment code is ZEBRA-42. "
    "Deployments must always be approved by the on-call engineer before release. "
    "Rollbacks use the previous ReplicaSet revision."
)


async def _make_team(client, token, name="Engineering Team"):
    return (
        await client.post(
            "/v1/ai-teams", headers=auth_headers(token), json={"name": name}
        )
    ).json()


async def _add_agent(client, token, team_id, name="Backend Engineer"):
    return (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team_id,
                "name": name,
                "role": "Engineering",
                "instructions": f"You are the {name}.",
                "model": "claude-sonnet",
                "temperature": 0.3,
                "max_tokens": 400,
            },
        )
    ).json()


def _upload(client, token, team_id, *, filename="runbook.txt", content=SECRET_DOC,
            content_type="text/plain"):
    return client.post(
        f"/v1/ai-teams/{team_id}/documents",
        headers=auth_headers(token),
        files={"file": (filename, content.encode("utf-8"), content_type)},
    )


async def test_upload_document_processes_to_ready(client):
    _, tokens = await create_authenticated_user(
        client, email="kb1@example.com", username="kb1"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)

    resp = await _upload(client, token, team["id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["filename"] == "runbook.txt"
    assert body["content_type"] == "text/plain"
    assert body["file_size"] > 0
    assert body["status"] == "READY"
    assert body["chunk_count"] >= 1


async def test_unsupported_file_type_rejected(client):
    _, tokens = await create_authenticated_user(
        client, email="kb2@example.com", username="kb2"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    resp = await _upload(
        client, token, team["id"], filename="malware.exe",
        content="x", content_type="application/octet-stream",
    )
    assert resp.status_code == 422


async def test_chunk_and_embedding_creation(client):
    import json

    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamDocumentChunk

    _, tokens = await create_authenticated_user(
        client, email="kb3@example.com", username="kb3"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    doc = (await _upload(client, token, team["id"])).json()

    async with AsyncSessionLocal() as session:
        chunks = (
            await session.execute(
                select(AITeamDocumentChunk).where(
                    AITeamDocumentChunk.document_id == doc["id"]
                )
            )
        ).scalars().all()
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.content
        assert chunk.embedding is not None
        vec = json.loads(chunk.embedding)
        assert isinstance(vec, list) and len(vec) > 0


async def test_list_and_delete_document(client):

    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.ai_team import AITeamDocumentChunk

    _, tokens = await create_authenticated_user(
        client, email="kb4@example.com", username="kb4"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    doc = (await _upload(client, token, team["id"])).json()

    listing = await client.get(
        f"/v1/ai-teams/{team['id']}/documents", headers=auth_headers(token)
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    deleted = await client.delete(
        f"/v1/ai-teams/documents/{doc['id']}", headers=auth_headers(token)
    )
    assert deleted.status_code == 204

    listing2 = await client.get(
        f"/v1/ai-teams/{team['id']}/documents", headers=auth_headers(token)
    )
    assert listing2.json()["total"] == 0

    # Chunks are removed with the document (cascade).
    async with AsyncSessionLocal() as session:
        chunks = (
            await session.execute(
                select(AITeamDocumentChunk).where(
                    AITeamDocumentChunk.document_id == doc["id"]
                )
            )
        ).scalars().all()
    assert len(chunks) == 0


async def test_retrieval_in_single_agent_execution(client):
    _, tokens = await create_authenticated_user(
        client, email="kb5@example.com", username="kb5"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    agent = await _add_agent(client, token, team["id"])
    await _upload(client, token, team["id"])

    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "What is the secret deployment code?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Knowledge sources surfaced for the execution screen.
    assert "runbook.txt" in body["knowledge_sources"]
    # Offline runner echoes the (knowledge-augmented) prompt, proving injection.
    assert "ZEBRA-42" in body["response"]


async def test_retrieval_in_team_execution(client):
    _, tokens = await create_authenticated_user(
        client, email="kb6@example.com", username="kb6"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    await _add_agent(client, token, team["id"], name="CTO")
    await _upload(client, token, team["id"])

    resp = await client.post(
        f"/v1/ai-teams/{team['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "What is the secret deployment code?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "runbook.txt" in body["knowledge_sources"]
    assert any("ZEBRA-42" in (s["response"] or "") for s in body["steps"])


async def test_no_documents_means_no_sources(client):
    _, tokens = await create_authenticated_user(
        client, email="kb7@example.com", username="kb7"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    agent = await _add_agent(client, token, team["id"])

    resp = await client.post(
        f"/v1/ai-team-agents/{agent['id']}/execute",
        headers=auth_headers(token),
        json={"prompt": "Hello agent"},
    )
    assert resp.status_code == 200
    assert resp.json()["knowledge_sources"] == []


async def test_knowledge_base_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(
        client, email="kb-a@example.com", username="kbaa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="kb-b@example.com", username="kbbb"
    )
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    team_a = await _make_team(client, token_a)
    doc_a = (await _upload(client, token_a, team_a["id"])).json()

    # Org B cannot upload into Org A's team.
    intrusion = await _upload(client, token_b, team_a["id"], filename="b.txt")
    assert intrusion.status_code == 404

    # Org B cannot list Org A's documents.
    listing = await client.get(
        f"/v1/ai-teams/{team_a['id']}/documents", headers=auth_headers(token_b)
    )
    assert listing.status_code == 404

    # Org B cannot delete Org A's document.
    deleted = await client.delete(
        f"/v1/ai-teams/documents/{doc_a['id']}", headers=auth_headers(token_b)
    )
    assert deleted.status_code == 404


async def test_audit_events(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(
        client, email="kb8@example.com", username="kb8"
    )
    token = tokens["access_token"]
    team = await _make_team(client, token)
    doc = (await _upload(client, token, team["id"])).json()

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.resource_id == doc["id"])
            )
        ).scalars().all()
    actions = {r.action for r in rows}
    assert "ai_document_uploaded" in actions
    assert "ai_document_processed" in actions

    await client.delete(
        f"/v1/ai-teams/documents/{doc['id']}", headers=auth_headers(token)
    )
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "ai_document_deleted",
                    AuditLog.resource_id == doc["id"],
                )
            )
        ).scalars().all()
    assert len(rows) >= 1
