# DevOps & SRE Workspace (Sprint 63C)

Daily operations platform for DevOps and SRE engineers. Aggregates existing Nexora
platforms into one interface — no duplicate engines.

Package: `app/workspace/`. Service: `app/services/devops_sre_workspace.py`.

## API (`/v1/ops-workspace`)

| Endpoint | Description |
|----------|-------------|
| `GET /my-work` | Personalized prioritized dashboard |
| `GET /queue` | Unified operations queue |
| `GET /changes` | Change center timeline |
| `GET /maintenance` | Maintenance windows and freezes |
| `POST /maintenance` | Schedule maintenance |
| `POST /maintenance/{id}/decide` | Approve/reject maintenance |
| `GET /calendar` | Operations calendar |
| `GET /slo` | SLO center (reuses Service Health + Reliability Dashboard) |
| `GET /cost` | Cost operations (reuses Cost Optimization) |
| `GET /executive` | Executive one-page view |
| `GET /executive/export/pdf` | Export executive view as PDF |
| `POST /briefing/daily` | Generate AI daily briefing → activity feed |
| `GET /briefing/daily/latest` | Latest briefing |
| `POST /handover` | Generate shift handover |
| `GET /handover/latest` | Latest handover |
| `GET /handover/{id}/export/pdf` | Export handover PDF |
| `GET /search?q=` | Unified search (delegates to platform SearchService) |
| `GET /kpis` | Operational KPIs (MTTR, DORA, availability, …) |
| `GET /automation-suggestions` | AI automation suggestions |
| `POST /automation-suggestions/{id}/dismiss` | Dismiss suggestion |
| `POST /ai-context` | Grounded AI side-panel context for Copilot |

## Reused platforms

- **Autonomous SRE** — `OperationsCenterService` (incidents, investigations, predictions)
- **Incidents / Monitoring** — alert and incident repositories
- **Delivery** — deployments, pipeline runs, pending approvals
- **Control Plane** — cluster operations, policy findings (drift/compliance)
- **Service Health** — SLO/error budget overview
- **Reliability Dashboard** — executive metrics and trends
- **Cost Optimization** — spend, waste, recommendations
- **Jobs / Workflows** — failed jobs and workflow executions
- **Activity Feed** — daily briefing storage
- **Search** — `SearchService` unified search
- **Copilot** — AI context endpoint feeds `/v1/copilot/chat`

## Models (`ws_*` tables)

- `ws_maintenance_windows`
- `ws_daily_briefings`
- `ws_shift_handovers`
- `ws_automation_suggestions`
- `ws_calendar_events`

Migration: `0024_workspace`

## Events

- `OpsDailyBriefing`
- `OpsShiftHandover`
- `OpsMaintenanceScheduled`

## AI tools

Registered in `app/ai/tools/ops_workspace.py`:

- `ops_workspace.my_work`
- `ops_workspace.queue`
- `ops_workspace.generate_briefing`
- `ops_workspace.generate_handover`
- `ops_workspace.ai_context`
- `ops_workspace.explain_queue_item`

## Configuration

- `OPS_WORKSPACE_ENABLED=true` (default)

## UI routes

- `/ops-workspace` — My Work dashboard
- `/ops-workspace/queue` — Operations queue
- `/ops-workspace/changes` — Change center
- `/ops-workspace/maintenance` — Maintenance center
- `/ops-workspace/slo` — SLO center
- `/ops-workspace/cost` — Cost operations
- `/ops-workspace/executive` — Executive view
