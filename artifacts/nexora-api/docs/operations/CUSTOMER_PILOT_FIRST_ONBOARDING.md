# Sprint 68A — First Customer Non-Production Pilot Onboarding

Controlled onboarding for one external customer into a scoped non-production pilot. **Not a GA launch.**

## Preconditions

- Sprint 67G GO evidence valid
- Deployment and operations readiness GO
- Customer agrees to scoped pilot terms and in-app-only notifications
- Customer provides non-production environment only
- Named customer approver and Nexora operator assigned

## Phase 1 — Bootstrap customer organization

```bash
cd artifacts/nexora-api
docker compose run --rm -e PYTHONPATH=/app \
  -e DATABASE_URL=postgresql://nexora:nexora@db:5432/nexora \
  -v "$(pwd)/artifacts:/app/artifacts" \
  api python scripts/pilot_sprint68a_customer_bootstrap.py
```

This creates:
- Customer org (`meridian-pilot-np` by default)
- Customer admin user
- Staging `DeliveryEnvironment`
- Pilot enrollment with kickoff scope and contacts
- Updates `PILOT_ORGANIZATION_IDS` in `.env` (restart API to apply)

```bash
docker compose up -d api
```

## Phase 2 — Prepare internal customer non-prod integrations

Customer connects to **their** non-production stack. For internal staging validation, bootstrap the internal pilot stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml up -d pilot-k3s pilot-gitea
./scripts/extract-pilot-k3s-kubeconfig.sh /tmp/pilot-internal-kubeconfig.yaml
./scripts/bootstrap-pilot-gitea.sh /tmp/pilot-internal-gitea
./scripts/pilot_sprint66f_rbac_bootstrap.sh   # namespace RBAC with scale permission
```

## Phase 3 — Run onboarding orchestrator

```bash
docker compose -f docker-compose.yml -f docker-compose.customer-pilot-monitoring.yml run --rm \
  -e PYTHONPATH=/app \
  -e DATABASE_URL=postgresql://nexora:nexora@db:5432/nexora \
  -e PILOT_INTERNAL_KUBECONFIG_PATH=/tmp/pilot-internal-kubeconfig.yaml \
  -v "$(pwd)/artifacts:/app/artifacts" \
  -v /tmp/pilot-internal-gitea:/tmp/pilot-internal-gitea:ro \
  -v /tmp/pilot-internal-kubeconfig.yaml:/tmp/pilot-internal-kubeconfig.yaml:ro \
  api python scripts/pilot_sprint68a_customer_onboarding.py
```

## Evidence directory

`artifacts/customer-pilot-first-customer-onboarding/`

## Hard boundaries

- No production infrastructure or credentials
- No provider mutation during onboarding
- No operation execution in Sprint 68A (unless `PILOT_68A_AUTHORIZE_EXECUTION=1` in a separate authorized sprint)
- Customer portal cannot execute operations
- Operator execution requires typed confirmation in a later sprint

## Outcomes

| Status | Meaning |
|--------|---------|
| `STOP` | Remediation required — do not propose operations |
| `READY_FOR_CUSTOMER_APPROVAL_PACKAGE` | Assessment/baseline complete; customer may review |
| `READY_FOR_OPERATOR_EXECUTION` | Only after explicit separate authorization |

## Related

- [FIRST_CUSTOMER_PILOT_RUNBOOK.md](./FIRST_CUSTOMER_PILOT_RUNBOOK.md)
- [CUSTOMER_PILOT_LAUNCH.md](./CUSTOMER_PILOT_LAUNCH.md)
- [CUSTOMER_INTEGRATION_ONBOARDING.md](./CUSTOMER_INTEGRATION_ONBOARDING.md)
