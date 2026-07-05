"""Sprint 58A.3 — Monitoring Ingestion Engine.

Real, read-only ingestion of firing alerts from connected providers, replacing
the old ``collect_alerts()`` stub. Two ingestion paths share one normalized
shape (``NormalizedAlert``):

  * POLL  — ``poll_<provider>(secret)`` reads the provider's live alert feed
            (background scheduler + manual ``/poll``).
  * WEBHOOK — ``parse_<provider>(payload)`` normalizes a pushed payload
            (``/monitoring/ingest``).

Supported: AWS CloudWatch, Azure Monitor, Prometheus, Alertmanager, Kubernetes
Events, GitHub Actions, GitLab Pipelines.

GUARANTEES:
  * READ-ONLY — only lists/reads; never mutates a provider resource.
  * SECRET-SAFE — no secret material in any returned field/log/exception.
  * BOUNDED + RESILIENT — per-call timeout, 3x exponential-backoff retry on
    transient failures; permanent failures raise ``IngestError`` (customer-safe)
    so the caller can dead-letter them.

Every normalized alert carries the Sprint 58A.3 required shape: alert_id,
alert_name, severity, status, resource, region, service, environment, labels,
annotations, description, timestamp, correlation_id.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.security.ssrf import SSRFError, safe_http_client

logger = get_logger(__name__)

_TIMEOUT = 12.0           # seconds per remote call
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 0.5   # seconds (doubles each attempt)
_PAGE = 100               # max alerts per provider per cycle

class IngestError(Exception):
    """Customer-safe ingestion failure (never contains secrets)."""


@dataclass
class NormalizedAlert:
    provider: str
    alert_id: str
    alert_name: str
    severity: str = "WARNING"
    status: str = "FIRING"
    service: str | None = None
    environment: str | None = None
    resource: str | None = None
    region: str | None = None
    labels: dict = field(default_factory=dict)
    annotations: dict = field(default_factory=dict)
    description: str | None = None
    timestamp: datetime | None = None
    correlation_id: str | None = None

    def with_correlation(self) -> NormalizedAlert:
        if not self.correlation_id:
            basis = "|".join([self.provider, self.alert_name, self.service or "",
                              self.environment or "", self.resource or ""])
            self.correlation_id = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:24]  # noqa: S324
        return self


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


async def _with_retry(factory):
    """Run ``factory()`` with 3x exponential backoff on transient failures."""
    delay = _RETRY_BASE_DELAY
    last: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return await factory()
        except IngestError:
            raise
        except SSRFError as exc:  # blocked target — deterministic, do not retry
            raise IngestError("Blocked request to a disallowed address.") from exc
        except Exception as exc:  # noqa: BLE001 - transient transport errors
            last = exc
            if attempt < _RETRY_ATTEMPTS - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
    raise IngestError(f"Provider unreachable after {_RETRY_ATTEMPTS} attempts: {type(last).__name__}")


# =========================================================================== #
# AWS CloudWatch
# =========================================================================== #
def _cloudwatch_collect(secret: dict) -> list[NormalizedAlert]:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    region = secret.get("region") or "us-east-1"
    cfg = Config(connect_timeout=_TIMEOUT, read_timeout=_TIMEOUT, retries={"max_attempts": 1})
    try:
        cw = boto3.client(
            "cloudwatch", region_name=region,
            aws_access_key_id=secret["access_key"], aws_secret_access_key=secret["secret_key"],
            config=cfg,
        )
        alarms = cw.describe_alarms(StateValue="ALARM", MaxRecords=_PAGE).get("MetricAlarms", [])
    except (ClientError, BotoCoreError) as exc:
        raise IngestError(f"CloudWatch read failed: {type(exc).__name__}") from exc

    out: list[NormalizedAlert] = []
    for al in alarms:
        dims = {d.get("Name"): d.get("Value") for d in (al.get("Dimensions") or [])}
        out.append(NormalizedAlert(
            provider="AWS", alert_id=al.get("AlarmArn", al.get("AlarmName", "")),
            alert_name=al.get("AlarmName", "cloudwatch-alarm"), severity="HIGH", status="FIRING",
            service=dims.get("ServiceName") or al.get("Namespace"), region=region,
            resource=dims.get("InstanceId") or dims.get("FunctionName") or al.get("Namespace"),
            labels={"namespace": al.get("Namespace"), "metric": al.get("MetricName"), **dims},
            annotations={"reason": al.get("StateReason")},
            description=al.get("AlarmDescription") or al.get("StateReason"),
            timestamp=_parse_ts(al.get("StateUpdatedTimestamp")),
        ).with_correlation())
    return out


async def poll_cloudwatch(secret: dict) -> list[NormalizedAlert]:
    return await _with_retry(lambda: asyncio.to_thread(_cloudwatch_collect, secret))


# =========================================================================== #
# Azure Monitor
# =========================================================================== #
_AZ_SEV = {"Sev0": "CRITICAL", "Sev1": "CRITICAL", "Sev2": "HIGH", "Sev3": "WARNING", "Sev4": "INFO"}


async def poll_azure_monitor(secret: dict) -> list[NormalizedAlert]:
    async def _run():
        tenant = secret["tenant_id"]
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            tok = await c.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={"grant_type": "client_credentials", "client_id": secret["client_id"],
                      "client_secret": secret["client_secret"],
                      "scope": "https://management.azure.com/.default"},
            )
            if tok.status_code >= 400:
                raise IngestError("Azure Monitor auth failed.")
            token = tok.json().get("access_token")
            sub = secret["subscription_id"]
            resp = await c.get(
                f"https://management.azure.com/subscriptions/{sub}/providers/"
                "Microsoft.AlertsManagement/alerts",
                headers={"Authorization": f"Bearer {token}"},
                params={"api-version": "2019-05-05-preview", "alertState": "New"},
            )
        if resp.status_code in (401, 403):
            raise IngestError("Azure Monitor denied access.")
        if resp.status_code >= 400:
            return []
        out: list[NormalizedAlert] = []
        for item in (resp.json().get("value") or [])[:_PAGE]:
            props = (item.get("properties") or {}).get("essentials") or {}
            out.append(NormalizedAlert(
                provider="AZURE", alert_id=item.get("id", item.get("name", "")),
                alert_name=item.get("name", "azure-alert"),
                severity=_AZ_SEV.get(props.get("severity"), "WARNING"),
                status="RESOLVED" if props.get("monitorCondition") == "Resolved" else "FIRING",
                resource=props.get("targetResource"), region=props.get("targetResourceGroup"),
                service=props.get("targetResourceName"),
                labels={"signalType": props.get("signalType"),
                        "monitorService": props.get("monitorService")},
                annotations={"alertRule": props.get("alertRule"),
                             "description": props.get("description")},
                description=props.get("description") or props.get("alertRule"),
                timestamp=_parse_ts(props.get("startDateTime")),
            ).with_correlation())
        return out

    return await _with_retry(_run)


# =========================================================================== #
# Prometheus  (/api/v1/alerts)
# =========================================================================== #
def _norm_endpoint(secret: dict) -> str:
    ep = (secret.get("endpoint") or secret.get("base_url") or "").rstrip("/")
    if not ep:
        raise IngestError("No endpoint configured.")
    return ep


def _auth_headers(secret: dict) -> dict:
    token = secret.get("token") or secret.get("api_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def poll_prometheus(secret: dict) -> list[NormalizedAlert]:
    async def _run():
        ep = _norm_endpoint(secret)
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(f"{ep}/api/v1/alerts", headers=_auth_headers(secret))
        if resp.status_code in (401, 403):
            raise IngestError("Prometheus denied access.")
        if resp.status_code >= 400:
            return []
        alerts = ((resp.json() or {}).get("data") or {}).get("alerts") or []
        return [_alert_from_prom("PROMETHEUS", a) for a in alerts[:_PAGE]]

    return await _with_retry(_run)


def _alert_from_prom(provider: str, a: dict) -> NormalizedAlert:
    labels = a.get("labels") or {}
    annotations = a.get("annotations") or {}
    state = (a.get("state") or a.get("status") or "firing")
    if isinstance(state, dict):
        state = state.get("state", "firing")
    return NormalizedAlert(
        provider=provider, alert_id=labels.get("alertname", "") + ":" + (labels.get("instance") or ""),
        alert_name=labels.get("alertname", "prometheus-alert"),
        severity=labels.get("severity", "WARNING"),
        status="RESOLVED" if str(state).lower() in ("resolved",) else "FIRING",
        service=labels.get("service") or labels.get("job"),
        environment=labels.get("environment") or labels.get("env") or labels.get("namespace"),
        resource=labels.get("instance") or labels.get("pod"), region=labels.get("region"),
        labels=labels, annotations=annotations,
        description=annotations.get("description") or annotations.get("summary"),
        timestamp=_parse_ts(a.get("activeAt") or a.get("startsAt")),
    ).with_correlation()


# =========================================================================== #
# Alertmanager  (/api/v2/alerts)
# =========================================================================== #
async def poll_alertmanager(secret: dict) -> list[NormalizedAlert]:
    async def _run():
        ep = _norm_endpoint(secret)
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(f"{ep}/api/v2/alerts", headers=_auth_headers(secret),
                               params={"active": "true", "silenced": "false"})
        if resp.status_code in (401, 403):
            raise IngestError("Alertmanager denied access.")
        if resp.status_code >= 400:
            return []
        return [_alert_from_am(a) for a in (resp.json() or [])[:_PAGE]]

    return await _with_retry(_run)


def _alert_from_am(a: dict) -> NormalizedAlert:
    labels = a.get("labels") or {}
    annotations = a.get("annotations") or {}
    state = ((a.get("status") or {}).get("state")) or "active"
    return NormalizedAlert(
        provider="ALERTMANAGER",
        alert_id=a.get("fingerprint") or labels.get("alertname", "alertmanager-alert"),
        alert_name=labels.get("alertname", "alertmanager-alert"),
        severity=labels.get("severity", "WARNING"),
        status="RESOLVED" if state == "resolved" else "FIRING",
        service=labels.get("service") or labels.get("job"),
        environment=labels.get("environment") or labels.get("namespace"),
        resource=labels.get("instance") or labels.get("pod"), region=labels.get("region"),
        labels=labels, annotations=annotations,
        description=annotations.get("description") or annotations.get("summary"),
        timestamp=_parse_ts(a.get("startsAt")),
    ).with_correlation()


# =========================================================================== #
# Kubernetes Events (Warning)
# =========================================================================== #
_K8S_HIGH_REASONS = {"Failed", "FailedMount", "BackOff", "Unhealthy", "FailedScheduling",
                     "CrashLoopBackOff", "OOMKilling", "NodeNotReady"}


def _k8s_collect(secret: dict) -> list[NormalizedAlert]:
    import yaml
    from kubernetes import client, config
    from kubernetes.client.exceptions import ApiException

    raw = secret.get("kubeconfig")
    if not raw:
        raise IngestError("No kubeconfig configured.")
    try:
        cfg = yaml.safe_load(raw)
        loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
        configuration = client.Configuration()
        loader.load_and_set(configuration)
        core = client.CoreV1Api(client.ApiClient(configuration))
        events = core.list_event_for_all_namespaces(
            limit=_PAGE, field_selector="type=Warning", _request_timeout=_TIMEOUT).items
    except ApiException as exc:
        raise IngestError(f"Kubernetes events read denied: {exc.status}") from exc
    except Exception as exc:  # noqa: BLE001 - transport/config
        raise IngestError(f"Kubernetes API unreachable: {type(exc).__name__}") from exc

    out: list[NormalizedAlert] = []
    for e in events:
        obj = e.involved_object
        reason = e.reason or "Warning"
        out.append(NormalizedAlert(
            provider="KUBERNETES",
            alert_id=(e.metadata.uid if e.metadata else None) or f"{reason}:{getattr(obj, 'name', '')}",
            alert_name=reason, severity="HIGH" if reason in _K8S_HIGH_REASONS else "WARNING",
            status="FIRING", service=getattr(obj, "name", None),
            environment=getattr(obj, "namespace", None),
            resource=f"{getattr(obj, 'kind', '')}/{getattr(obj, 'name', '')}".strip("/"),
            region=getattr(obj, "namespace", None),
            labels={"kind": getattr(obj, "kind", None), "reason": reason,
                    "count": e.count, "component": (e.source.component if e.source else None)},
            annotations={"message": e.message},
            description=e.message,
            timestamp=_parse_ts(e.last_timestamp or e.event_time or
                                (e.metadata.creation_timestamp if e.metadata else None)),
        ).with_correlation())
    return out


async def poll_kubernetes_events(secret: dict) -> list[NormalizedAlert]:
    return await _with_retry(lambda: asyncio.to_thread(_k8s_collect, secret))


# =========================================================================== #
# GitHub Actions (failed workflow runs)
# =========================================================================== #
async def poll_github_actions(secret: dict) -> list[NormalizedAlert]:
    repos = secret.get("repositories") or ([secret["repository"]] if secret.get("repository") else [])
    if not repos:
        # Truly nothing to scan (no repo configured) — zero alerts, not a failure.
        return []
    token = secret.get("token")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            for repo in repos[:10]:
                resp = await c.get(
                    f"https://api.github.com/repos/{repo}/actions/runs",
                    headers=headers, params={"status": "failure", "per_page": 30})
                if resp.status_code in (401, 403):
                    raise IngestError("GitHub denied access.")
                if resp.status_code >= 400:
                    continue
                for run in (resp.json().get("workflow_runs") or [])[:30]:
                    out.append(NormalizedAlert(
                        provider="GITHUB", alert_id=str(run.get("id")),
                        alert_name=f"workflow-failed:{run.get('name', 'workflow')}",
                        severity="HIGH", status="FIRING", service=repo,
                        environment=run.get("head_branch"), resource=repo, region=None,
                        labels={"workflow": run.get("name"), "branch": run.get("head_branch"),
                                "event": run.get("event")},
                        annotations={"url": run.get("html_url"), "conclusion": run.get("conclusion")},
                        description=f"Workflow '{run.get('name')}' failed on {repo}@{run.get('head_branch')}",
                        timestamp=_parse_ts(run.get("updated_at") or run.get("created_at")),
                    ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# GitLab Pipelines (failed)
# =========================================================================== #
async def poll_gitlab_pipelines(secret: dict) -> list[NormalizedAlert]:
    base = (secret.get("base_url") or "https://gitlab.com").rstrip("/")
    projects = secret.get("projects") or ([secret["project"]] if secret.get("project") else [])
    if not projects:
        return []
    headers = {"PRIVATE-TOKEN": secret.get("token", "")}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            for proj in projects[:10]:
                pid = str(proj).replace("/", "%2F")
                resp = await c.get(f"{base}/api/v4/projects/{pid}/pipelines",
                                   headers=headers, params={"status": "failed", "per_page": 30})
                if resp.status_code in (401, 403):
                    raise IngestError("GitLab denied access.")
                if resp.status_code >= 400:
                    continue
                for pl in (resp.json() or [])[:30]:
                    out.append(NormalizedAlert(
                        provider="GITLAB", alert_id=str(pl.get("id")),
                        alert_name=f"pipeline-failed:{proj}", severity="HIGH", status="FIRING",
                        service=str(proj), environment=pl.get("ref"), resource=str(proj),
                        labels={"ref": pl.get("ref"), "source": pl.get("source")},
                        annotations={"url": pl.get("web_url")},
                        description=f"Pipeline #{pl.get('id')} failed on {proj}@{pl.get('ref')}",
                        timestamp=_parse_ts(pl.get("updated_at") or pl.get("created_at")),
                    ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# Jenkins (failed builds)
# =========================================================================== #
async def poll_jenkins(secret: dict) -> list[NormalizedAlert]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json
    from app.delivery.pipelines.jenkins_live import _flatten_jobs, _job_base_url

    endpoint = (secret.get("endpoint") or "").rstrip("/")
    user = secret.get("username")
    token = secret.get("api_token")
    if not endpoint or not user or not token:
        return []

    async def _run():
        out: list[NormalizedAlert] = []
        data = await asyncio.to_thread(
            get_json,
            f"{endpoint}/api/json?tree=jobs[name,fullName,_class,jobs[name,fullName,_class]]",
            auth=(user, token),
        )
        for full_name, _job in _flatten_jobs(data.get("jobs", []))[:10]:
            base = _job_base_url(endpoint, full_name)
            tree = "builds[number,result,url,timestamp]"
            try:
                builds = await asyncio.to_thread(
                    get_json, f"{base}/api/json?tree={tree}", auth=(user, token),
                )
            except Exception:  # noqa: BLE001
                continue
            for build in (builds.get("builds") or [])[:5]:
                if not isinstance(build, dict):
                    continue
                result = (build.get("result") or "").upper()
                if result not in ("FAILURE", "UNSTABLE"):
                    continue
                out.append(NormalizedAlert(
                    provider="JENKINS",
                    alert_id=f"{full_name}#{build.get('number')}",
                    alert_name=f"build-failed:{full_name}",
                    severity="HIGH", status="FIRING", service=full_name,
                    resource=full_name, labels={"job": full_name, "result": result},
                    annotations={"url": build.get("url")},
                    description=f"Jenkins build #{build.get('number')} failed on {full_name}",
                    timestamp=_parse_ts(build.get("timestamp")),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# CircleCI (failed pipelines)
# =========================================================================== #
async def poll_circleci(secret: dict) -> list[NormalizedAlert]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    token = secret.get("api_token")
    if not token:
        return []
    headers = {"Circle-Token": token}

    async def _run():
        out: list[NormalizedAlert] = []
        collabs = await asyncio.to_thread(
            get_json, "https://circleci.com/api/v2/me/collaborations", headers=headers,
        )
        items = collabs if isinstance(collabs, list) else collabs.get("items", [])
        for collab in (items or [])[:10]:
            if not isinstance(collab, dict):
                continue
            slug = collab.get("vcs_url") or collab.get("slug") or ""
            if not slug:
                continue
            proj = slug.replace("https://github.com/", "gh/").replace("https://gitlab.com/", "gl/")
            if not proj.startswith(("gh/", "bb/")):
                proj = f"gh/{proj}" if "/" in proj else slug
            try:
                data = await asyncio.to_thread(
                    get_json, f"https://circleci.com/api/v2/project/{proj}/pipeline", headers=headers,
                )
            except Exception:  # noqa: BLE001
                continue
            for pl in (data.get("items") or [])[:10]:
                state = (pl.get("state") or "").upper()
                if state not in ("FAILED", "ERROR"):
                    continue
                out.append(NormalizedAlert(
                    provider="CIRCLECI",
                    alert_id=str(pl.get("id")),
                    alert_name=f"pipeline-failed:{proj}",
                    severity="HIGH", status="FIRING", service=proj,
                    resource=proj, labels={"state": state},
                    annotations={"url": pl.get("web_url")},
                    description=f"CircleCI pipeline {pl.get('id')} failed on {proj}",
                    timestamp=_parse_ts(pl.get("created_at")),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# Datadog (triggered monitors)
# =========================================================================== #
async def poll_datadog(secret: dict) -> list[NormalizedAlert]:
    api_key = secret.get("api_key")
    app_key = secret.get("app_key")
    site = secret.get("site") or "https://api.datadoghq.com"
    if not site.startswith("http"):
        site = f"https://api.{site.strip('.')}"
    site = site.rstrip("/")
    if not api_key or not app_key:
        return []
    headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(
                f"{site}/api/v1/monitor",
                headers=headers, params={"monitor_tags": "status:alert", "page_size": 50},
            )
            if resp.status_code in (401, 403):
                raise IngestError("Datadog denied access.")
            if resp.status_code >= 400:
                return []
            for mon in (resp.json() or [])[:_PAGE]:
                if not isinstance(mon, dict):
                    continue
                out.append(NormalizedAlert(
                    provider="DATADOG",
                    alert_id=str(mon.get("id")),
                    alert_name=mon.get("name") or f"monitor-{mon.get('id')}",
                    severity="WARNING",
                    status="FIRING", service=mon.get("type"),
                    labels={"type": mon.get("type"), "query": (mon.get("query") or "")[:120]},
                    description=mon.get("message") or mon.get("name"),
                    timestamp=_now(),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# PagerDuty (open incidents)
# =========================================================================== #
async def poll_pagerduty(secret: dict) -> list[NormalizedAlert]:
    token = secret.get("api_key") or secret.get("api_token") or secret.get("token")
    if not token:
        return []
    headers = {"Authorization": f"Token token={token}", "Accept": "application/vnd.pagerduty+json;version=2"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(
                "https://api.pagerduty.com/incidents",
                headers=headers,
                params={"statuses[]": "triggered", "limit": 50},
            )
            if resp.status_code in (401, 403):
                raise IngestError("PagerDuty denied access.")
            if resp.status_code >= 400:
                return []
            for inc in (resp.json().get("incidents") or [])[:_PAGE]:
                if not isinstance(inc, dict):
                    continue
                out.append(NormalizedAlert(
                    provider="PAGERDUTY",
                    alert_id=inc.get("id", ""),
                    alert_name=inc.get("title") or "pagerduty-incident",
                    severity=(inc.get("urgency") or "high").upper(),
                    status="FIRING", service=(inc.get("service") or {}).get("summary"),
                    labels={"urgency": inc.get("urgency"), "status": inc.get("status")},
                    annotations={"url": inc.get("html_url")},
                    description=inc.get("title"),
                    timestamp=_parse_ts(inc.get("created_at")),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


    return await _with_retry(_run)


# =========================================================================== #
# Opsgenie (open alerts)
# =========================================================================== #
async def poll_opsgenie(secret: dict) -> list[NormalizedAlert]:
    api_key = secret.get("api_key")
    if not api_key:
        return []
    headers = {"Authorization": f"GenieKey {api_key}"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(
                "https://api.opsgenie.com/v2/alerts",
                headers=headers,
                params={"query": "status:open", "limit": 50},
            )
            if resp.status_code in (401, 403):
                raise IngestError("Opsgenie denied access.")
            if resp.status_code >= 400:
                return []
            for alert in (resp.json().get("data") or [])[:_PAGE]:
                if not isinstance(alert, dict):
                    continue
                out.append(NormalizedAlert(
                    provider="OPSGENIE",
                    alert_id=alert.get("id", ""),
                    alert_name=alert.get("message") or "opsgenie-alert",
                    severity=(alert.get("priority") or "P3").upper(),
                    status="FIRING",
                    service=(alert.get("source") or ""),
                    labels={"priority": alert.get("priority"), "status": alert.get("status")},
                    description=alert.get("message"),
                    timestamp=_parse_ts(alert.get("createdAt")),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# Grafana (unified alerting)
# =========================================================================== #
async def poll_grafana(secret: dict) -> list[NormalizedAlert]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(f"{endpoint}/api/alerting/alerts", headers=headers)
            if resp.status_code == 404:
                resp = await c.get(f"{endpoint}/api/alerts", headers=headers)
            if resp.status_code in (401, 403):
                raise IngestError("Grafana denied access.")
            if resp.status_code >= 400:
                return []
            alerts = resp.json() if isinstance(resp.json(), list) else (resp.json().get("data") or [])
            for alert in alerts[:_PAGE]:
                if not isinstance(alert, dict):
                    continue
                labels = alert.get("labels") or {}
                out.append(NormalizedAlert(
                    provider="GRAFANA",
                    alert_id=str(alert.get("fingerprint") or alert.get("id") or labels.get("alertname")),
                    alert_name=labels.get("alertname") or alert.get("name") or "grafana-alert",
                    severity=labels.get("severity", "WARNING"),
                    status="FIRING",
                    service=labels.get("service"),
                    labels=labels,
                    description=alert.get("annotations", {}).get("description") if isinstance(alert.get("annotations"), dict) else None,
                    timestamp=_now(),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# New Relic (open incidents)
# =========================================================================== #
async def poll_newrelic(secret: dict) -> list[NormalizedAlert]:
    api_key = secret.get("api_key")
    if not api_key:
        return []
    headers = {"API-Key": api_key, "Content-Type": "application/json"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get("https://api.newrelic.com/v2/alerts_incidents.json", headers=headers,
                              params={"only_open": "true", "page_size": 50})
            if resp.status_code in (401, 403):
                raise IngestError("New Relic denied access.")
            if resp.status_code >= 400:
                return []
            for inc in (resp.json().get("incidents") or [])[:_PAGE]:
                if not isinstance(inc, dict):
                    continue
                out.append(NormalizedAlert(
                    provider="NEW_RELIC",
                    alert_id=str(inc.get("id")),
                    alert_name=inc.get("description") or "newrelic-incident",
                    severity="HIGH", status="FIRING",
                    service=str(inc.get("policy_name") or ""),
                    labels={"policy": inc.get("policy_name")},
                    description=inc.get("description"),
                    timestamp=_parse_ts(inc.get("opened_at")),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# Loki (ruler alerts via prometheus-compatible API)
# =========================================================================== #
async def poll_loki(secret: dict) -> list[NormalizedAlert]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    if not endpoint:
        return []

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(f"{endpoint}/prometheus/api/v1/alerts")
            if resp.status_code >= 400:
                health = await c.get(f"{endpoint}/ready")
                if health.status_code >= 400:
                    raise IngestError("Loki is not reachable.")
                return []
            for alert in (resp.json().get("data", {}).get("alerts") or [])[:_PAGE]:
                if not isinstance(alert, dict):
                    continue
                labels = alert.get("labels") or {}
                out.append(NormalizedAlert(
                    provider="LOKI",
                    alert_id=labels.get("alertname", "loki-alert"),
                    alert_name=labels.get("alertname", "loki-alert"),
                    severity=labels.get("severity", "WARNING"),
                    status="FIRING",
                    labels=labels,
                    description=alert.get("annotations", {}).get("description") if isinstance(alert.get("annotations"), dict) else None,
                    timestamp=_now(),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# Elasticsearch (cluster health degradation)
# =========================================================================== #
async def poll_elastic(secret: dict) -> list[NormalizedAlert]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    api_key = secret.get("api_key")
    if not endpoint or not api_key:
        return []
    headers = {"Authorization": f"ApiKey {api_key}"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(f"{endpoint}/_cluster/health", headers=headers)
            if resp.status_code in (401, 403):
                raise IngestError("Elasticsearch denied access.")
            if resp.status_code >= 400:
                return []
            health = resp.json()
            status = (health.get("status") or "").lower()
            if status in ("red", "yellow"):
                out.append(NormalizedAlert(
                    provider="ELASTIC",
                    alert_id=f"cluster-{status}",
                    alert_name=f"elasticsearch-cluster-{status}",
                    severity="CRITICAL" if status == "red" else "WARNING",
                    status="FIRING",
                    service=health.get("cluster_name"),
                    labels={"status": status},
                    description=f"Elasticsearch cluster health is {status}",
                    timestamp=_now(),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# Bitbucket (failed pipelines)
# =========================================================================== #
async def poll_bitbucket(secret: dict) -> list[NormalizedAlert]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    user = secret.get("username")
    pwd = secret.get("app_password")
    if not user or not pwd:
        return []
    auth = (user, pwd)

    async def _run():
        out: list[NormalizedAlert] = []
        repos = await asyncio.to_thread(
            get_json, "https://api.bitbucket.org/2.0/repositories?pagelen=20&role=member", auth=auth,
        )
        for repo in (repos.get("values") or [])[:10]:
            if not isinstance(repo, dict):
                continue
            full = repo.get("full_name") or ""
            if "/" not in full:
                continue
            ws, slug = full.split("/", 1)
            try:
                pls = await asyncio.to_thread(
                    get_json,
                    f"https://api.bitbucket.org/2.0/repositories/{ws}/{slug}/pipelines/?pagelen=10",
                    auth=auth,
                )
            except Exception:  # noqa: BLE001
                continue
            for pl in (pls.get("values") or []):
                result = ((pl.get("state") or {}).get("result") or {}).get("name")
                if result != "FAILED":
                    continue
                out.append(NormalizedAlert(
                    provider="BITBUCKET",
                    alert_id=str(pl.get("uuid") or pl.get("build_number")),
                    alert_name=f"pipeline-failed:{full}",
                    severity="HIGH", status="FIRING", service=full,
                    labels={"repo": full, "build": str(pl.get("build_number"))},
                    description=f"Bitbucket pipeline failed on {full}",
                    timestamp=_parse_ts(pl.get("created_on")),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# SonarQube (open blocker/critical issues)
# =========================================================================== #
async def poll_sonarqube(secret: dict) -> list[NormalizedAlert]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []

    async def _run():
        out: list[NormalizedAlert] = []
        data = await asyncio.to_thread(
            get_json,
            f"{endpoint}/api/issues/search?resolved=false&severities=BLOCKER,CRITICAL&ps=50",
            auth=(token, ""),
        )
        for issue in (data.get("issues") or [])[:_PAGE]:
            if not isinstance(issue, dict):
                continue
            out.append(NormalizedAlert(
                provider="SONARQUBE",
                alert_id=issue.get("key", ""),
                alert_name=f"sonar-{issue.get('type', 'issue')}",
                severity=issue.get("severity", "CRITICAL"),
                status="FIRING",
                service=issue.get("project"),
                labels={"type": issue.get("type"), "rule": issue.get("rule")},
                description=issue.get("message"),
                timestamp=_parse_ts(issue.get("creationDate")),
            ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# =========================================================================== #
# GCP Cloud Monitoring (open incidents / policies)
# =========================================================================== #
async def poll_gcp_monitoring(secret: dict) -> list[NormalizedAlert]:
    import asyncio

    from app.services.gcp_auth import gcp_access_token, parse_service_account

    try:
        sa, project = parse_service_account(secret)
        token = await asyncio.to_thread(
            gcp_access_token, sa, ["https://www.googleapis.com/auth/monitoring.read"],
        )
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"GCP auth failed: {type(exc).__name__}") from exc

    headers = {"Authorization": f"Bearer {token}"}

    async def _run():
        out: list[NormalizedAlert] = []
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(
                f"https://monitoring.googleapis.com/v3/projects/{project}/alertPolicies",
                headers=headers,
                params={"filter": "enabled=true", "pageSize": 50},
            )
            if resp.status_code in (401, 403):
                raise IngestError("GCP Monitoring denied access.")
            if resp.status_code >= 400:
                return []
            for pol in (resp.json().get("alertPolicies") or [])[:_PAGE]:
                if not isinstance(pol, dict):
                    continue
                name = pol.get("displayName") or pol.get("name", "").split("/")[-1]
                out.append(NormalizedAlert(
                    provider="GCP",
                    alert_id=pol.get("name", name),
                    alert_name=name,
                    severity="WARNING",
                    status="FIRING",
                    service=project,
                    resource=project,
                    labels={"combiner": pol.get("combiner")},
                    description=f"GCP alert policy enabled: {name}",
                    timestamp=_now(),
                ).with_correlation())
        return out[:_PAGE]

    return await _with_retry(_run)


# --------------------------------------------------------------------------- #
INGEST_POLLERS = {
    "AWS": poll_cloudwatch,
    "AZURE": poll_azure_monitor,
    "CLOUDWATCH": poll_cloudwatch,
    "PROMETHEUS": poll_prometheus,
    "ALERTMANAGER": poll_alertmanager,
    "KUBERNETES": poll_kubernetes_events,
    "GITHUB": poll_github_actions,
    "GITLAB": poll_gitlab_pipelines,
    "BITBUCKET": poll_bitbucket,
    "JENKINS": poll_jenkins,
    "CIRCLECI": poll_circleci,
    "DATADOG": poll_datadog,
    "PAGERDUTY": poll_pagerduty,
    "OPSGENIE": poll_opsgenie,
    "GRAFANA": poll_grafana,
    "NEW_RELIC": poll_newrelic,
    "LOKI": poll_loki,
    "ELASTIC": poll_elastic,
    "SONARQUBE": poll_sonarqube,
    "GCP": poll_gcp_monitoring,
}


INGEST_PROVIDERS = frozenset(INGEST_POLLERS.keys())


def provider_supports_ingestion(provider: str) -> bool:
    return (provider or "").upper() in INGEST_POLLERS


async def poll_provider(provider: str, secret: dict) -> list[NormalizedAlert]:
    poller = INGEST_POLLERS.get((provider or "").upper())
    if poller is None:
        return []
    return await poller(secret)


# =========================================================================== #
# Webhook parsers (push ingestion)
# =========================================================================== #
def parse_alertmanager(payload: dict) -> list[NormalizedAlert]:
    """Alertmanager webhook (also covers Prometheus, since Prometheus pushes via AM)."""
    return [_alert_from_am_webhook(a) for a in (payload.get("alerts") or [])][:_PAGE]


def _alert_from_am_webhook(a: dict) -> NormalizedAlert:
    labels = a.get("labels") or {}
    annotations = a.get("annotations") or {}
    return NormalizedAlert(
        provider="ALERTMANAGER",
        alert_id=a.get("fingerprint") or labels.get("alertname", "alertmanager-alert"),
        alert_name=labels.get("alertname", "alertmanager-alert"),
        severity=labels.get("severity", "WARNING"),
        status="RESOLVED" if (a.get("status") == "resolved") else "FIRING",
        service=labels.get("service") or labels.get("job"),
        environment=labels.get("environment") or labels.get("namespace"),
        resource=labels.get("instance") or labels.get("pod"), region=labels.get("region"),
        labels=labels, annotations=annotations,
        description=annotations.get("description") or annotations.get("summary"),
        timestamp=_parse_ts(a.get("startsAt")),
    ).with_correlation()


def parse_cloudwatch(payload: dict) -> list[NormalizedAlert]:
    """AWS CloudWatch alarm delivered via SNS (Message is JSON)."""
    import json

    msg = payload.get("Message")
    data = json.loads(msg) if isinstance(msg, str) else (msg or payload)
    state = (data.get("NewStateValue") or "ALARM").upper()
    region = data.get("Region") or data.get("AWSAccountId")
    trigger = data.get("Trigger") or {}
    return [NormalizedAlert(
        provider="AWS", alert_id=data.get("AlarmArn", data.get("AlarmName", "cloudwatch-alarm")),
        alert_name=data.get("AlarmName", "cloudwatch-alarm"),
        severity="HIGH" if state == "ALARM" else "INFO",
        status="RESOLVED" if state == "OK" else "FIRING",
        service=trigger.get("Namespace"), region=region, resource=trigger.get("MetricName"),
        labels={"namespace": trigger.get("Namespace"), "metric": trigger.get("MetricName")},
        annotations={"reason": data.get("NewStateReason")},
        description=data.get("AlarmDescription") or data.get("NewStateReason"),
        timestamp=_parse_ts(data.get("StateChangeTime")),
    ).with_correlation()]


def parse_azure_monitor(payload: dict) -> list[NormalizedAlert]:
    """Azure Monitor Common Alert Schema webhook."""
    data = payload.get("data") or {}
    ess = data.get("essentials") or {}
    return [NormalizedAlert(
        provider="AZURE", alert_id=ess.get("alertId", ess.get("alertRule", "azure-alert")),
        alert_name=ess.get("alertRule", "azure-alert"),
        severity=_AZ_SEV.get(ess.get("severity"), "WARNING"),
        status="RESOLVED" if ess.get("monitorCondition") == "Resolved" else "FIRING",
        resource=(ess.get("alertTargetIDs") or [None])[0], region=ess.get("targetResourceGroup"),
        service=ess.get("targetResourceName"),
        labels={"signalType": ess.get("signalType"), "monitorService": ess.get("monitoringService")},
        annotations={"description": ess.get("description")},
        description=ess.get("description") or ess.get("alertRule"),
        timestamp=_parse_ts(ess.get("firedDateTime")),
    ).with_correlation()]


def parse_github(payload: dict) -> list[NormalizedAlert]:
    """GitHub Actions ``workflow_run`` webhook (only failed conclusions alert)."""
    run = payload.get("workflow_run") or {}
    repo = (payload.get("repository") or {}).get("full_name")
    if (run.get("conclusion") or "").lower() not in ("failure", "timed_out", "cancelled"):
        return []
    return [NormalizedAlert(
        provider="GITHUB", alert_id=str(run.get("id")),
        alert_name=f"workflow-failed:{run.get('name', 'workflow')}", severity="HIGH", status="FIRING",
        service=repo, environment=run.get("head_branch"), resource=repo,
        labels={"workflow": run.get("name"), "branch": run.get("head_branch")},
        annotations={"url": run.get("html_url"), "conclusion": run.get("conclusion")},
        description=f"Workflow '{run.get('name')}' {run.get('conclusion')} on {repo}",
        timestamp=_parse_ts(run.get("updated_at")),
    ).with_correlation()]


def parse_gitlab(payload: dict) -> list[NormalizedAlert]:
    """GitLab Pipeline event webhook (only failed pipelines alert)."""
    attrs = payload.get("object_attributes") or {}
    proj = (payload.get("project") or {}).get("path_with_namespace")
    if (attrs.get("status") or "").lower() != "failed":
        return []
    return [NormalizedAlert(
        provider="GITLAB", alert_id=str(attrs.get("id")),
        alert_name=f"pipeline-failed:{proj}", severity="HIGH", status="FIRING",
        service=proj, environment=attrs.get("ref"), resource=proj,
        labels={"ref": attrs.get("ref"), "source": attrs.get("source")},
        annotations={"url": attrs.get("url")},
        description=f"Pipeline #{attrs.get('id')} failed on {proj}@{attrs.get('ref')}",
        timestamp=_parse_ts(attrs.get("finished_at") or attrs.get("created_at")),
    ).with_correlation()]


def parse_jenkins(payload: dict) -> list[NormalizedAlert]:
    """Jenkins build notification webhook (failed/unstable builds only)."""
    build = payload.get("build") or {}
    job_name = (
        payload.get("name")
        or payload.get("fullName")
        or (payload.get("project") or {}).get("name")
        or build.get("fullName")
    )
    result = (
        build.get("status")
        or build.get("result")
        or payload.get("buildStatus")
        or ""
    ).upper()
    if result not in ("FAILURE", "UNSTABLE", "FAILED"):
        return []
    number = build.get("number") or payload.get("buildNumber")
    url = build.get("url") or build.get("full_url") or payload.get("buildUrl")
    alert_id = f"{job_name}#{number}" if job_name and number is not None else str(number or job_name or "jenkins-build")
    return [NormalizedAlert(
        provider="JENKINS",
        alert_id=alert_id,
        alert_name=f"build-failed:{job_name or 'job'}",
        severity="HIGH",
        status="FIRING",
        service=job_name,
        resource=job_name,
        labels={"job": job_name, "result": result},
        annotations={"url": url},
        description=f"Jenkins build #{number} failed on {job_name}" if number else f"Jenkins build failed on {job_name}",
        timestamp=_parse_ts(build.get("timestamp") or payload.get("timestamp")),
    ).with_correlation()]


def parse_datadog(payload: dict) -> list[NormalizedAlert]:
    """Datadog monitor notification webhook (v1 alert payload)."""
    title = payload.get("title") or payload.get("alert_title") or "datadog-alert"
    alert_type = (payload.get("alert_type") or payload.get("event_type") or "error").lower()
    status = "RESOLVED" if alert_type in ("success", "recovery", "resolved") else "FIRING"
    severity = "CRITICAL" if alert_type in ("error", "failure") else "WARNING"
    tags = payload.get("tags") or []
    labels = {t.split(":", 1)[0]: t.split(":", 1)[1] for t in tags if ":" in t}
    return [NormalizedAlert(
        provider="DATADOG",
        alert_id=str(payload.get("id") or payload.get("alert_id") or title),
        alert_name=title,
        severity=severity,
        status=status,
        service=payload.get("org") or labels.get("service"),
        environment=labels.get("env") or labels.get("environment"),
        resource=payload.get("host") or labels.get("host"),
        labels=labels,
        annotations={"body": payload.get("body"), "link": payload.get("link")},
        description=payload.get("body") or payload.get("text") or title,
        timestamp=_parse_ts(payload.get("date") or payload.get("last_updated")),
    ).with_correlation()]


def parse_pagerduty(payload: dict) -> list[NormalizedAlert]:
    """PagerDuty v2 webhook (incident.triggered / incident.resolved)."""
    messages = payload.get("messages") or [payload]
    out: list[NormalizedAlert] = []
    for msg in messages[:_PAGE]:
        event = (msg.get("event") or msg.get("event_type") or "").lower()
        incident = msg.get("incident") or msg.get("data") or msg
        if not incident:
            continue
        status = "RESOLVED" if "resolve" in event else "FIRING"
        urgency = (incident.get("urgency") or "high").lower()
        severity = "CRITICAL" if urgency == "high" else "WARNING"
        title = incident.get("title") or incident.get("summary") or "pagerduty-incident"
        service = (incident.get("service") or {}).get("summary") or incident.get("service")
        out.append(NormalizedAlert(
            provider="PAGERDUTY",
            alert_id=str(incident.get("id") or incident.get("incident_number") or title),
            alert_name=title,
            severity=severity,
            status=status,
            service=service,
            environment=incident.get("urgency"),
            resource=service,
            labels={"event": event, "status": incident.get("status")},
            annotations={"html_url": incident.get("html_url")},
            description=incident.get("description") or title,
            timestamp=_parse_ts(incident.get("created_at") or incident.get("last_status_change_at")),
        ).with_correlation())
    return out


INGEST_PARSERS = {
    "ALERTMANAGER": parse_alertmanager,
    "PROMETHEUS": parse_alertmanager,
    "AWS": parse_cloudwatch,
    "CLOUDWATCH": parse_cloudwatch,
    "AZURE": parse_azure_monitor,
    "GITHUB": parse_github,
    "GITLAB": parse_gitlab,
    "JENKINS": parse_jenkins,
    "DATADOG": parse_datadog,
    "PAGERDUTY": parse_pagerduty,
}


def parse_webhook(provider: str, payload: dict) -> list[NormalizedAlert]:
    parser = INGEST_PARSERS.get((provider or "").upper())
    if parser is None:
        raise IngestError(f"No webhook parser for provider '{provider}'.")
    try:
        return parser(payload or {})
    except IngestError:
        raise
    except Exception as exc:  # noqa: BLE001 - malformed payload
        raise IngestError(f"Could not parse {provider} webhook payload.") from exc
