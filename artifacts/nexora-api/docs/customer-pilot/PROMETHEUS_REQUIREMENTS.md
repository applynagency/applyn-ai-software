# Prometheus Requirements

## Scope

Read-only access to a Prometheus-compatible metrics endpoint. No configuration changes.

## Required endpoint access

| Path | Purpose |
|------|---------|
| `/api/v1/status/buildinfo` | Confirm endpoint identity |
| `/api/v1/targets` | Target health summary |
| `/api/v1/query` | Safe read-only PromQL (replica/availability) |

## Namespace evidence

Declare a label key/value (commonly `namespace=<pilot-namespace>`) used for pilot evidence queries. Wildcard label values are rejected.

## Authentication

- Bearer token or basic auth via credential reference if required
- Credentials stored encrypted; never returned in API responses

## Not requested

- Scrape configuration changes
- Alert or recording rule edits
- Remote write
- Target mutation
- Admin API access

## Missing metrics

If expected series are unavailable, validation may report guidance and **INSUFFICIENT_EVIDENCE** for optional telemetry without claiming full observability coverage.
