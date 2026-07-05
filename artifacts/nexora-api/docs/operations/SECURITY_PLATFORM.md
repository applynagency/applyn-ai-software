# Enterprise DevSecOps & Cloud Security Platform (Sprint 65D)

Unified security findings, posture, compliance, and remediation — extending Delivery scans,
Control Plane K8s policies, Platform Engineering compliance, and identity security.

## Architecture

`SecurityPlatformService` orchestrates:

| Capability | Reused engine |
|------------|---------------|
| Code/container/dependency scans | `app/delivery/security/scanners.py` (offline adapters) |
| K8s posture | CIS/PSS-compatible adapter + `cp_policy_findings` patterns |
| Cloud posture | `platform_engineering/compliance/checks.py` |
| IaC policy | Checkov/OPA-compatible offline adapter |
| IAM review | Access review campaigns + IAM scan adapter |
| Remediation | Proposal → approval pattern (no direct execution) |
| Investigations | Correlation with alerts, incidents, deployments |

**All scanner adapters are offline/simulated unless real credentials are configured.**

## Canonical finding model (`sec_findings`)

Lifecycle: `OPEN` → `ACKNOWLEDGED` → `IN_REMEDIATION` → `RESOLVED` (also `ACCEPTED_RISK`, `FALSE_POSITIVE`, `EXPIRED`)

Deduplication via `fingerprint` unique per organization.

## API (`/v1/security/*`)

| Endpoint | Description |
|----------|-------------|
| `GET /overview` | Posture score, open critical, pending remediations |
| `GET/POST /scans` | Run and list security scans |
| `GET /findings` | Paginated canonical findings |
| `POST /findings/{id}/transition` | Lifecycle transitions |
| `GET /vulnerabilities` | CVE-focused view |
| `GET /sbom` | SBOM inventory |
| `GET /kubernetes` | K8s security score |
| `GET /cloud` | Cloud posture |
| `GET /iac` | IaC policy violations |
| `GET /identity` | IAM/access review |
| `GET /compliance` | Compliance mapping |
| `GET/POST /exceptions` | Risk exceptions |
| `GET/POST /remediation` | Approval-gated proposals |
| `GET /analytics` | Posture analytics |
| `GET/POST /investigations` | Security timelines |

## Domain events

`SecurityFindingCreated`, `SecurityFindingUpdated`, `CriticalVulnerabilityDetected`, `SecretDetected`, `PolicyViolationDetected`, `SecurityScoreChanged`, `SecurityRemediationProposed`, `SecurityRemediationExecuted`, `SecurityExceptionGranted`, `SecurityIncidentCreated`

## AI tools (grounded, redacted)

`security.explain_finding`, `prioritize_risks`, `find_attack_surface`, `explain_cve_impact`, `recommend_remediation`, `review_iac_plan`, `analyze_rbac`, `generate_exception_justification`

## Prometheus metrics

`nexora_security_findings_total`, `nexora_security_open_critical_findings`, `nexora_security_scan_duration_seconds`, `nexora_security_remediation_total`, `nexora_security_posture_score`, `nexora_security_exception_total`, `nexora_security_sla_breaches_total`

## Configuration

`SECURITY_PLATFORM_ENABLED=true` (default)

## Migration

`0030_security_platform` (Sprint 65D) → `0031_security_production` (Sprint 65E, HEAD)

---

# Production Integration (Sprint 65E)

Extends 65D with live provider execution, historical backfill, SBOM parsing, remediation execution binding, SLAs, and policy gates.

## Production providers

Per-organization `sec_providers` with modes: `live` | `offline` | `unavailable`.

Supported types: Trivy, Gitleaks, Semgrep/CodeQL-compatible, Checkov/tfsec-compatible, SBOM parser (SPDX/CycloneDX).

Live mode requires binary on PATH **and** `enabled=true`. Never reported as live without validation.

Subprocess execution uses `app/security_platform/executor.py` (allowlists, timeout, output caps, secret redaction).

## Historical backfill

Idempotent import from `cp_policy_findings`, `dlv_security_scans`, `pe_compliance_reports`, `pe_drift_findings` into `sec_findings`.

Preserves `source_system`, `source_record_id`, `imported_at`. Does not delete sources.

Admin APIs: `POST /backfill/dry-run`, `POST /backfill/execute`, `GET /backfill/status`.

## Remediation execution

Approved proposals bind to `ExecutionEngine` via `sec_remediation_executions` (checkpoints, verification, rollback metadata).

High-risk actions always require approval. Failed execution does not resolve findings.

## SLA & gates

`sec_sla_policies` drive due dates, breach detection, and IR escalation for critical overdue findings.

Gate decisions (`WARN` / `BLOCK` / `APPROVAL_REQUIRED`) use canonical `sec_findings` — no secrets in gate output.

## Additional API endpoints

`GET/POST /providers`, `POST /providers/{id}/validate`, `GET /scan-runs`, `POST /scans/{id}/execute`, `POST /sbom/import`, `GET /sbom/components`, `GET /sla`, `POST /sla/evaluate`, `GET/POST /remediation/{id}/execution|execute`

## Additional events

`SecurityProviderValidated`, `SecurityScanStarted`, `SecurityScanCompleted`, `SecurityBackfillCompleted`, `SecuritySBOMImported`, `SecurityRemediationExecutionStarted`, `SecurityRemediationExecutionCompleted`, `SecuritySLABreached`, `SecurityGateBlocked`

## Additional metrics

`nexora_security_provider_health`, `nexora_security_scans_live_total`, `nexora_security_scans_offline_total`, `nexora_security_backfill_total`, `nexora_security_remediation_execution_total`, `nexora_security_sla_due_total`, `nexora_security_gate_blocks_total`
