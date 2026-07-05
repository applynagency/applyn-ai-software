"""Tests for the grounded LLM copilot.

Covers the grounded pipeline offline (no LLM key): RAG retrieval, knowledge-graph
grounding, read-only tool calling, citations + hallucination prevention,
confidence scoring, retry/fallback, SSE streaming, conversation history/memory,
and tenant isolation.
"""

import json

import pytest

from app.core.config import settings
from app.services.grounded_copilot.confidence import (
    build_allowed_set,
    validate_citations,
)
from app.services.grounded_copilot.llm import GroundedLLMClient
from app.tests.conftest import auth_headers, create_authenticated_user

pytestmark = pytest.mark.asyncio
H = auth_headers


# ------------------------------------------------------------------ helpers
async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=H(token), json={"name": "Ops"})).json()
    await client.post(
        "/v1/ai-team-agents",
        headers=H(token),
        json={
            "team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True,
        },
    )


async def _poll(client, token, alert_name, service="checkout", severity="CRITICAL"):
    body = (await client.post(
        "/v1/monitoring/poll", headers=H(token),
        json={"alerts": [{
            "provider": "PROMETHEUS", "alert_id": f"a-{alert_name}-{service}",
            "alert_name": alert_name, "severity": severity,
            "service": service, "environment": "production",
        }]},
    )).json()
    return body["alerts"][0]["incident_id"]


async def _service(client, token, name, tier="TIER_1"):
    return (await client.post(
        "/v1/services", headers=H(token),
        json={"name": name, "tier": tier, "owner_team": "core"},
    )).json()


async def _chat(client, token, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return await client.post("/v1/copilot/chat", headers=H(token), json=payload)


# ------------------------------------------------------------------ basics
async def test_chat_grounded_answer_with_citations(client):
    _, t = await create_authenticated_user(client, email="gc1@e.com", username="gc1")
    token = t["access_token"]
    await _team_agent(client, token)
    await _service(client, token, "checkout")
    await _poll(client, token, "CrashLoopBackOff in checkout", "checkout")

    r = await _chat(client, token, "Why did checkout fail recently?")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conversation_id"] and body["message_id"]
    assert body["intent"] == "INCIDENT_CAUSE"
    assert "checkout" in body["answer"].lower()
    assert body["generation_mode"] == "offline"
    assert body["retrieval_provider"] == "offline-hash"
    assert any(c["source"] == "incident" for c in body["citations"])
    assert body["grounded"] is True
    assert 0 < body["confidence"] <= 99
    # All three read-only tools were invoked.
    tools = {tc["tool"] for tc in body["tool_calls"]}
    assert tools == {
        "search_reliability_data",
        "get_service_blast_radius",
        "search_incident_knowledge",
    }


async def test_rag_retrieves_relevant_incident(client):
    _, t = await create_authenticated_user(client, email="gc2@e.com", username="gc2")
    token = t["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, "DatabaseConnectionPoolExhausted in payments", "payments")

    r = await _chat(client, token, "payments database connection pool problems")
    assert r.status_code == 200, r.text
    body = r.json()
    # The RAG layer surfaced the semantically-related incident as a source.
    assert body["sources"], "expected RAG sources"
    assert body["sources"][0]["source"] == "incident"
    assert body["sources"][0]["score"] is not None


async def test_knowledge_graph_grounding(client):
    _, t = await create_authenticated_user(client, email="gc3@e.com", username="gc3")
    token = t["access_token"]
    api = await _service(client, token, "api")
    db = await _service(client, token, "database")
    # api depends on database -> database has a downstream dependent (blast radius).
    dep = await client.post(
        "/v1/service-dependencies", headers=H(token),
        json={"source_service_id": api["id"], "target_service_id": db["id"],
              "dependency_type": "SYNC"},
    )
    assert dep.status_code == 201, dep.text

    r = await _chat(client, token, "Which service has the largest blast radius?")
    assert r.status_code == 200, r.text
    body = r.json()
    graph_tool = next(tc for tc in body["tool_calls"] if tc["tool"] == "get_service_blast_radius")
    assert graph_tool["ok"] is True
    assert any(c["source"] == "service" for c in body["citations"])


# --------------------------------------------------- hallucination prevention
async def test_validate_citations_filters_ungrounded():
    real = {"source": "incident", "id": "i-1", "label": "Real incident"}
    fake = {"source": "incident", "id": "i-999", "label": "Fabricated"}
    allowed = build_allowed_set([real])
    grounded, hallucinated = validate_citations([real, fake], allowed)
    assert grounded == [real]
    assert hallucinated == [fake]


async def test_response_citations_reference_real_records(client):
    _, t = await create_authenticated_user(client, email="gc4@e.com", username="gc4")
    token = t["access_token"]
    await _team_agent(client, token)
    inc_id = await _poll(client, token, "OutOfMemory in api", "api")

    body = (await _chat(client, token, "Why did api fail?")).json()
    incident_citations = [c for c in body["citations"] if c["source"] == "incident"]
    assert incident_citations
    # Every incident citation id must be a real investigation id (no fabrication).
    assert all(c["id"] for c in incident_citations)
    assert any(c["id"] == inc_id for c in incident_citations)


# ------------------------------------------------------------ confidence
async def test_confidence_low_without_data(client):
    _, t = await create_authenticated_user(client, email="gc5@e.com", username="gc5")
    token = t["access_token"]
    body = (await _chat(client, token, "hello there what can you do")).json()
    assert body["intent"] == "HELP"
    # Help with no grounded records -> low confidence flag.
    assert body["low_confidence"] is True


async def test_confidence_higher_with_grounded_incident(client):
    _, t = await create_authenticated_user(client, email="gc6@e.com", username="gc6")
    token = t["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, "TimeoutError in gateway", "gateway")
    body = (await _chat(client, token, "Why did gateway fail recently?")).json()
    assert body["confidence"] >= settings.COPILOT_MIN_CONFIDENCE
    assert body["grounded"] is True


# ------------------------------------------------------------ retry/fallback
async def test_llm_failure_falls_back_deterministically(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="gc7@e.com", username="gc7")
    token = t["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, "DiskPressure in worker", "worker")

    # Force live mode, make the live call always fail, and disable backoff sleeps.
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "COPILOT_RETRY_BASE_DELAY_SECONDS", 0.0)

    async def _boom(self, system, history, user_prompt):
        raise RuntimeError("provider down")

    monkeypatch.setattr(GroundedLLMClient, "_live_generate", _boom)

    body = (await _chat(client, token, "Why did worker fail?")).json()
    assert body["generation_mode"] == "fallback"
    # Fallback still returns the grounded deterministic answer.
    assert "worker" in body["answer"].lower()
    assert any(c["source"] == "incident" for c in body["citations"])


# ------------------------------------------------------------ streaming
async def test_streaming_sse(client):
    _, t = await create_authenticated_user(client, email="gc8@e.com", username="gc8")
    token = t["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, "PanicCrash in ledger", "ledger")

    resp = await client.post(
        "/v1/copilot/chat/stream", headers=H(token),
        json={"message": "Why did ledger fail?"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = []
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))

    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] == "done"
    done = events[-1]
    assert done["answer"] and "ledger" in done["answer"].lower()
    assert "confidence" in done and "citations" in done


# ------------------------------------------------- conversation history / memory
async def test_conversation_history_persisted(client):
    _, t = await create_authenticated_user(client, email="gc9@e.com", username="gc9")
    token = t["access_token"]
    await _team_agent(client, token)
    await _service(client, token, "checkout")
    await _service(client, token, "payments")
    await _poll(client, token, "checkout down", "checkout")
    await _poll(client, token, "payments down", "payments")

    first = (await _chat(client, token, "Why did checkout fail?")).json()
    cid = first["conversation_id"]
    second = (await _chat(client, token, "what about payments?", conversation_id=cid)).json()
    assert second["conversation_id"] == cid

    detail = (await client.get(f"/v1/copilot/conversations/{cid}", headers=H(token))).json()
    assert len(detail["messages"]) == 4
    assert [m["role"] for m in detail["messages"]] == ["USER", "ASSISTANT", "USER", "ASSISTANT"]

    listed = (await client.get("/v1/copilot/conversations", headers=H(token))).json()
    assert any(c["id"] == cid and c["message_count"] == 4 for c in listed)


# ------------------------------------------------------------ isolation
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="gcA@e.com", username="gcA")
    _, t2 = await create_authenticated_user(client, email="gcB@e.com", username="gcB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _team_agent(client, tok1)
    await _poll(client, tok1, "org1 only incident", "checkout")
    s1 = (await _chat(client, tok1, "Why did checkout fail?")).json()
    cid = s1["conversation_id"]

    # Org 2 cannot read org 1's conversation, and sees none of its data.
    assert (await client.get(f"/v1/copilot/conversations/{cid}", headers=H(tok2))).status_code == 404
    r2 = (await _chat(client, tok2, "Which service caused the most incidents?")).json()
    assert "checkout" not in r2["answer"].lower()
