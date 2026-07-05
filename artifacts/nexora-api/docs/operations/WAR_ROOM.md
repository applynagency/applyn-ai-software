# Collaborative War Room (real-time incident response)

The War Room is an incident-response space shared by **humans and AI
specialists**. It started as an advisory, deterministic multi-agent analysis
(`POST /v1/war-rooms/{id}/execute`, see `app/services/war_room.py`) and is now a
**real-time collaboration surface** on top of that room: live messages, threads,
@mentions, presence, typing indicators, file uploads, pinned evidence, and
human-decided approvals — all streamed over a WebSocket.

Safety invariant is unchanged: **the room is advisory only.** It never executes
remediation, deploys, or rolls anything back. Every approval is decided by a
human.

---

## Architecture

```
WebSocket  ──►  app/api/v1/war_room_collab.py  ──►  WarRoomCollabService
   ▲                       │                              │
   │                       ▼                              ▼
ConnectionManager  ◄── broadcast(event)            repositories (org-scoped)
(app/realtime)             │                              │
   │                       ▼                              ▼
   └────────────  Redis pub/sub broker  ◄──────────  AuditLogRepository
                  (cross-worker fan-out)
```

* **Transport** (`app/realtime/`)
  * `manager.ConnectionManager` — process singleton; tracks live sockets per
    room, delivers broadcast events to every local socket, and derives presence
    from the live connection set.
  * `broker` — Redis pub/sub for **cross-worker** delivery. Each envelope carries
    an `origin` (process id) so a worker ignores the echo of its own publishes.
    With no Redis configured (single worker / tests) broadcast is purely
    in-process — `ConnectionManager` already reaches every local socket.
* **Service** (`app/services/war_room_collab.py`) — all collaboration logic; every
  state change is persisted (org-scoped), audited, and broadcast.
* **Persistence** — extends the existing war-room tables (`app/models/war_room.py`).

The same write operations are exposed over **REST** (for clients that don't hold
an open socket) and over the **WebSocket** (for live participants). Both paths go
through `WarRoomCollabService`, so REST writes are broadcast to live sockets too.

---

## Data model (migration `0007_war_room_collab`)

New columns on `war_room_messages`:

| column | meaning |
| --- | --- |
| `author_type` | `AI` / `HUMAN` / `SYSTEM` |
| `user_id`, `user_name` | the human author (null for AI/SYSTEM) |
| `parent_message_id` | thread root (replies point at the message they answer) |
| `mentions` | resolved `[{type, id, label}]` (user or agent) |

New tables:

* `war_room_participants` — human membership + presence (`is_active`, `last_seen_at`).
* `war_room_attachments` — uploaded files (`storage_path`, `content_type`, `size_bytes`, `kind`).
* `war_room_evidence` — pinned evidence (references an attachment or an existing record).
* `war_room_approvals` — war-room-scoped approvals (`PENDING` → `APPROVED`/`REJECTED`).

The migration is idempotent (inspector-guarded column adds + ORM
`create(checkfirst=True)` for tables), matching the project convention. The
`HEAD` constant in `app/tests/test_migration_check.py` is bumped to
`0007_war_room_collab`.

---

## Capabilities

### Live messages & threads
`POST /v1/war-rooms/{id}/messages` posts a human message; it is persisted and
broadcast (`type: "message"`). Replies set `parent_message_id`; one level of
nesting (a reply to a reply attaches to the same thread root). Read a thread with
`GET /v1/war-rooms/{id}/messages/{mid}/thread`.

### Mentions → AI participants
A message may carry `mentions: ["SRE", "<user-id-or-username>"]`. Tokens are
resolved against org membership (unknown tokens are dropped — no dangling
mentions). Mentioning an **AI agent** (`SRE`, `CTO`, `KUBERNETES`, `GITHUB`,
`DATABASE`, `SECURITY`, or `COPILOT`) **invites it to respond**: the service calls
the Copilot's deterministic evidence provider
(`EvidenceProvider.gather_evidence`) to produce a **grounded, cited**
answer (every citation references a real record — hallucination-proof and
offline-safe) and posts it as an AI message threaded under the human message.
`POST /v1/war-rooms/{id}/ai` invites an AI participant directly.

### Presence & typing
Presence is derived from live WebSocket connections (`ConnectionManager.presence`).
Joining (`POST .../join`, or simply connecting the socket) records a participant
and broadcasts `participant_joined` + `presence`. Typing indicators are
ephemeral (`type: "typing"`, never persisted). On socket disconnect the
participant's `last_seen_at` is updated and `presence` is re-broadcast.

### Uploads & evidence
`POST /v1/war-rooms/{id}/uploads` (multipart) stores a file under
`WAR_ROOM_UPLOAD_DIR/<room>/`, validated against `WAR_ROOM_ALLOWED_UPLOAD_TYPES`
and `WAR_ROOM_MAX_UPLOAD_BYTES`. Files are served only through the **org-scoped**
download endpoint (`GET .../uploads/{aid}`), never the public `/static` mount.
`POST /v1/war-rooms/{id}/evidence` pins an evidence item that references an
attachment or an existing record (`source_type`/`source_id`).

### Approvals (human-decided)
`POST /v1/war-rooms/{id}/approvals` opens a `PENDING` approval; a privileged user
(`can_write_ai_teams`) decides it via
`POST .../approvals/{aid}/decision` with `{"decision": "APPROVE"|"REJECT"}`.
Re-deciding a settled approval returns `400`. Every decision is audited and
broadcast (`approval_decided`).

---

## WebSocket protocol

```
WS /v1/war-rooms/{id}/ws?token=<access_token>
```

Auth mirrors the HTTP dependencies manually (WebSockets can't use the bearer
dependency): the token is decoded, the user loaded, and org membership/role
resolved. Invalid token → close `4401`; unknown room / no read access → close
`4404`; realtime disabled → close `4503`.

On connect the server sends a `connected` snapshot (recent messages,
participants, online list) and broadcasts updated `presence`.

**Client → server frames**

| frame | effect |
| --- | --- |
| `{"type":"message","content":...,"parent_message_id"?,"mentions"?}` | post a live message (broadcast; AI auto-responds to agent mentions) |
| `{"type":"typing","is_typing":true}` | broadcast a typing indicator |
| `{"type":"ai","prompt":...,"agent"?,"parent_message_id"?}` | invite an AI participant; **streams** `ai_token` chunks, then a final `message` |
| `{"type":"presence"}` | request a presence re-broadcast |
| `{"type":"ping"}` | server replies `{"type":"pong"}` |

**Server → client events**: `connected`, `message`, `ai_token` (streaming
chunks), `participant_joined`, `participant_left`, `presence`, `typing`,
`attachment`, `evidence`, `approval_requested`, `approval_decided`, `error`.

---

## Configuration (`app/core/config.py`)

| setting | default | purpose |
| --- | --- | --- |
| `WAR_ROOM_REALTIME_ENABLED` | `True` | enable the WebSocket endpoint |
| `WAR_ROOM_UPLOAD_DIR` | `uploads/war_room` | upload storage root |
| `WAR_ROOM_MAX_UPLOAD_BYTES` | `26214400` (25 MiB) | per-file size limit |
| `WAR_ROOM_ALLOWED_UPLOAD_TYPES` | images/pdf/text/json/zip | accepted MIME types |
| `WAR_ROOM_AI_STREAM_CHUNK` | `48` | AI streaming chunk size |
| `WAR_ROOM_PUBSUB_PREFIX` | `warroom` | Redis channel prefix |

Cross-worker broadcast uses the shared Redis client (`REDIS_URL`). Without Redis
everything still works on a single worker.

---

## Security & multi-tenancy

* Every endpoint requires an organization context and `can_read_ai_teams`
  (participate) / `can_write_ai_teams` (decide approvals); superusers bypass.
* All queries are organization-scoped; a user in another org gets `404` for the
  room (tenant isolation is tested).
* Uploads are validated by type/size and only downloadable through the
  org-scoped endpoint.
* Every write (`message`, `ai_message`, `joined`, `upload`, `evidence_added`,
  `approval_requested`, `approval_decided`) is recorded via
  `AuditLogRepository` (tamper-evident hash chain — see `AUDIT.md`).

---

## Offline / testability

The AI participant uses the deterministic evidence pipeline, so it works without
any LLM key. The realtime layer needs no Redis for a single worker. WebSocket
behaviour is covered by driving `war_room_ws` with an in-process fake socket
(auth, join, snapshot, live message, typing, AI-token streaming, presence on
disconnect), plus `ConnectionManager`/broker unit tests and the full REST
collaboration surface. See `app/tests/test_war_room_collab.py`.
