"""Tests for the collaborative (real-time) War Room.

Covers the REST collaboration surface (join/presence, live messages, threads,
@mentions that invite AI participants, file uploads, evidence, approvals,
tenant isolation), the in-process realtime layer (ConnectionManager presence +
broadcast, no-Redis broker fallback), and the WebSocket endpoint itself driven
through a fake socket (auth, join, initial snapshot, live message + typing +
AI-token streaming broadcast, presence on disconnect).

Everything runs offline/deterministic (no Redis, no live LLM).
"""

import pytest
from fastapi import WebSocketDisconnect

from app.api.v1.war_room_collab import war_room_ws
from app.realtime import broker
from app.realtime.manager import ConnectionManager
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _setup_room(client, *, email, username, title="Collab Room"):
    _, tokens = await create_authenticated_user(client, email=email, username=username)
    token = tokens["access_token"]
    room = (await client.post("/v1/war-rooms", headers=H(token),
                              json={"incident_id": None, "title": title})).json()
    return token, room["id"]


# ================================ REST: participants / presence ===========
async def test_join_and_list_participants(client):
    token, room_id = await _setup_room(client, email="c1@e.com", username="col1")
    r = await client.post(f"/v1/war-rooms/{room_id}/join", headers=H(token))
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["is_active"] is True

    parts = (await client.get(f"/v1/war-rooms/{room_id}/participants", headers=H(token))).json()
    assert len(parts) == 1
    assert parts[0]["user_id"] == me["user_id"]


async def test_presence_snapshot(client):
    token, room_id = await _setup_room(client, email="c2@e.com", username="col2")
    await client.post(f"/v1/war-rooms/{room_id}/join", headers=H(token))
    pres = (await client.get(f"/v1/war-rooms/{room_id}/presence", headers=H(token))).json()
    assert pres["war_room_id"] == room_id
    assert pres["online"] == []  # no live socket in a pure REST call
    assert len(pres["participants"]) == 1


# ================================ REST: live messages / threads ===========
async def test_post_and_list_messages(client):
    token, room_id = await _setup_room(client, email="c3@e.com", username="col3")
    r = await client.post(f"/v1/war-rooms/{room_id}/messages", headers=H(token),
                          json={"content": "Service is down", "message_type": "INFO"})
    assert r.status_code == 201, r.text
    msg = r.json()
    assert msg["author_type"] == "HUMAN"
    assert msg["content"] == "Service is down"
    assert msg["user_id"]

    msgs = (await client.get(f"/v1/war-rooms/{room_id}/messages", headers=H(token))).json()
    # system opener + our message
    assert any(m["content"] == "Service is down" for m in msgs)
    assert msgs == sorted(msgs, key=lambda m: m["sequence"])


async def test_threaded_reply(client):
    token, room_id = await _setup_room(client, email="c4@e.com", username="col4")
    root = (await client.post(f"/v1/war-rooms/{room_id}/messages", headers=H(token),
                              json={"content": "root question"})).json()
    reply = (await client.post(f"/v1/war-rooms/{room_id}/messages", headers=H(token),
                               json={"content": "a reply", "parent_message_id": root["id"]})).json()
    assert reply["parent_message_id"] == root["id"]

    thread = (await client.get(
        f"/v1/war-rooms/{room_id}/messages/{root['id']}/thread", headers=H(token))).json()
    assert [m["content"] for m in thread] == ["a reply"]


async def test_unknown_parent_404(client):
    token, room_id = await _setup_room(client, email="c5@e.com", username="col5")
    r = await client.post(f"/v1/war-rooms/{room_id}/messages", headers=H(token),
                          json={"content": "x", "parent_message_id": "nope"})
    assert r.status_code == 404


# ================================ mentions -> AI participant ===============
async def test_mention_agent_invites_ai_response(client):
    token, room_id = await _setup_room(client, email="c6@e.com", username="col6")
    r = await client.post(f"/v1/war-rooms/{room_id}/messages", headers=H(token),
                          json={"content": "what's the status @SRE?", "mentions": ["SRE"]})
    assert r.status_code == 201, r.text
    human = r.json()
    assert any(m["type"] == "agent" and m["id"] == "SRE" for m in human["mentions"])

    msgs = (await client.get(f"/v1/war-rooms/{room_id}/messages", headers=H(token))).json()
    ai = [m for m in msgs if m["author_type"] == "AI"]
    assert ai, "AI agent should have responded to the mention"
    assert ai[-1]["agent"] == "SRE"
    assert ai[-1]["parent_message_id"] == human["id"]


async def test_unknown_mention_dropped(client):
    token, room_id = await _setup_room(client, email="c7@e.com", username="col7")
    r = await client.post(f"/v1/war-rooms/{room_id}/messages", headers=H(token),
                          json={"content": "hi @ghost", "mentions": ["ghost-user-id"]})
    assert r.status_code == 201
    assert r.json()["mentions"] == []


async def test_ai_invite_endpoint(client):
    token, room_id = await _setup_room(client, email="c8@e.com", username="col8")
    r = await client.post(f"/v1/war-rooms/{room_id}/ai", headers=H(token),
                          json={"prompt": "summarize current incidents"})
    assert r.status_code == 201, r.text
    assert r.json()["author_type"] == "AI"


# ================================ uploads / evidence ======================
async def test_upload_list_and_download(client):
    token, room_id = await _setup_room(client, email="c9@e.com", username="col9")
    files = {"file": ("trace.txt", b"stacktrace contents", "text/plain")}
    r = await client.post(f"/v1/war-rooms/{room_id}/uploads", headers=H(token), files=files)
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["filename"] == "trace.txt"
    assert att["size_bytes"] == len(b"stacktrace contents")

    listing = (await client.get(f"/v1/war-rooms/{room_id}/uploads", headers=H(token))).json()
    assert len(listing) == 1

    dl = await client.get(f"/v1/war-rooms/{room_id}/uploads/{att['id']}", headers=H(token))
    assert dl.status_code == 200
    assert dl.content == b"stacktrace contents"


async def test_unsupported_upload_type_rejected(client):
    token, room_id = await _setup_room(client, email="c10@e.com", username="c10")
    files = {"file": ("evil.exe", b"MZ", "application/x-msdownload")}
    r = await client.post(f"/v1/war-rooms/{room_id}/uploads", headers=H(token), files=files)
    assert r.status_code == 415


async def test_evidence_links_attachment(client):
    token, room_id = await _setup_room(client, email="c11@e.com", username="c11")
    files = {"file": ("graph.png", b"\x89PNG\r\n", "image/png")}
    att = (await client.post(f"/v1/war-rooms/{room_id}/uploads", headers=H(token), files=files)).json()

    r = await client.post(f"/v1/war-rooms/{room_id}/evidence", headers=H(token),
                          json={"title": "Latency chart", "description": "p99 spike",
                                "source_type": "attachment", "attachment_id": att["id"]})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["attachment_id"] == att["id"]

    listing = (await client.get(f"/v1/war-rooms/{room_id}/evidence", headers=H(token))).json()
    assert len(listing) == 1


# ================================ approvals ===============================
async def test_approval_request_and_approve(client):
    token, room_id = await _setup_room(client, email="c12@e.com", username="c12")
    ap = (await client.post(f"/v1/war-rooms/{room_id}/approvals", headers=H(token),
                            json={"title": "Roll back checkout", "kind": "REMEDIATION"})).json()
    assert ap["status"] == "PENDING"

    decided = await client.post(
        f"/v1/war-rooms/{room_id}/approvals/{ap['id']}/decision", headers=H(token),
        json={"decision": "APPROVE", "reason": "validated in staging"})
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "APPROVED"
    assert body["decided_by"]


async def test_approval_double_decision_rejected(client):
    token, room_id = await _setup_room(client, email="c13@e.com", username="c13")
    ap = (await client.post(f"/v1/war-rooms/{room_id}/approvals", headers=H(token),
                            json={"title": "Scale db"})).json()
    await client.post(f"/v1/war-rooms/{room_id}/approvals/{ap['id']}/decision", headers=H(token),
                      json={"decision": "REJECT"})
    again = await client.post(f"/v1/war-rooms/{room_id}/approvals/{ap['id']}/decision",
                              headers=H(token), json={"decision": "APPROVE"})
    assert again.status_code == 400


# ================================ tenant isolation ========================
async def test_tenant_isolation(client):
    token_a, room_id = await _setup_room(client, email="iso-a@e.com", username="isoa")
    _, tokens_b = await create_authenticated_user(client, email="iso-b@e.com", username="isob")
    token_b = tokens_b["access_token"]

    r = await client.get(f"/v1/war-rooms/{room_id}/messages", headers=H(token_b))
    assert r.status_code == 404


# ================================ realtime: manager =======================
class _FakeSocket:
    def __init__(self, token: str = "", frames=None):
        self.query_params = {"token": token} if token else {}
        self.headers = {}
        self.sent: list[dict] = []
        self._frames = list(frames or [])
        self.accepted = False
        self.closed_code = None

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent.append(data)

    async def receive_json(self):
        if self._frames:
            return self._frames.pop(0)
        raise WebSocketDisconnect()

    async def close(self, code=1000):
        self.closed_code = code


async def test_manager_broadcast_and_presence():
    m = ConnectionManager()
    a, b = _FakeSocket(), _FakeSocket()
    ca = await m.connect("room", a, user_id="u1", user_name="A", role="OWNER")
    await m.connect("room", b, user_id="u2", user_name="B", role="MEMBER")

    await m.broadcast("room", {"type": "ping"})
    assert {"type": "ping"} in a.sent
    assert {"type": "ping"} in b.sent

    presence = {p["user_id"] for p in m.presence("room")}
    assert presence == {"u1", "u2"}

    m.disconnect("room", ca)
    assert {p["user_id"] for p in m.presence("room")} == {"u2"}
    m.reset()


async def test_broker_without_redis_is_noop():
    assert await broker.publish("room", {"a": 1}) is False
    items = [x async for x in broker.subscribe("room")]
    assert items == []


# ================================ WebSocket endpoint ======================
async def test_ws_rejects_bad_token():
    sock = _FakeSocket(token="not-a-real-token")
    await war_room_ws(sock, "any-room")
    assert sock.accepted is False
    assert sock.closed_code == 4401


async def test_ws_unknown_room_closes(client):
    token, _ = await _setup_room(client, email="ws0@e.com", username="ws0")
    sock = _FakeSocket(token=token)
    await war_room_ws(sock, "no-such-room")
    assert sock.accepted is True
    assert sock.closed_code == 4404


async def test_ws_live_message_flow(client):
    token, room_id = await _setup_room(client, email="ws1@e.com", username="ws1")
    sock = _FakeSocket(token=token, frames=[
        {"type": "message", "content": "ws hello"},
        {"type": "typing", "is_typing": True},
    ])
    await war_room_ws(sock, room_id)

    types = [e.get("type") for e in sock.sent]
    assert "connected" in types
    # the connected snapshot includes the opener message and the joining participant
    connected = next(e for e in sock.sent if e["type"] == "connected")
    assert connected["data"]["participants"]
    # our posted message was broadcast back to us
    messages = [e for e in sock.sent if e.get("type") == "message"]
    assert any(e["data"]["content"] == "ws hello" for e in messages)
    # typing indicator broadcast
    assert any(e.get("type") == "typing" for e in sock.sent)
    # presence broadcast happened
    assert any(e.get("type") == "presence" for e in sock.sent)


async def test_ws_ai_token_streaming(client):
    token, room_id = await _setup_room(client, email="ws2@e.com", username="ws2")
    sock = _FakeSocket(token=token, frames=[
        {"type": "ai", "prompt": "what is happening", "agent": "COPILOT"},
    ])
    await war_room_ws(sock, room_id)

    assert any(e.get("type") == "ai_token" for e in sock.sent)
    ai_messages = [e for e in sock.sent
                   if e.get("type") == "message" and e["data"]["author_type"] == "AI"]
    assert ai_messages


@pytest.mark.parametrize("frame", [{"type": "ping"}])
async def test_ws_ping_pong(client, frame):
    token, room_id = await _setup_room(client, email="ws3@e.com", username="ws3")
    sock = _FakeSocket(token=token, frames=[frame])
    await war_room_ws(sock, room_id)
    assert any(e.get("type") == "pong" for e in sock.sent)
