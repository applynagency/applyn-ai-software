# Enterprise Incident Response & On-Call Platform (Sprint 65C)

Unified incident management layer extending on-call, escalation, lifecycle, war room,
postmortem, Autonomous SRE, and observability — **no duplicate engines**.

## Architecture

`IncidentResponsePlatformService` orchestrates:

| Capability | Reused engine |
|------------|---------------|
| On-call schedules | `OnCallService` |
| Escalation | `EscalationEngine` |
| Lifecycle | `IncidentLifecycleService` |
| Major incidents / war room | `WarRoomService` |
| Postmortems | `PostmortemService` |
| AI coordination | `coordinate_incident()` + SRE patterns |
| Analytics | `OnCallMetricsService` + `compute_analytics()` |
| Status pages | New `ir_*` persistence + public view builder |

All data is **organization scoped**.

## API (`/v1/incidents/*`)

| Endpoint | Description |
|----------|-------------|
| `GET /oncall` | On-call dashboard, current shifts, overrides |
| `POST /oncall/overrides` | Vacation / temporary replacement |
| `GET /escalation` | Escalation policies and recent events |
| `POST /escalation/run` | Process due escalations |
| `GET/POST /status-pages` | Status page management |
| `GET /status-pages/{slug}/public` | Public/JSON status view |
| `GET/POST /communications` | Communications hub |
| `GET /postmortems` | Postmortem dashboard |
| `POST /postmortems/{id}/generate` | Generate postmortem |
| `GET /analytics` | MTTR, MTTA, trends, workload |
| `GET/POST /major` | Major incident management |
| `POST /coordinate` | AI incident coordinator |

## Domain events

- `OnCallStarted`, `OnCallEnded`
- `EscalationTriggered`, `EscalationSucceeded`
- `MajorIncidentStarted`, `MajorIncidentEnded`
- `StatusPageUpdated`, `PostmortemGenerated`, `ResponderAssigned`

## AI tools (grounded)

- `incident.find_best_responder`
- `incident.summarize`
- `incident.generate_status_update`
- `incident.predict_severity`
- `incident.generate_postmortem`
- `incident.explain_timeline`
- `incident.suggest_actions`

## Prometheus metrics

- `nexora_ir_open_incidents`
- `nexora_ir_mtta_minutes`, `nexora_ir_mttr_minutes`
- `nexora_ir_escalation_duration_seconds`
- `nexora_ir_notification_duration_seconds`
- `nexora_ir_oncall_coverage`
- `nexora_ir_status_page_updates_total`

## Configuration

- `INCIDENT_RESPONSE_PLATFORM_ENABLED=true` (default)

## Database

Migration `0029_incident_response` creates `ir_*` tables for status pages, communications, major incidents, overrides, and coordinator runs.

## UI

Pages under `/incident-response/*` in the Incidents nav module.
