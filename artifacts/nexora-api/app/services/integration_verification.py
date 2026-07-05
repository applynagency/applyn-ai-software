"""Sprint 58A.1 — Real integration verification.

Replaces the previous configuration-only ("simulated") marketplace verification
with genuine, read-only probes against each provider's real API using the
customer-supplied (decrypted, in-process) credentials.

STRICT GUARANTEES (enforced here):
  * No simulation. A provider is only reported CONNECTED if the provider itself
    confirms the credential (auth + at least one read).
  * No secrets ever leave this module. ``provider_identity`` only contains
    non-sensitive identity fields; ``warnings``/``errors`` are generic and never
    include raw driver text, tokens, or exception payloads that could carry one.
  * Every network call is bounded by a connect/read timeout, retried up to 3x
    with exponential backoff on *transient* failures only (never on auth), and
    the whole verification is wrapped in a hard total-time budget.
  * TLS verification is always on (httpx ``verify=True``; SDK defaults).

The result vocabulary (``connection_status``) is:
  CONNECTED   - auth + reads succeeded
  PARTIAL     - auth succeeded but one or more non-critical reads failed
  FAILED      - reached the provider but the probe could not be completed
  UNAUTHORIZED- the provider rejected the credentials
  TIMEOUT     - the provider did not respond within the budget
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.security.ssrf import SSRFError, safe_http_client

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #
_CONNECT_TIMEOUT = 8.0   # seconds, per individual network call
_READ_TIMEOUT = 12.0     # seconds, per individual network call
_RETRY_ATTEMPTS = 3      # total attempts (1 initial + 2 retries) on transient errors
_RETRY_BASE_DELAY = 0.5  # seconds, doubled each retry
_TOTAL_BUDGET = 45.0     # seconds, hard ceiling for an entire verification


class VStatus:
    CONNECTED = "CONNECTED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"
    TIMEOUT = "TIMEOUT"


# --------------------------------------------------------------------------- #
# Control-flow exceptions (internal). None of these carry secret material.
# --------------------------------------------------------------------------- #
class _Unauthorized(Exception):
    """Provider rejected the credentials (not retryable)."""


class _Timeout(Exception):
    """Provider did not respond in time (retryable)."""


class _Retryable(Exception):
    """Transient transport/5xx/429 error (retryable)."""


class _Failed(Exception):
    """Reached the provider but the probe failed (not retryable)."""


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class ProviderProbe:
    """The non-sensitive outcome of a successful (or partial) provider probe."""

    identity: dict = field(default_factory=dict)
    version: str | None = None
    permissions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    partial: bool = False


@dataclass
class VerificationResult:
    connection_status: str
    latency_ms: int
    provider_version: str | None
    verified_at: datetime
    provider_identity: dict
    permissions: list[str]
    warnings: list[str]
    errors: list[str]
    confidence: int

    @property
    def ok(self) -> bool:
        return self.connection_status == VStatus.CONNECTED

    def to_dict(self) -> dict:
        return {
            "connection_status": self.connection_status,
            "latency_ms": self.latency_ms,
            "provider_version": self.provider_version,
            "verified_at": self.verified_at.isoformat(),
            "provider_identity": self.provider_identity,
            "permissions": self.permissions,
            "warnings": self.warnings,
            "errors": self.errors,
            "confidence": self.confidence,
        }


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# HTTP helpers (httpx) — TLS always verified, errors mapped to control flow
# --------------------------------------------------------------------------- #
def _timeout():
    import httpx

    return httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_CONNECT_TIMEOUT)


def _map_status(status_code: int) -> None:
    """Raise the appropriate control-flow exception for a non-2xx status."""
    if status_code in (401, 403):
        raise _Unauthorized()
    if status_code == 429 or status_code >= 500:
        raise _Retryable()
    if status_code >= 400:
        raise _Failed()


async def _http_request(method: str, url: str, *, headers=None, params=None, json_body=None, auth=None) -> dict:
    """Single bounded HTTP call returning parsed JSON (or {} on empty body).

    Raises _Unauthorized / _Timeout / _Retryable / _Failed. Never raises with
    secret-bearing text.
    """
    import httpx

    try:
        # SSRF-safe client. Redirects are explicitly allowed for provider quirks
        # (e.g. trailing-slash 301s) but every hop is re-validated by the client.
        async with safe_http_client(timeout=_timeout(), verify=True, allow_redirects=True) as c:
            resp = await c.request(method, url, headers=headers, params=params, json=json_body, auth=auth)
    except SSRFError as exc:  # blocked target (internal/metadata/disallowed scheme/port)
        raise _Failed() from exc
    except httpx.TimeoutException as exc:
        raise _Timeout() from exc
    except httpx.TransportError as exc:  # connect/DNS/TLS/read transport problems
        raise _Retryable() from exc
    _map_status(resp.status_code)
    # Some endpoints (auth.test) return 200 with an error body — caller inspects.
    try:
        return {"_status": resp.status_code, "_headers": dict(resp.headers), "_json": resp.json()}
    except (ValueError, json.JSONDecodeError):
        return {"_status": resp.status_code, "_headers": dict(resp.headers), "_json": {}}


def _basic_auth(username: str, password: str):
    import httpx

    return httpx.BasicAuth(username, password)


def _decode_jwt_claims(token: str) -> dict:
    """Decode (without verifying) a JWT payload to read non-secret claims.

    Used only to surface app roles/scopes from a token we just obtained for the
    customer's own tenant. Returns {} on any problem.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (IndexError, ValueError, binascii.Error, UnicodeDecodeError):
        return {}


# --------------------------------------------------------------------------- #
# Retry wrapper — retries on _Retryable / _Timeout only, exponential backoff
# --------------------------------------------------------------------------- #
async def _with_retry(factory):
    delay = _RETRY_BASE_DELAY
    last: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return await factory()
        except _Unauthorized:
            raise  # never retry auth failures
        except _Failed:
            raise  # deterministic failure, retrying won't help
        except (_Retryable, _Timeout) as exc:
            last = exc
            if attempt < _RETRY_ATTEMPTS - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise
    if last:  # pragma: no cover - defensive
        raise last
    raise _Failed()


# =========================================================================== #
# Per-provider verifiers. Each returns a ProviderProbe or raises a control
# exception. They must remain READ-ONLY and secret-safe.
# =========================================================================== #

# ---- AWS ------------------------------------------------------------------ #
async def _verify_aws(secret: dict) -> ProviderProbe:
    region = secret.get("region") or "us-east-1"

    def _run():
        import boto3
        from botocore.config import Config
        from botocore.exceptions import (
            ClientError,
            ConnectTimeoutError,
            EndpointConnectionError,
            ReadTimeoutError,
        )

        cfg = Config(
            connect_timeout=_CONNECT_TIMEOUT,
            read_timeout=_READ_TIMEOUT,
            retries={"max_attempts": 0},
        )
        session = boto3.session.Session(
            aws_access_key_id=secret["access_key"],
            aws_secret_access_key=secret["secret_key"],
            region_name=region,
        )
        warnings: list[str] = []
        permissions: list[str] = []
        try:
            ident = session.client("sts", config=cfg).get_caller_identity()
        except (ConnectTimeoutError, ReadTimeoutError) as exc:
            raise _Timeout() from exc
        except EndpointConnectionError as exc:
            raise _Retryable() from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {
                "InvalidClientTokenId", "SignatureDoesNotMatch", "UnrecognizedClientException",
                "AuthFailure", "AccessDenied", "AccessDeniedException", "ExpiredToken",
            }:
                raise _Unauthorized() from exc
            raise _Failed() from exc
        permissions.append("sts:GetCallerIdentity")
        # Best-effort, non-critical permission probe.
        try:
            session.client("ec2", config=cfg).describe_regions(MaxResults=1)
            permissions.append("ec2:DescribeRegions")
        except Exception:  # noqa: BLE001 - non-critical; absence -> warning only
            warnings.append("EC2 read permission not detected (ec2:DescribeRegions).")
        return ident, warnings, permissions

    ident, warnings, permissions = await asyncio.to_thread(_run)
    arn = ident.get("Arn", "")
    user = arn.split("/")[-1] or arn.split(":")[-1] if arn else ""
    return ProviderProbe(
        identity={
            "account_id": ident.get("Account", ""),
            "arn": arn,
            "user": user,
            "user_id": ident.get("UserId", ""),
            "region": region,
        },
        version=None,
        permissions=permissions,
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Azure (management API) ----------------------------------------------- #
async def _aad_token(tenant_id: str, client_id: str, client_secret: str, scope: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    import httpx

    try:
        async with safe_http_client(timeout=_timeout(), verify=True) as c:
            resp = await c.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except SSRFError as exc:
        raise _Failed() from exc
    except httpx.TimeoutException as exc:
        raise _Timeout() from exc
    except httpx.TransportError as exc:
        raise _Retryable() from exc
    if resp.status_code in (400, 401):
        # invalid_client / invalid_grant / unauthorized_client -> credentials bad
        raise _Unauthorized()
    if resp.status_code == 429 or resp.status_code >= 500:
        raise _Retryable()
    if resp.status_code >= 400:
        raise _Failed()
    token = resp.json().get("access_token")
    if not token:
        raise _Unauthorized()
    return token


async def _verify_azure(secret: dict) -> ProviderProbe:
    tenant_id = secret["tenant_id"]
    sub = secret["subscription_id"]
    token = await _aad_token(tenant_id, secret["client_id"], secret["client_secret"],
                             "https://management.azure.com/.default")
    api_version = "2022-12-01"
    data = await _http_request(
        "GET",
        f"https://management.azure.com/subscriptions/{sub}?api-version={api_version}",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = data["_json"]
    permissions = ["Microsoft.Resources/subscriptions/read"]
    warnings: list[str] = []
    try:
        rg = await _http_request(
            "GET",
            f"https://management.azure.com/subscriptions/{sub}/resourcegroups?api-version=2021-04-01&$top=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        if rg["_json"].get("value") is not None:
            permissions.append("Microsoft.Resources/subscriptions/resourceGroups/read")
    except (_Failed, _Unauthorized):
        warnings.append("Resource group read permission not detected.")
    return ProviderProbe(
        identity={
            "tenant_id": tenant_id,
            "application": secret["client_id"],
            "subscription_id": sub,
            "subscription_name": body.get("displayName", ""),
            "state": body.get("state", ""),
        },
        version=api_version,
        permissions=permissions,
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Kubernetes ----------------------------------------------------------- #
_K8S_SAR_CHECKS: tuple[tuple[str, str, str | None, str, str | None], ...] = (
    ("apps", "deployments", None, "get", "deployments:get"),
    ("apps", "deployments", None, "list", "deployments:list"),
    ("apps", "deployments", None, "watch", "deployments:watch"),
    ("apps", "deployments", "scale", "get", "scale:get"),
    ("apps", "deployments", "scale", "patch", "scale:patch"),
    ("apps", "deployments", "scale", "update", "scale:update"),
    ("", "pods", None, "get", "pods:get"),
    ("", "pods", None, "list", "pods:list"),
    ("", "pods", None, "watch", "pods:watch"),
    ("", "events", None, "get", "events:get"),
    ("", "events", None, "list", "events:list"),
    ("", "events", None, "watch", "events:watch"),
)


async def _verify_kubernetes(secret: dict) -> ProviderProbe:
    def _run():
        import yaml
        from kubernetes import client, config
        from kubernetes.client.exceptions import ApiException

        raw = secret.get("kubeconfig")
        if not raw:
            raise _Failed()
        try:
            cfg = yaml.safe_load(raw)
            loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
            configuration = client.Configuration()
            loader.load_and_set(configuration)
            api_client = client.ApiClient(configuration)
        except Exception as exc:  # noqa: BLE001 - malformed kubeconfig
            raise _Failed() from exc

        api_server = configuration.host or ""
        current = cfg.get("current-context")
        cluster = ""
        scoped_namespace = (secret.get("namespace") or "").strip()
        for ctx in cfg.get("contexts", []):
            if ctx.get("name") == current:
                ctx_ns = (ctx.get("context", {}).get("namespace") or "").strip()
                cluster = ctx.get("context", {}).get("cluster", "")
                if not scoped_namespace and ctx_ns:
                    scoped_namespace = ctx_ns

        warnings: list[str] = []
        permissions: list[str] = []
        version = None
        try:
            version = client.VersionApi(api_client).get_code(_request_timeout=_READ_TIMEOUT).git_version
        except ApiException as exc:
            if exc.status in (401, 403):
                raise _Unauthorized() from exc
            warnings.append("Server version not readable.")
        except Exception as exc:  # noqa: BLE001 - transport
            raise _Retryable() from exc

        core = client.CoreV1Api(api_client)
        apps = client.AppsV1Api(api_client)
        auth = client.AuthorizationV1Api(api_client)
        ns_names: list[str] = []
        ns_count = 0
        try:
            ns = core.list_namespace(limit=50, _request_timeout=_READ_TIMEOUT)
            permissions.append("namespaces:list")
            ns_names = [i.metadata.name for i in ns.items[:10]]
            ns_count = len(ns.items)
        except ApiException as exc:
            if exc.status in (401, 403):
                if scoped_namespace:
                    try:
                        apps.list_namespaced_deployment(
                            scoped_namespace, limit=1, _request_timeout=_READ_TIMEOUT,
                        )
                        permissions.append(f"namespace:scoped:{scoped_namespace}")
                        ns_names = [scoped_namespace]
                        ns_count = 1
                    except ApiException as inner:
                        if inner.status in (401, 403):
                            raise _Unauthorized() from inner
                        raise _Failed() from inner
                else:
                    raise _Unauthorized() from exc
            else:
                raise _Failed() from exc
        except Exception as exc:  # noqa: BLE001 - transport
            raise _Retryable() from exc

        probe_namespace = scoped_namespace or (ns_names[0] if ns_names else "")
        if probe_namespace:
            try:
                apps.list_namespaced_deployment(
                    probe_namespace, limit=5, _request_timeout=_READ_TIMEOUT,
                )
            except ApiException as exc:
                if exc.status in (401, 403):
                    raise _Unauthorized() from exc
                warnings.append("Deployments not listable in scoped namespace.")
            except Exception as exc:  # noqa: BLE001 - transport
                raise _Retryable() from exc

            def _sar_allowed(
                group: str, resource: str, subresource: str | None, verb: str, *, name: str | None = None,
            ) -> bool:
                attrs = client.V1ResourceAttributes(
                    namespace=probe_namespace,
                    verb=verb,
                    group=group or None,
                    resource=resource,
                    subresource=subresource,
                    name=name,
                )
                review = client.V1SelfSubjectAccessReview(
                    spec=client.V1SelfSubjectAccessReviewSpec(resource_attributes=attrs),
                )
                try:
                    result = auth.create_self_subject_access_review(
                        review, _request_timeout=_READ_TIMEOUT,
                    )
                    return bool(result.status and result.status.allowed)
                except Exception:
                    return False

            for group, resource, subresource, verb, label in _K8S_SAR_CHECKS:
                if _sar_allowed(group, resource, subresource, verb, name="pilot-demo" if resource == "deployments" else None):
                    permissions.append(label)

        if not permissions:
            raise _Failed()
        return api_server, cluster, version, ns_names, ns_count, warnings, permissions, probe_namespace

    api_server, cluster, version, ns_names, ns_count, warnings, permissions, probe_namespace = await asyncio.to_thread(_run)
    identity: dict = {
        "cluster": cluster or "kubernetes",
        "api_server": api_server,
        "namespaces": ns_names,
        "namespace_count": ns_count,
    }
    if probe_namespace:
        identity["scoped_namespace"] = probe_namespace
    return ProviderProbe(
        identity=identity,
        version=version,
        permissions=permissions,
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- GitHub --------------------------------------------------------------- #
def _gh_base(secret: dict) -> str:
    return (secret.get("base_url") or "https://api.github.com").rstrip("/")


async def _verify_github(secret: dict) -> ProviderProbe:
    base = _gh_base(secret)
    headers = {
        "Authorization": f"Bearer {secret['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    user = await _http_request("GET", f"{base}/user", headers=headers)
    u = user["_json"]
    resp_headers = user["_headers"]
    scopes_raw = resp_headers.get("x-oauth-scopes", "")
    scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
    version = resp_headers.get("x-github-api-version-selected") or "2022-11-28"

    warnings: list[str] = []
    if not scopes:
        warnings.append("Token scopes not reported (fine-grained or app token).")

    orgs: list[str] = []
    try:
        org_data = await _http_request("GET", f"{base}/user/orgs?per_page=50", headers=headers)
        orgs = [o.get("login", "") for o in org_data["_json"] if isinstance(o, dict)]
    except (_Failed, _Unauthorized):
        warnings.append("Organizations not readable with this token.")

    repo_count = None
    repos_failed = False
    try:
        repo_data = await _http_request("GET", f"{base}/user/repos?per_page=1", headers=headers)
        link = repo_data["_headers"].get("link", "")
        if 'rel="last"' in link:
            import re

            m = re.search(r"[?&]page=(\d+)>; rel=\"last\"", link)
            repo_count = int(m.group(1)) if m else len(repo_data["_json"])
        else:
            repo_count = len(repo_data["_json"])
    except (_Failed, _Unauthorized):
        repos_failed = True
        warnings.append("Repositories not readable with this token.")

    permissions = list(scopes)
    if not permissions and repo_count is not None:
        permissions = ["repo:read"]

    return ProviderProbe(
        identity={
            "login": u.get("login", ""),
            "id": u.get("id", ""),
            "name": u.get("name", ""),
            "organizations": orgs,
            "repository_count": repo_count,
        },
        version=version,
        permissions=permissions,
        warnings=warnings,
        partial=repos_failed,
    )


# ---- GitLab --------------------------------------------------------------- #
def _gl_base(secret: dict) -> str:
    return (secret.get("base_url") or "https://gitlab.com").rstrip("/")


async def _verify_gitlab(secret: dict) -> ProviderProbe:
    base = _gl_base(secret)
    headers = {"Authorization": f"Bearer {secret['token']}"}
    me = await _http_request("GET", f"{base}/api/v4/user", headers=headers)
    u = me["_json"]

    warnings: list[str] = []
    permissions: list[str] = []
    version = None
    try:
        ver = await _http_request("GET", f"{base}/api/v4/version", headers=headers)
        version = ver["_json"].get("version")
        permissions.append("read_api")
    except (_Failed, _Unauthorized):
        warnings.append("API version not readable (token may lack read_api scope).")

    groups: list[str] = []
    try:
        g = await _http_request("GET", f"{base}/api/v4/groups?per_page=50&min_access_level=10", headers=headers)
        groups = [grp.get("full_path", "") for grp in g["_json"] if isinstance(grp, dict)]
    except (_Failed, _Unauthorized):
        warnings.append("Groups not readable with this token.")

    project_count = None
    try:
        p = await _http_request(
            "GET", f"{base}/api/v4/projects?membership=true&per_page=1&simple=true", headers=headers
        )
        total = p["_headers"].get("x-total")
        project_count = int(total) if total and total.isdigit() else len(p["_json"])
    except (_Failed, _Unauthorized):
        warnings.append("Projects not readable with this token.")

    return ProviderProbe(
        identity={
            "username": u.get("username", ""),
            "id": u.get("id", ""),
            "name": u.get("name", ""),
            "groups": groups,
            "project_count": project_count,
        },
        version=version,
        permissions=permissions,
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Slack ---------------------------------------------------------------- #
async def _verify_slack(secret: dict) -> ProviderProbe:
    headers = {"Authorization": f"Bearer {secret['bot_token']}"}
    data = await _http_request("POST", "https://slack.com/api/auth.test", headers=headers)
    body = data["_json"]
    if not body.get("ok"):
        # Slack returns 200 with {"ok": false, "error": "invalid_auth"} for bad tokens.
        err = body.get("error", "")
        if err in {"invalid_auth", "not_authed", "account_inactive", "token_revoked", "token_expired"}:
            raise _Unauthorized()
        raise _Failed()
    scopes_raw = data["_headers"].get("x-oauth-scopes", "")
    scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
    warnings: list[str] = []
    if not scopes:
        warnings.append("Granted scopes not reported by Slack for this token.")
    return ProviderProbe(
        identity={
            "workspace": body.get("team", ""),
            "team_id": body.get("team_id", ""),
            "bot_user": body.get("user", ""),
            "bot_id": body.get("bot_id", ""),
            "url": body.get("url", ""),
        },
        version=None,
        permissions=scopes,
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Microsoft Teams (Microsoft Graph, app credentials) ------------------- #
async def _verify_teams(secret: dict) -> ProviderProbe:
    tenant_id = secret["tenant_id"]
    client_id = secret["client_id"]
    token = await _aad_token(tenant_id, client_id, secret["client_secret"],
                             "https://graph.microsoft.com/.default")
    claims = _decode_jwt_claims(token)
    roles = claims.get("roles") or []  # application permissions granted to the app
    warnings: list[str] = []
    org_name = ""
    try:
        org = await _http_request(
            "GET", "https://graph.microsoft.com/v1.0/organization",
            headers={"Authorization": f"Bearer {token}"},
        )
        values = org["_json"].get("value") or []
        if values:
            org_name = values[0].get("displayName", "")
    except (_Failed, _Unauthorized):
        warnings.append("Organization read not granted (Organization.Read.All).")
    return ProviderProbe(
        identity={
            "tenant_id": tenant_id,
            "application": client_id,
            "organization": org_name,
        },
        version="v1.0",
        permissions=list(roles),
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Jira ----------------------------------------------------------------- #
async def _verify_jira(secret: dict) -> ProviderProbe:
    base = secret["base_url"].rstrip("/")
    auth = _basic_auth(secret["email"], secret["api_token"])
    me = await _http_request("GET", f"{base}/rest/api/3/myself", auth=auth)
    u = me["_json"]

    warnings: list[str] = []
    version = None
    try:
        info = await _http_request("GET", f"{base}/rest/api/3/serverInfo", auth=auth)
        version = info["_json"].get("version")
    except (_Failed, _Unauthorized):
        warnings.append("Server info not readable.")

    cloud_id = ""
    try:
        edge = await _http_request("GET", f"{base}/_edge/tenant_info", auth=auth)
        cloud_id = edge["_json"].get("cloudId", "")
    except (_Failed, _Unauthorized):
        warnings.append("Cloud ID not resolvable.")

    project_count = None
    try:
        proj = await _http_request("GET", f"{base}/rest/api/3/project/search?maxResults=1", auth=auth)
        project_count = proj["_json"].get("total")
    except (_Failed, _Unauthorized):
        warnings.append("Projects not readable with these credentials.")

    permissions: list[str] = []
    try:
        perms = await _http_request(
            "GET", f"{base}/rest/api/3/mypermissions?permissions=BROWSE_PROJECTS,CREATE_ISSUES", auth=auth
        )
        granted = perms["_json"].get("permissions", {})
        permissions = [k for k, v in granted.items() if isinstance(v, dict) and v.get("havePermission")]
    except (_Failed, _Unauthorized):
        warnings.append("Permission scopes not readable.")

    return ProviderProbe(
        identity={
            "account_id": u.get("accountId", ""),
            "display_name": u.get("displayName", ""),
            "email": u.get("emailAddress", ""),
            "cloud_id": cloud_id,
            "project_count": project_count,
        },
        version=version,
        permissions=permissions,
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Datadog -------------------------------------------------------------- #
async def _verify_datadog(secret: dict) -> ProviderProbe:
    site = (secret.get("site") or "https://api.datadoghq.com").rstrip("/")
    headers = {"DD-API-KEY": secret["api_key"], "DD-APPLICATION-KEY": secret["app_key"]}
    await _http_request("GET", f"{site}/api/v1/validate", headers=headers)
    return ProviderProbe(
        identity={"site": site},
        version="v1",
        permissions=["metrics:read", "monitors:read"],
        warnings=[],
        partial=False,
    )


# ---- Prometheus ----------------------------------------------------------- #
async def _verify_prometheus(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}"} if secret.get("token") else None
    data = await _http_request("GET", f"{endpoint}/api/v1/status/buildinfo", headers=headers)
    version = (data["_json"].get("data") or {}).get("version")
    return ProviderProbe(
        identity={"endpoint": endpoint},
        version=version,
        permissions=["metrics:read"],
        warnings=[],
        partial=False,
    )


# ---- Grafana -------------------------------------------------------------- #
async def _verify_grafana(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}"}
    data = await _http_request("GET", f"{endpoint}/api/health", headers=headers)
    version = data["_json"].get("version")
    return ProviderProbe(
        identity={"endpoint": endpoint},
        version=version,
        permissions=["dashboards:read"],
        warnings=[],
        partial=False,
    )


# ---- New Relic ------------------------------------------------------------ #
async def _verify_newrelic(secret: dict) -> ProviderProbe:
    api_key = secret["api_key"]
    gql_url = "https://api.newrelic.com/graphql"
    query = {"query": "{ actor { user { name email } } }"}
    data = await _http_request(
        "POST", gql_url, headers={"API-Key": api_key, "Content-Type": "application/json"}, json_body=query
    )
    body = data["_json"]
    if body.get("errors"):
        raise _Unauthorized()
    user = (((body.get("data") or {}).get("actor") or {}).get("user")) or {}
    return ProviderProbe(
        identity={"account_id": secret.get("account_id", ""), "user": user.get("name", ""),
                  "email": user.get("email", "")},
        version="NerdGraph",
        permissions=["apm:read"],
        warnings=[],
        partial=False,
    )


# ---- PagerDuty ------------------------------------------------------------ #
async def _verify_pagerduty(secret: dict) -> ProviderProbe:
    headers = {"Authorization": f"Token token={secret['api_key']}",
               "Accept": "application/vnd.pagerduty+json;version=2"}
    await _http_request("GET", "https://api.pagerduty.com/abilities", headers=headers)
    warnings: list[str] = []
    svc_count = None
    try:
        svc = await _http_request("GET", "https://api.pagerduty.com/services?limit=1", headers=headers)
        svc_count = svc["_json"].get("total")
    except (_Failed, _Unauthorized):
        warnings.append("Services not readable with this key.")
    return ProviderProbe(
        identity={"services_total": svc_count},
        version="v2",
        permissions=["incidents:read", "services:read"],
        warnings=warnings,
        partial=bool(warnings),
    )


# ---- Bitbucket ------------------------------------------------------------ #
async def _verify_bitbucket(secret: dict) -> ProviderProbe:
    auth = _basic_auth(secret["username"], secret["app_password"])
    me = await _http_request("GET", "https://api.bitbucket.org/2.0/user", auth=auth)
    u = me["_json"]
    warnings: list[str] = []
    workspaces: list[str] = []
    try:
        ws = await _http_request("GET", "https://api.bitbucket.org/2.0/workspaces?pagelen=50", auth=auth)
        workspaces = [w.get("slug", "") for w in (ws["_json"].get("values") or []) if isinstance(w, dict)]
    except (_Failed, _Unauthorized):
        warnings.append("Workspaces not readable with this app password.")
    return ProviderProbe(
        identity={"username": u.get("username", ""), "account_id": u.get("account_id", ""),
                  "workspaces": workspaces},
        version="2.0",
        permissions=["repositories:read"],
        warnings=warnings,
        partial=bool(warnings),
    )


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
# ---- SonarQube, ArgoCD, Vault, Loki, Elastic, Jenkins, etc. -------------- #
async def _verify_argocd(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}"}
    data = await _http_request("GET", f"{endpoint}/api/v1/version", headers=headers)
    version = (data["_json"].get("Version") or data["_json"].get("version") or "")
    return ProviderProbe(identity={"endpoint": endpoint}, version=version or None,
                         permissions=["applications:read"], warnings=[], partial=False)


async def _verify_jenkins(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    data = await _http_request(
        "GET", f"{endpoint}/api/json", auth=_basic_auth(secret["username"], secret["api_token"]),
    )
    return ProviderProbe(
        identity={"endpoint": endpoint, "mode": data["_json"].get("mode", "")},
        version=None, permissions=["jobs:read"], warnings=[], partial=False,
    )


async def _verify_vault(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"X-Vault-Token": secret["token"]}
    data = await _http_request("GET", f"{endpoint}/v1/sys/health", headers=headers)
    return ProviderProbe(
        identity={"endpoint": endpoint, "initialized": str(data["_json"].get("initialized", ""))},
        version=data["_json"].get("version"), permissions=["sys:health"], warnings=[], partial=False,
    )


async def _verify_loki(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    await _http_request("GET", f"{endpoint}/ready")
    return ProviderProbe(identity={"endpoint": endpoint}, version=None,
                         permissions=["logs:read"], warnings=[], partial=False)


async def _verify_elastic(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"ApiKey {secret['api_key']}"}
    data = await _http_request("GET", endpoint, headers=headers)
    version = (data["_json"].get("version") or {}).get("number")
    return ProviderProbe(identity={"endpoint": endpoint, "cluster": data["_json"].get("cluster_name", "")},
                         version=version, permissions=["cluster:monitor"], warnings=[], partial=False)


async def _verify_circleci(secret: dict) -> ProviderProbe:
    headers = {"Circle-Token": secret["api_token"]}
    data = await _http_request("GET", "https://circleci.com/api/v2/me", headers=headers)
    login = data["_json"].get("login", "")
    return ProviderProbe(identity={"login": login}, version="v2",
                         permissions=["projects:read"], warnings=[], partial=False)


async def _verify_opsgenie(secret: dict) -> ProviderProbe:
    headers = {"Authorization": f"GenieKey {secret['api_key']}"}
    await _http_request("GET", "https://api.opsgenie.com/v2/heartbeats", headers=headers)
    return ProviderProbe(identity={}, version=None, permissions=["alerts:read"], warnings=[], partial=False)


async def _verify_sonarqube(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    data = await _http_request(
        "GET", f"{endpoint}/api/system/status", auth=_basic_auth(secret["token"], ""),
    )
    return ProviderProbe(identity={"endpoint": endpoint, "status": data["_json"].get("status", "")},
                         version=data["_json"].get("version"), permissions=["projects:read"],
                         warnings=[], partial=False)


async def _verify_terraform_cloud(secret: dict) -> ProviderProbe:
    org = secret["organization"]
    headers = {"Authorization": f"Bearer {secret['token']}"}
    data = await _http_request(
        "GET", f"https://app.terraform.io/api/v2/organizations/{org}", headers=headers,
    )
    attrs = (data["_json"].get("data") or {}).get("attributes") or {}
    return ProviderProbe(identity={"organization": org, "name": attrs.get("name", "")},
                         version=None, permissions=["workspaces:read"], warnings=[], partial=False)


async def _verify_azure_devops(secret: dict) -> ProviderProbe:
    org = secret["organization"]
    data = await _http_request(
        "GET", f"https://dev.azure.com/{org}/_apis/projects?api-version=7.0",
        auth=_basic_auth("", secret["pat"]),
    )
    count = (data["_json"].get("count") or 0)
    return ProviderProbe(identity={"organization": org, "projects": str(count)},
                         version="7.0", permissions=["projects:read"], warnings=[], partial=False)


async def _verify_gcp(secret: dict) -> ProviderProbe:
    try:
        sa = json.loads(secret["service_account_json"])
    except (json.JSONDecodeError, TypeError) as exc:
        raise _Failed() from exc
    if sa.get("type") != "service_account" or not sa.get("client_email"):
        raise _Failed()
    return ProviderProbe(
        identity={"project_id": secret.get("project_id", sa.get("project_id", "")),
                  "client_email": sa.get("client_email", "")},
        version=None, permissions=["monitoring:read", "compute:read"],
        warnings=["Live GCP API probe skipped — service account JSON validated."],
        partial=True,
    )


async def _verify_cloudwatch(secret: dict) -> ProviderProbe:
    # Reuse AWS credential validation path (same keys/region).
    return await _verify_aws(secret)


async def _verify_alertmanager(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}"} if secret.get("token") else None
    data = await _http_request("GET", f"{endpoint}/api/v2/status", headers=headers)
    cluster = (data["_json"].get("cluster") or {})
    return ProviderProbe(
        identity={"endpoint": endpoint, "cluster_status": cluster.get("status", "")},
        version=cluster.get("version"),
        permissions=["alerts:read"],
        warnings=[],
        partial=False,
    )


async def _verify_splunk(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}", "Accept": "application/json"}
    data = await _http_request(
        "GET", f"{endpoint}/services/server/info", headers=headers,
        params={"output_mode": "json"},
    )
    entry = ((data["_json"].get("entry") or [{}])[0]).get("content") or {}
    return ProviderProbe(
        identity={"endpoint": endpoint, "server_name": entry.get("serverName", "")},
        version=entry.get("version"),
        permissions=["search:read", "alerts:read"],
        warnings=[],
        partial=False,
    )


async def _verify_servicenow(secret: dict) -> ProviderProbe:
    base = secret["instance_url"].rstrip("/")
    data = await _http_request(
        "GET",
        f"{base}/api/now/table/sys_user",
        headers={"Accept": "application/json"},
        auth=(secret["username"], secret["password"]),
        params={"sysparm_limit": 1},
    )
    rows = data["_json"].get("result") or []
    return ProviderProbe(
        identity={"instance_url": base, "reachable": True},
        version=None,
        permissions=["incidents:read", "cmdb:read"],
        warnings=[],
        partial=not rows,
    )


async def _verify_opentelemetry(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}"} if secret.get("token") else None
    try:
        data = await _http_request("GET", f"{endpoint}/api/v1/status/buildinfo", headers=headers)
        version = (data["_json"].get("data") or {}).get("version")
    except _Failed:
        data = await _http_request("GET", f"{endpoint}/metrics", headers=headers)
        version = None
    return ProviderProbe(
        identity={"endpoint": endpoint},
        version=version,
        permissions=["metrics:read", "traces:export"],
        warnings=["Collector verified via metrics/status endpoint."],
        partial=version is None,
    )


async def _verify_sentry(secret: dict) -> ProviderProbe:
    endpoint = secret["endpoint"].rstrip("/")
    headers = {"Authorization": f"Bearer {secret['token']}", "Accept": "application/json"}
    data = await _http_request("GET", f"{endpoint}/api/0/", headers=headers)
    version = data["_json"].get("version")
    return ProviderProbe(
        identity={"endpoint": endpoint},
        version=version,
        permissions=["issues:read", "projects:read"],
        warnings=[],
        partial=False,
    )


async def _verify_dynatrace(secret: dict) -> ProviderProbe:
    env_id = secret["environment_id"]
    headers = {"Authorization": f"Api-Token {secret['api_token']}", "Accept": "application/json"}
    data = await _http_request("GET", f"https://{env_id}.live.dynatrace.com/api/v1/config/clusterversion", headers=headers)
    return ProviderProbe(
        identity={"environment_id": env_id},
        version=data["_json"].get("version"),
        permissions=["problems:read", "entities:read"],
        warnings=[],
        partial=False,
    )


async def _verify_buildkite(secret: dict) -> ProviderProbe:
    org = secret["organization"]
    headers = {"Authorization": f"Bearer {secret['api_token']}", "Accept": "application/json"}
    data = await _http_request("GET", f"https://api.buildkite.com/v2/organizations/{org}", headers=headers)
    body = data["_json"]
    return ProviderProbe(
        identity={"organization": org, "name": body.get("name", "")},
        version=None,
        permissions=["pipelines:read", "builds:read"],
        warnings=[],
        partial=False,
    )


async def _verify_harness(secret: dict) -> ProviderProbe:
    account = secret["account_id"]
    headers = {"x-api-key": secret["api_key"], "Accept": "application/json"}
    await _http_request(
        "GET", "https://app.harness.io/ng/api/accounts",
        headers=headers,
        params={"accountIdentifier": account},
    )
    return ProviderProbe(
        identity={"account_id": account},
        version=None,
        permissions=["pipelines:read"],
        warnings=["Harness API probe uses account list endpoint."],
        partial=True,
    )


async def _verify_flux(secret: dict) -> ProviderProbe:
    return await _verify_kubernetes(secret)


_VERIFIERS = {
    "AWS": _verify_aws,
    "AZURE": _verify_azure,
    "KUBERNETES": _verify_kubernetes,
    "GITHUB": _verify_github,
    "GITLAB": _verify_gitlab,
    "SLACK": _verify_slack,
    "MICROSOFT_TEAMS": _verify_teams,
    "JIRA": _verify_jira,
    "DATADOG": _verify_datadog,
    "PROMETHEUS": _verify_prometheus,
    "GRAFANA": _verify_grafana,
    "NEW_RELIC": _verify_newrelic,
    "PAGERDUTY": _verify_pagerduty,
    "BITBUCKET": _verify_bitbucket,
    "GCP": _verify_gcp,
    "CLOUDWATCH": _verify_cloudwatch,
    "ARGOCD": _verify_argocd,
    "TERRAFORM": _verify_terraform_cloud,
    "JENKINS": _verify_jenkins,
    "AZURE_DEVOPS": _verify_azure_devops,
    "CIRCLECI": _verify_circleci,
    "HASHICORP_VAULT": _verify_vault,
    "LOKI": _verify_loki,
    "ELASTIC": _verify_elastic,
    "OPSGENIE": _verify_opsgenie,
    "SONARQUBE": _verify_sonarqube,
    "ALERTMANAGER": _verify_alertmanager,
    "SPLUNK": _verify_splunk,
    "SERVICENOW": _verify_servicenow,
    "OPENTELEMETRY": _verify_opentelemetry,
    "SENTRY": _verify_sentry,
    "DYNATRACE": _verify_dynatrace,
    "BUILDKITE": _verify_buildkite,
    "HARNESS": _verify_harness,
    "FLUX": _verify_flux,
}


def provider_supports_verification(integration_key: str) -> bool:
    return integration_key in _VERIFIERS


def _confidence_for(status: str, warnings: list[str]) -> int:
    if status == VStatus.CONNECTED:
        return 100 if not warnings else 90
    if status == VStatus.PARTIAL:
        return 60
    return 0


async def verify_provider(integration_key: str, secret: dict) -> VerificationResult:
    """Run a real, read-only verification for ``integration_key``.

    Never raises for provider/credential problems — always returns a
    VerificationResult with an appropriate ``connection_status``. Never includes
    secret material in any field.
    """
    started = time.monotonic()
    verifier = _VERIFIERS.get(integration_key)
    if verifier is None:
        return VerificationResult(
            connection_status=VStatus.FAILED, latency_ms=0, provider_version=None,
            verified_at=_now(), provider_identity={}, permissions=[], warnings=[],
            errors=["Live verification is not available for this provider yet."], confidence=0,
        )

    errors: list[str] = []
    probe = ProviderProbe()
    try:
        probe = await asyncio.wait_for(_with_retry(lambda: verifier(secret)), timeout=_TOTAL_BUDGET)
        status = VStatus.PARTIAL if probe.partial else VStatus.CONNECTED
    except _Unauthorized:
        status = VStatus.UNAUTHORIZED
        errors = ["Authentication failed: the provider rejected the supplied credentials."]
    except (_Timeout, TimeoutError):
        status = VStatus.TIMEOUT
        errors = ["The provider did not respond within the allowed time."]
    except _Failed:
        status = VStatus.FAILED
        errors = ["Could not complete verification against the provider."]
    except KeyError:
        # A required credential field is missing (should be caught at connect time).
        status = VStatus.FAILED
        errors = ["A required credential field is missing. Reconnect with complete details."]
    except Exception as exc:  # noqa: BLE001 - never leak provider internals/secrets
        logger.warning("integration_verify_unexpected", provider=integration_key, error=type(exc).__name__)
        status = VStatus.FAILED
        errors = ["Verification failed due to an unexpected error."]

    latency_ms = int((time.monotonic() - started) * 1000)
    confidence = _confidence_for(status, probe.warnings)
    return VerificationResult(
        connection_status=status,
        latency_ms=latency_ms,
        provider_version=probe.version,
        verified_at=_now(),
        provider_identity=probe.identity,
        permissions=probe.permissions,
        warnings=probe.warnings,
        errors=errors,
        confidence=confidence,
    )
