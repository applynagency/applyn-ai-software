# Nexora AI Development Team

A multi-agent software delivery platform where users submit business requirements and an AI Product Owner Agent (Claude) generates Epics, Features, User Stories, Acceptance Criteria, Story Points, Sprint Plans, and Risks.

## Run & Operate

- `bash artifacts/nexora-api/start.sh` — start the Nexora API server (port 8001)
- `pnpm --filter @workspace/api-server run dev` — run the shared API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `SESSION_SECRET`

## Stack

- **Runtime**: Python 3.12, FastAPI, Uvicorn
- **Database**: PostgreSQL + SQLAlchemy async + Alembic
- **Validation**: Pydantic v2
- **Auth**: JWT (access + refresh tokens), bcrypt password hashing
- **AI**: Anthropic Claude (`claude-sonnet-4-6`) via `anthropic` Python SDK
- **Logging**: structlog (JSON format)
- **Node workspace**: pnpm workspaces, Node.js 24, TypeScript 5.9

## Where things live

- `artifacts/nexora-api/` — main FastAPI application
  - `app/agents/product_owner.py` — AI Product Owner Agent (Claude integration)
  - `app/api/v1/` — route handlers (auth, workspaces, projects, requirements, agents)
  - `app/models/` — SQLAlchemy ORM models
  - `app/schemas/` — Pydantic v2 request/response schemas
  - `app/repositories/` — async database repositories
  - `app/services/` — business logic layer
  - `app/workflows/engine.py` — agent workflow orchestration
  - `app/core/config.py` — settings (reads env vars)
  - `alembic/` — database migrations
- `artifacts/api-server/` — shared Node.js API server (separate product)

## Architecture decisions

- Clean architecture: routes → services → repositories → models
- All DB access is async via SQLAlchemy 2.x async sessions
- Claude prompt instructs compact JSON output (under 6000 tokens) to avoid truncation
- `max_tokens=16000` for Claude to handle complex requirement outputs
- Slug generation uses `model_validator(mode="after")` so `name` is available when slug is computed
- sslmode stripped from DATABASE_URL in config validator (asyncpg doesn't accept it in URL)
- bcrypt used directly (not via passlib) to avoid version incompatibility

## Product

- **User auth**: register, login, refresh token, JWT-protected routes
- **Workspaces**: multi-tenant workspace management
- **Projects**: projects within workspaces
- **Requirements**: business requirements submission
- **Product Owner Agent**: Claude AI analyzes requirements and outputs:
  - Epics → Features → User Stories
  - Acceptance Criteria + Story Points
  - Sprint Plan
  - Risks & Assumptions
  - Tech Stack Recommendations

## API Endpoints

All routes prefixed with `/nexora-api/v1/`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/nexora-api/health` | Health check |
| POST | `/v1/auth/register` | Register (email, username, full_name, password) |
| POST | `/v1/auth/login` | Login → JWT tokens |
| POST | `/v1/auth/refresh` | Refresh access token |
| CRUD | `/v1/workspaces` | Workspace management |
| CRUD | `/v1/projects` | Project management |
| CRUD | `/v1/requirements` | Requirements management |
| POST | `/v1/agents/product-owner/run` | Trigger Product Owner Agent |
| GET | `/v1/agents/runs` | List agent runs |
| GET | `/v1/agents/runs/{id}` | Get agent run + output |

Interactive docs: `/nexora-api/docs`

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- Register requires: `email`, `username`, `full_name`, `password` (all four fields)
- Claude may take 60-120s for complex requirements — consider async background task pattern for production
- Always run `pnpm --filter @workspace/db run push` after schema changes (dev only; use Alembic for prod)
- `ANTHROPIC_MAX_TOKENS` is 16000 — do not lower below 8192 or large requirement outputs get truncated

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
