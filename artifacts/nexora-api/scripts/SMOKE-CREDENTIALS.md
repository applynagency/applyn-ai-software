# Nexora local smoke credentials

Use these for local Docker dev at `http://localhost:8000`.

## Primary smoke user (has Jenkins connected)

| Field | Value |
|-------|--------|
| **Email** | `browser-smoke-1783108438688@example.com` |
| **Password** | `SmokeTest123!` |
| **Organization** | Browser Smoke's Organization |

### Jenkins connection (verified)

| Field | Value |
|-------|--------|
| **Connection ID** | `3cc1e214-9138-4193-b64b-04bce87965fc` |
| **Integration** | JENKINS |
| **Status** | VERIFIED / HEALTHY |
| **Permissions** | `jobs:read` |

### Quick verify

```bash
cd artifacts/nexora-api
NEXORA_EMAIL="browser-smoke-1783108438688@example.com" \
NEXORA_PASSWORD="SmokeTest123!" \
node scripts/verify-jenkins-connection.mjs
```

## Wrong account (do not use for Jenkins tests)

| Field | Value |
|-------|--------|
| Email | `browser-smoke-1783109644408@example.com` |
| Note | Has **0** Jenkins connections |

## Deploy after code changes

```bash
cd artifacts/nexora-api
docker compose build api && docker compose up -d api
docker compose exec -T api alembic upgrade head
```

## P0: Auto alert → incident → AI investigate

Local Docker (`docker-compose.override.yml`) enables:

| Env var | Value | Effect |
|---------|-------|--------|
| `MONITORING_ENABLED` | `true` | In-process monitoring loop (~60s) polls Jenkins + other providers |
| `ESCALATION_ENABLED` | `true` | On-call escalation scheduler (~60s) advances policies |
| `UNIVERSAL_DISCOVERY_ENABLED` | `true` | Background discovery sync for connected cloud/K8s integrations |
| `INTEGRATION_PIPELINE_SYNC_ENABLED` | `true` | Syncs pipeline runs every ~5 min (no `--profile jobs` needed) |
| `INTEGRATION_GITOPS_SYNC_ENABLED` | `true` | Refreshes GitOps app state from Argo CD every ~5 min |
| `WAR_ROOM_REALTIME_ENABLED` | `true` | Live war room chat + presence on `/war-rooms` |
| `JOB_QUEUE_ENABLED` | `false` | Schedulers run inside the API container |

### Verify the loop

1. Log in as the smoke user above.
2. Open **Alerts** (`/alerts`) and click **Poll providers now**, or wait ~60s.
3. A failed Jenkins build should create an alert → auto-incident → **RCA & fixes** on the incident page.

Optional: run the worker profile for Arq cron instead of in-process loops:

```bash
docker compose --profile jobs up -d worker
```

## P1: Governed actions & triage

| Feature | How |
|---------|-----|
| **Investigate alert** (WARNING+) | Alerts page → **Investigate → incident** or `POST /v1/monitoring/alerts/{id}/investigate` |
| **Approve & execute fix** | Incident page → **What to do next** → Approve (requires action bound to infra) |
| **Postmortem draft** | Incident page → **Generate postmortem draft** |
| **RCA in notifications** | Auto-incident sends suspected cause + top fix to Slack/email (when `NOTIFICATIONS_ENABLED=true`) |

## Key URLs

- AI Ops Command Center: `/`
- Incidents (RCA + logs + fix suggestions): `/incidents`
- Alerts (poll + auto-incident): `/alerts`
- Integrations health board: `/integrations`
- On-call schedules: `/incidents/on-call`

## P3: Operational evidence on incidents

| Feature | How |
|---------|-----|
| **Log excerpt** | Incident detail loads `/v1/incidents/{id}/evidence` — searches connected log backends |
| **Jenkins console tail** | Failed Jenkins alerts show build console excerpt on incident page |
| **Metrics snapshot** | Top discovered metrics on incident evidence panel |
| **Alert detail drawer** | Alerts page → **Details** expands labels + investigate |
| **On-call schedule UI** | `/incidents/on-call` → create schedule form (no API-only) |

## Production SRE loop (required env flags)

`app/core/config.py` defaults schedulers to `false` for safe cold starts. Enable these in production (or staging) for the full alert → incident → escalation → discovery loop:

| Env var | Recommended | Effect |
|---------|-------------|--------|
| `MONITORING_ENABLED` | `true` | Polls connected observability/CI providers for alerts |
| `ESCALATION_ENABLED` | `true` | Runs on-call escalation policies |
| `UNIVERSAL_DISCOVERY_ENABLED` | `true` | Syncs architecture/inventory from cloud and K8s connections |
| `INTEGRATION_PIPELINE_SYNC_ENABLED` | `true` | Keeps pipeline runs current for DORA and delivery views |
| `INTEGRATION_GITOPS_SYNC_ENABLED` | `true` | Refreshes Argo CD GitOps app inventory periodically |
| `WAR_ROOM_REALTIME_ENABLED` | `true` | Enables war room WebSocket + live collaboration UI |
| `NOTIFICATIONS_ENABLED` | `true` | Delivers Slack/Teams/email on incidents (when webhooks configured) |

### Live logs search

Connect **Loki**, **Elasticsearch**, or **CloudWatch** under **Integrations**. `/logs` resolves marketplace credentials automatically (LOKI → ELASTIC → CLOUDWATCH priority).

### P1: Live metrics + per-org notifications

| Feature | How |
|---------|-----|
| **Live metrics** | Connect **Prometheus** or **Datadog** → **Observe → Metrics** (`/metrics`) runs live PromQL/queries |
| **Org notification webhooks** | **Settings → Notifications** — save Slack/Teams webhook URLs and PagerDuty routing key per org |
| **PagerDuty outbound** | Add `pagerduty` to escalation policy channels or default channels — triggers Events API v2 |
| **SonarQube security scan** | Connect SonarQube → **Security** → run SAST scan with project key as target |

### P2: GitOps write, war room realtime, PE live paths

| Feature | How |
|---------|-----|
| **Argo CD live sync** | Connect Argo CD → **Delivery → GitOps** → **Sync** on drifted apps (`POST /v1/delivery/gitops/apps/{name}/sync`) |
| **GitOps state scheduler** | `INTEGRATION_GITOPS_SYNC_ENABLED=true` refreshes Argo app inventory every ~5 min |
| **War room realtime** | `WAR_ROOM_REALTIME_ENABLED=true` → `/war-rooms` shows live chat + WebSocket presence |
| **Terraform Cloud plan** | Connect Terraform Cloud → PE IaC stack with `terraform_workspace_id` in variables → PLAN uses live TFC API |
| **Vault secret ref metadata** | Connect HashiCorp Vault → create PE secret ref with `VAULT` backend — live KV metadata when reachable |
