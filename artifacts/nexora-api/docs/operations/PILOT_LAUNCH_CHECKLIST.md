# First Customer Pilot — Launch Checklist

Operational steps for a real non-production pilot. No architecture changes required.

## Prerequisites

- PostgreSQL backup taken and verified (`pg_restore --list <dump>`).
- Deployed API image includes `alembic/versions/0035_pilot_execution.py`.
- One pilot organization UUID chosen (single org only).
- Non-production Kubernetes namespace/cluster, GitHub repo token/App, Prometheus read-only credentials.

## 1. Deploy and migrate

```bash
cd artifacts/nexora-api
docker compose build api
docker compose up -d api db redis
docker compose run --rm --no-deps -v "$(pwd):/app" \
  -e DATABASE_URL=postgresql+asyncpg://nexora:nexora@db:5432/nexora \
  api alembic upgrade head
docker compose run --rm --no-deps -v "$(pwd):/app" \
  -e DATABASE_URL=postgresql+asyncpg://nexora:nexora@db:5432/nexora \
  api alembic heads    # expect: 0035_pilot_execution (head)
docker compose run --rm --no-deps -v "$(pwd):/app" \
  -e DATABASE_URL=postgresql+asyncpg://nexora:nexora@db:5432/nexora \
  api alembic current  # expect: 0035_pilot_execution (head)
curl -s http://localhost:8000/nexora-api/health
```

## 2. Pilot mode configuration (`.env`)

```env
PILOT_MODE_ENABLED=true
PILOT_MODE_ALL_ORGS=false
PILOT_ORGANIZATION_IDS=["<pilot-org-uuid>"]
```

Restart API after editing `.env`:

```bash
docker compose up -d api
```

Confirm Pilot Center API (authenticated):

```bash
curl -s -H "Authorization: Bearer <token>" \
  http://localhost:8000/nexora-api/v1/pilot/execution/status
```

## 3. Enrollment safety limits

After first Pilot Center access creates an enrollment:

```sql
UPDATE pilot_enrollments
SET operation_limit = 2,
    cooldown_minutes = 15,
    kill_switch = false
WHERE organization_id = '<pilot-org-uuid>';
```

## 4. Connect integrations (k8s-github-prometheus path)

Via UI **Integrations** or API:

1. `POST /nexora-api/v1/integrations/connect` — Kubernetes, GitHub, Prometheus (non-prod credentials only).
2. `POST /nexora-api/v1/integrations/connections/{id}/validate` — real probes.
3. Confirm each connection: `lifecycle_state=CONNECTED`, `provider_mode=live`, required capabilities present.

Do **not** proceed if any required integration is `FAILED`, `offline`, or stale.

## 5. Execute pilot stages (strict order)

| Stage | Action |
|-------|--------|
| CONNECT | `POST /v1/pilot/onboarding-paths/k8s-github-prometheus/start` |
| VALIDATE | `POST /v1/pilot/readiness/check` |
| READ_ONLY_ASSESSMENT | `POST /v1/pilot/assessment/run` |
| BASELINE_CAPTURE | `POST /v1/pilot/baseline/capture` (read latest via `GET /v1/pilot/scorecard`) |
| PROPOSE_OPERATION | `POST /v1/pilot/live-operations` (allowlisted template, non-prod env) |
| CUSTOMER_APPROVAL | `POST /v1/pilot/approvals` |
| EXECUTE | `POST /v1/pilot/live-operations/{id}/confirm` |
| VERIFY | Auto + `POST /v1/pilot/live-operations/{id}/verify` if needed |
| COMPLETE | Completes when verification is `VERIFIED` |

Stop on any blocker. Do not skip stages.

## 6. First live operation

Preferred: `restart_deployment` on one unhealthy non-prod deployment.

Before execute: capture K8s status, pods, events, Prometheus health query.

After execute: collect before/after evidence. Mark `VERIFIED` only with real live evidence.

## 7. Completion artifacts

```bash
GET /v1/pilot/evidence-pack/export   # JSON + Markdown + HTML (redacted)
GET /v1/pilot/report/export
GET /v1/pilot/support/diagnostics
```

Keep kill switch available: `POST /v1/pilot/safety/kill-switch` with `{"enabled": true}` if needed.

## Production safety

- Tag production environments `tier=PRODUCTION` — pilot mutations are rejected.
- Never use production kubeconfigs, cloud credentials, or deployment write tokens.
