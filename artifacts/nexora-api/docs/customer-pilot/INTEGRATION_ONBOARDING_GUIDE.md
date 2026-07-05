# Integration Onboarding Guide

This guide walks customer admins through connecting integrations for a **scoped non-production pilot**. Onboarding performs **read-only validation only** — no deployments, scales, restarts, or repository changes.

## Overview

1. Create an onboarding session per provider (Kubernetes, source control, Prometheus)
2. Declare a **non-production** environment and scope
3. Store credentials (encrypted; never shown again)
4. Run validation
5. Review RBAC guidance and evidence
6. Acknowledge readiness

## Supported providers

| Provider | Scope required |
|----------|----------------|
| Kubernetes | One namespace (not cluster-wide) |
| GitHub / GitHub Enterprise / Gitea | One repository (`owner/name`) |
| Prometheus | Endpoint + optional namespace label for evidence queries |

## What is validated

### Kubernetes (read-only)

- Deployments: get, list, watch
- Pods: get, list, watch
- Events: get, list, watch
- Optional future scale: deployments/scale get, patch, update (guidance only)

**Explicitly checked absent:** secrets read, exec, port-forward, nodes, delete, cluster-admin

### Source control

- Identity and repository read access
- Branches/commits metadata when permitted
- Workflow history: if unavailable, marked **INSUFFICIENT_EVIDENCE** (not a hard failure when repo read works)

### Prometheus

- Build info and targets (read-only)
- Safe PromQL queries for pilot evidence
- No scrape config, alert rule, or remote-write changes

## After validation

- A **CONNECTED + live** registry entry is created only when validation succeeds
- Run **Pilot Readiness** to see `GO`, `NO_GO`, or `INSUFFICIENT_EVIDENCE`
- Complete acknowledgement to reach `READY_FOR_PILOT` per session

## What does not happen during onboarding

- No pilot enrollment or stage advancement
- No live operations or approvals
- No infrastructure or cloud mutation
- No webhook or pipeline creation

See also: [CUSTOMER_PREREQUISITES.md](./CUSTOMER_PREREQUISITES.md), [KUBERNETES_RBAC_TEMPLATES.md](./KUBERNETES_RBAC_TEMPLATES.md)
