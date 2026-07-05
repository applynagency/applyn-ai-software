# Grounded Copilot

The grounded copilot replaces the deterministic keyword copilot with a grounded
LLM pipeline. It answers questions about the customer's own reliability data
(incidents, deployments, services, SLOs, dependencies, on-call, cost, capacity)
using **retrieve-then-read**: every answer is grounded in retrieved records, with
citations, confidence scoring, and hallucination prevention. It is strictly
read-only and never returns secrets.

Package: `app/services/grounded_copilot/`. API: `/v1/copilot`.

This is the **single** Copilot. The former SRE Copilot and standalone Reliability
Copilot were merged in (Sprint 60B): their deterministic reliability tooling is
now an internal `EvidenceProvider`
(`app/services/grounded_copilot/evidence.py`) consumed here, and there is exactly
one API (`/v1/copilot`) and one UI page. No legacy copilot routes or service
names remain.

## Architecture

```
question
  │
  ├─ memory            prior conversation turns → chat history + summary
  ├─ tools (read-only) ─┬─ search_reliability_data   (authoritative evidence + citations)
  │                     ├─ get_service_blast_radius  (knowledge graph facts)
  │                     └─ search_incident_knowledge (RAG over incidents)
  ├─ ground            assemble evidence-only prompt (system prompt forbids outside knowledge)
  ├─ generate          LLM answer (retry + backoff) → deterministic fallback / offline
  ├─ validate          hallucination prevention (citations ∈ retrieved) + confidence scoring
  └─ persist           conversation history (copilot_conversations / copilot_messages)
```

### RAG (`retrieval.py`)
A per-request semantic corpus is built from the org's most recent incident
investigations (title, summary, root cause, suspected trigger, recommendations),
embedded with the shared `EmbeddingService` and ranked by cosine similarity
(`COPILOT_RAG_TOP_K`, corpus bounded by `COPILOT_RAG_CORPUS_LIMIT`). Real
embeddings are used when `OPENAI_API_KEY` is set; otherwise a deterministic
offline-hash embedding keeps retrieval (and tests) working without a provider.

### Knowledge graph (`knowledge_graph.py`)
Grounds answers in the service dependency graph: a service's tier, its direct
dependencies, and its transitive downstream dependents (blast radius). Built from
the service catalog (`Service`) + dependency edges (`ServiceDependency`) via the
in-memory `_Graph`.

### Tool calling (`tools.py`)
A read-only tool registry (`TOOL_SPECS` + `CopilotToolExecutor`). Each tool wraps
a tested retrieval path and returns `{text, citations}` where citations reference
real org-scoped records. The engine orchestrates the tools (retrieve-then-read);
`TOOL_SPECS` are also valid Anthropic tool schemas. Tools are never mutating.

### Memory (`memory.py`)
The last `COPILOT_MEMORY_TURNS` turns are replayed as LLM chat history and as a
compact summary for the deterministic path.

### Generation, retry & fallback (`llm.py`)
`GroundedLLMClient` runs the Anthropic completion with exponential-backoff retry
(`COPILOT_MAX_RETRIES`, `COPILOT_RETRY_BASE_DELAY_SECONDS`). Non-retriable errors
(auth/bad-request) skip retries. On exhaustion it falls back to the deterministic
grounded synthesis. When `ANTHROPIC_API_KEY` is unset it runs fully offline
(deterministic). Each turn records its `generation_mode`: `live` / `offline` /
`fallback`.

### Citations, confidence & hallucination prevention (`confidence.py`)
- **Citations** are emitted only for records actually retrieved by the tools.
- **`validate_citations`** drops any citation not in the retrieved allow-set, so a
  fabricated source can never reach the UI.
- **`score_confidence`** produces a 0-100 score from grounding strength (number of
  grounded citations, top RAG similarity, successful tool results), reduced for
  fallback mode and any dropped (hallucinated) citations. Answers below
  `COPILOT_MIN_CONFIDENCE` are flagged `low_confidence`.

## API (`/v1/copilot`)

Org-scoped, audited, read-only. Requires AI-team read permission.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/v1/copilot/chat` | Grounded answer (JSON). |
| `POST` | `/v1/copilot/chat/stream` | Same, streamed as Server-Sent Events. |
| `GET` | `/v1/copilot/conversations` | List conversations. |
| `GET` | `/v1/copilot/conversations/{id}` | Conversation + message history. |
| `GET` | `/v1/copilot/suggested-questions` | Starter questions. |

### Chat response

```json
{
  "conversation_id": "…", "message_id": "…",
  "answer": "…", "intent": "INCIDENT_CAUSE",
  "citations": [{"source": "incident", "id": "…", "label": "…"}],
  "sources":   [{"source": "incident", "id": "…", "label": "…", "score": 0.81}],
  "tool_calls": [{"tool": "search_reliability_data", "input": {…}, "ok": true}],
  "confidence": 73, "grounded": true,
  "generation_mode": "offline", "model": "offline",
  "low_confidence": false, "retrieval_provider": "offline-hash",
  "suggested_questions": ["…"]
}
```

### Streaming (SSE)

`POST /v1/copilot/chat/stream` emits `text/event-stream` lines:

```
data: {"type": "start", "conversation_id": "…", "intent": "…"}
data: {"type": "token", "text": "…"}
...
data: {"type": "done", "message_id": "…", "answer": "…", "citations": [...], "confidence": 73, ...}
```

## Persistence

`copilot_conversations` and `copilot_messages` (model `grounded_copilot.py`).
Assistant turns store the answer plus grounding evidence: `citations`, `sources`,
`tool_calls`, `confidence`, `grounded`, `generation_mode`, `model`. Migration
`0006_grounded_copilot` (idempotent `create(checkfirst=True)`); Alembic HEAD =
`0006_grounded_copilot`.

## Configuration (`app/core/config.py`)

| Setting | Default | Meaning |
| --- | --- | --- |
| `COPILOT_ENABLED` | `True` | Master switch. |
| `COPILOT_MODEL` | `""` | Live model (falls back to `ANTHROPIC_MODEL`). |
| `COPILOT_MAX_TOKENS` | `1500` | Live generation cap. |
| `COPILOT_TEMPERATURE` | `0.2` | Live generation temperature. |
| `COPILOT_MAX_RETRIES` | `2` | Retries before deterministic fallback. |
| `COPILOT_RETRY_BASE_DELAY_SECONDS` | `0.5` | Exponential backoff base. |
| `COPILOT_STREAMING_ENABLED` | `True` | Enable the SSE endpoint. |
| `COPILOT_RAG_TOP_K` | `5` | RAG chunks retrieved. |
| `COPILOT_RAG_CORPUS_LIMIT` | `200` | Records in the per-request RAG corpus. |
| `COPILOT_MEMORY_TURNS` | `8` | Prior turns replayed as memory. |
| `COPILOT_MIN_CONFIDENCE` | `40` | Below this → `low_confidence`. |

## Offline / testability

With `ANTHROPIC_API_KEY` unset (tests/CI) the copilot produces a deterministic,
grounded answer synthesized from the retrieved evidence — no network call. The
same path is the live fallback. Tests (`app/tests/test_grounded_copilot.py`)
cover RAG retrieval, knowledge-graph grounding, tool calling, citation/no-
hallucination guarantees, confidence scoring, retry/fallback, SSE streaming,
conversation history/memory, and tenant isolation.

## Relationship to the legacy copilots

The earlier deterministic copilots (`/v1/reliability-copilot`,
`/v1/sre-copilot`) were removed. Their tested retrieval logic now lives in the
internal `EvidenceProvider` (`EvidenceProvider.gather_evidence`), which the
grounded copilot uses as its authoritative, hallucination-proof evidence tool
before adding the LLM, RAG, graph, memory, streaming, confidence and fallback
layers on top.
