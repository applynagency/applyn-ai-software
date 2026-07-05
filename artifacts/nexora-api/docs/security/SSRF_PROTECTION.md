# SSRF Protection

Enterprise-grade Server-Side Request Forgery (SSRF) protection for all outbound
HTTP that Nexora makes on behalf of a tenant.

> **Why:** Integration verification, monitoring ingestion, and discovery all
> fetch **customer-supplied URLs** (`base_url`, `endpoint`, OAuth token hosts).
> Without guards an authenticated tenant could coerce the server into requesting
> internal services or cloud metadata (e.g. `http://169.254.169.254/...`). This
> closes that class of attack at a single shared chokepoint.

---

## 1. Module: `app/security/ssrf.py`

A dependency-light guard (`ipaddress` + `socket`; `httpx` only for the client).

| Function | Purpose |
|---|---|
| `validate_ip(ip, *, policy=None)` | Validate one IP (str or `ipaddress` object). Raises `SSRFError` if blocked; returns the parsed address. |
| `validate_hostname(hostname, *, policy=None)` | Validate a hostname or IP literal. Resolves DNS and checks **every** resolved address. Returns the list of validated IPs. |
| `validate_url(url, *, policy=None)` | Full URL validation: scheme → port → host → DNS → IPs. Returns a `ValidatedURL(url, scheme, hostname, port, ip_addresses)`. |
| `safe_http_client(*, policy=None, allow_redirects=False, timeout=None, verify=True, transport=None, **kwargs)` | An `httpx.AsyncClient` that SSRF-validates the initial request **and every redirect hop**. |

Supporting types: `SSRFError`, `SSRFPolicy`, `ValidatedURL`, `default_policy()`.

### What is blocked

**Addresses (always blocked, even with `allow_private=True`):**
- Loopback — `127.0.0.0/8`, `::1`
- Link-local — `169.254.0.0/16`, `fe80::/10`
- Cloud metadata — `169.254.169.254` (AWS/Azure/GCP IMDS) and `fd00:ec2::254` (AWS IPv6)
- Multicast, reserved, unspecified (`0.0.0.0`), IPv6 unique-local (`fc00::/7`)
- IPv4-mapped IPv6 forms of the above (e.g. `::ffff:127.0.0.1`)

**Private ranges (blocked unless `SSRF_ALLOW_PRIVATE_NETWORKS=true`):**
- `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`

**Hostnames (always blocked):** `localhost`, `*.localhost`, `metadata`,
`metadata.google.internal`, `metadata.goog`.

**Schemes:** only `http`/`https` (blocks `file://`, `gopher://`, `ftp://`, …).

**Ports:** must be `1–65535`; a sensitive-service denylist is rejected
(`22, 23, 25, 135, 445, 1433, 3306, 3389, 5432, 5984, 6379, 9200, 11211, 27017`).
An optional strict allow-list (`SSRFPolicy.allowed_ports`) can be supplied.

**Redirects:** disabled by default. When a caller opts in
(`allow_redirects=True`), each hop is re-validated by the transport, so an
allowed first host cannot bounce to an internal target.

### DNS-rebinding

`validate_hostname` resolves the name and rejects the request if **any** A/AAAA
address is blocked. This defeats the simple "public name → private A record"
trick. There is a small theoretical TOCTOU window between validation and the
socket connect (full mitigation = connect-time IP pinning); this is documented
as residual and is a candidate for a future hardening pass. In the multi-tenant
SaaS default (`allow_private=false`) the practical exposure is minimal because
all private/loopback/metadata space is blocked outright.

---

## 2. Usage

```python
from app.security.ssrf import safe_http_client, SSRFError

try:
    async with safe_http_client(timeout=..., verify=True) as c:   # redirects OFF
        resp = await c.get(user_supplied_url)
except SSRFError:
    ...  # blocked target — map to your subsystem's safe error
```

Validate without making a request:

```python
from app.security.ssrf import validate_url, SSRFError
try:
    info = validate_url("https://api.example.com/v1")
except SSRFError:
    ...
```

---

## 3. Configuration (`app/core/config.py`)

| Setting | Default | Meaning |
|---|---|---|
| `SSRF_PROTECTION_ENABLED` | `True` | Master switch. When `False`, the guard passes everything through (use only for debugging). |
| `SSRF_ALLOW_PRIVATE_NETWORKS` | `False` | On-prem/self-hosted: permit RFC-1918 targets. Loopback/link-local/metadata remain blocked. |

Both are read by `default_policy()`; no migration or env change is required for
default secure behavior.

---

## 4. Files changed

| File | Change |
|---|---|
| `app/security/ssrf.py` | **New.** The guard + `safe_http_client`. |
| `app/core/config.py` | Added `SSRF_PROTECTION_ENABLED`, `SSRF_ALLOW_PRIVATE_NETWORKS`. |
| `app/services/integration_verification.py` | `_http_request` and `_aad_token` now use `safe_http_client`; `SSRFError` → `_Failed`. |
| `app/services/monitoring_ingestion.py` | All 5 pollers (Azure Monitor, Prometheus, AlertManager, GitHub Actions, GitLab Pipelines) use `safe_http_client`; `_with_retry` maps `SSRFError` → `IngestError` (not retried). |
| `app/services/discovery_adapters.py` | Azure `_aad_token` and `_arm_list` use `safe_http_client`; `SSRFError` → `AdapterError`. |
| `app/tests/test_ssrf.py` | **New.** 40+ unit tests (IP/hostname/URL/policy/transport). |
| `app/tests/test_ssrf_integration.py` | **New.** Integration tests proving every outbound path is guarded. |
| `docs/security/SSRF_PROTECTION.md` | **New.** This document. |

`universal_discovery_adapters.py` is automatically covered: it reuses
`integration_verification._http_request`, so no change was needed there.

---

## 5. Migration notes

- **No database migration.** This change is code-only (no schema/models).
- **No API contract change.** Verification/ingestion/discovery response shapes
  are unchanged; a blocked URL surfaces as the same customer-safe failure those
  subsystems already return (`FAILED` / `IngestError` / `AdapterError`), so
  clients need no updates. **Backward compatible.**
- **Default-secure.** Protection is on by default. No config is required.
- **Self-hosted / on-prem deployments** that legitimately target private
  networks (internal GitLab, in-cluster Prometheus on `10.x`) must set
  `SSRF_ALLOW_PRIVATE_NETWORKS=true`. Loopback/link-local/metadata stay blocked.
- **Non-standard ports keep working** (e.g. self-hosted Prometheus `:9090`,
  GitLab `:8443`) — ports are validated, not restricted to 80/443.
- **Out of scope (by design):** the AWS (`boto3`) and Kubernetes SDK clients are
  not routed through this guard. They target provider-owned or
  customer-cluster API servers (often legitimately private), and the SDKs manage
  their own transport. SSRF risk there is bounded by the credential itself.

---

## 6. Tests

Run in the project Python 3.11 image:

```bash
docker run --rm \
  -e DEBUG=false \
  -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  -e MASTER_ENCRYPTION_KEY="<test-key>" \
  -v "$PWD":/app -w /app nexora-api-api:latest \
  python -m pytest app/tests/test_ssrf.py app/tests/test_ssrf_integration.py -q
```

**Unit (`test_ssrf.py`)** — IP blocking (loopback/private/link-local/metadata/
multicast/unspecified/mapped-IPv6), public allow, on-prem policy, disabled
policy, hostname blocking + DNS-rebinding rejection, URL scheme/port/host
validation, default-port derivation, high-port backward-compat, and
`safe_http_client` behavior (blocks before egress, allows public via mock
transport, redirects off by default, redirect-hop validation when enabled).

**Integration (`test_ssrf_integration.py`)** — proves the guard is wired into
each subsystem: `integration_verification._http_request`/`_aad_token`,
`monitoring_ingestion.poll_prometheus`/`poll_alertmanager`, and
`discovery_adapters._aad_token` all reject internal/metadata/bad-scheme targets
with their own safe exception, and allowed public hosts still flow through.

**Result:** 62 SSRF tests pass; 75 regression tests across integration
verification, monitoring, and discovery pass unchanged (no regressions).
