"""Sprint 39C — real, read-only tool connectors.

Turns simulated investigation into real infrastructure reads using customer-owned
credentials resolved from the Sprint 35A encrypted store. Every connector here is
strictly read-only and never returns, logs, or stores secret material.

Design rules (all enforced here):
  * Secrets arrive as a transient ``dict`` and are used in-process only.
  * Connectors return customer-safe summaries / details — never tokens, keys,
    passwords, kubeconfigs, or raw exception text that could contain secrets.
  * On any failure they raise ``ConnectorError`` with a generic, safe message.
  * Providers without a real connector (SLACK/JIRA) are handled by the caller's
    simulated executor, so 39B behavior is unchanged.

The actual read-only allow-list per provider/action lives in ``tool_registry`` and
is validated BEFORE a connector is ever called; connectors assume the action is
already known to be read-only.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger

logger = get_logger(__name__)

# Providers that have a real connector in this sprint.
REAL_PROVIDERS = {
    "KUBERNETES",
    "AZURE",
    "AWS",
    "GITHUB",
    "POSTGRESQL",
    "PROMETHEUS",
    "GRAFANA",
    "DATADOG",
}


class ConnectorError(Exception):
    """Raised when a real connector cannot complete a read.

    The message is always customer-safe (no secrets, no raw driver text).
    """


def provider_has_real_connector(provider: str) -> bool:
    return provider in REAL_PROVIDERS


def _safe(provider: str, what: str) -> ConnectorError:
    return ConnectorError(
        f"Could not {what} for {provider} with the provided credentials. "
        "Please check the connection details and the credential's read-only access."
    )


# --------------------------------------------------------------------------- #
# Kubernetes (customer kubeconfig)
# --------------------------------------------------------------------------- #
def _k8s_client(secret: dict):
    import yaml  # PyYAML ships with the kubernetes client
    from kubernetes import client, config

    raw = secret.get("kubeconfig")
    if not raw:
        raise _safe("KUBERNETES", "load kubeconfig")
    try:
        cfg = yaml.safe_load(raw)
        loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
        configuration = client.Configuration()
        loader.load_and_set(configuration)
        api_client = client.ApiClient(configuration)
        current = cfg.get("current-context")
        cluster = ""
        for ctx in cfg.get("contexts", []):
            if ctx.get("name") == current:
                cluster = ctx.get("context", {}).get("cluster", "")
        return client.CoreV1Api(api_client), client.AppsV1Api(api_client), client.NetworkingV1Api(api_client), cluster
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("k8s_config_error", error=type(exc).__name__)
        raise _safe("KUBERNETES", "load kubeconfig") from exc


async def _k8s_verify(secret: dict) -> dict:
    def _run():
        core, _apps, _net, cluster = _k8s_client(secret)
        core.list_namespace(limit=1, _request_timeout=10)
        return cluster

    cluster = await asyncio.to_thread(_run)
    return {"connected": True, "details": {"cluster": cluster or "kubernetes"}}


async def _k8s_execute(action: str, secret: dict, payload: dict) -> str:
    ns = (payload or {}).get("namespace")

    def _run():
        core, apps, net, _cluster = _k8s_client(secret)
        if action == "get_pods":
            items = (core.list_namespaced_pod(ns, limit=50, _request_timeout=15).items
                     if ns else core.list_pod_for_all_namespaces(limit=50, _request_timeout=15).items)
            names = [i.metadata.name for i in items[:10]]
            return f"Retrieved {len(items)} pod(s){f' in {ns}' if ns else ''}. Sample: {', '.join(names) or 'none'}."
        if action == "get_deployments":
            items = (apps.list_namespaced_deployment(ns, limit=50, _request_timeout=15).items
                     if ns else apps.list_deployment_for_all_namespaces(limit=50, _request_timeout=15).items)
            names = [i.metadata.name for i in items[:10]]
            return f"Retrieved {len(items)} deployment(s). Sample: {', '.join(names) or 'none'}."
        if action == "get_services":
            items = (core.list_namespaced_service(ns, limit=50, _request_timeout=15).items
                     if ns else core.list_service_for_all_namespaces(limit=50, _request_timeout=15).items)
            return f"Retrieved {len(items)} service(s)."
        if action == "get_ingress":
            items = (net.list_namespaced_ingress(ns, limit=50, _request_timeout=15).items
                     if ns else net.list_ingress_for_all_namespaces(limit=50, _request_timeout=15).items)
            return f"Retrieved {len(items)} ingress object(s)."
        if action == "get_namespaces":
            items = core.list_namespace(limit=100, _request_timeout=15).items
            names = [i.metadata.name for i in items[:15]]
            return f"Retrieved {len(items)} namespace(s). Sample: {', '.join(names)}."
        if action in ("get_events", "describe_resource"):
            items = (core.list_namespaced_event(ns, limit=50, _request_timeout=15).items
                     if ns else core.list_event_for_all_namespaces(limit=50, _request_timeout=15).items)
            return f"Retrieved {len(items)} event(s){f' in {ns}' if ns else ''}."
        raise _safe("KUBERNETES", f"perform {action}")

    try:
        return await asyncio.to_thread(_run)
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("k8s_exec_error", action=action, error=type(exc).__name__)
        raise _safe("KUBERNETES", f"perform {action}") from exc


# --------------------------------------------------------------------------- #
# Azure (customer service principal)
# --------------------------------------------------------------------------- #
async def _azure_token(secret: dict) -> str:
    from azure.identity import ClientSecretCredential

    def _run():
        cred = ClientSecretCredential(
            tenant_id=secret["tenant_id"],
            client_id=secret["client_id"],
            client_secret=secret["client_secret"],
        )
        return cred.get_token("https://management.azure.com/.default").token

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        logger.warning("azure_auth_error", error=type(exc).__name__)
        raise _safe("AZURE", "authenticate") from exc


async def _azure_get(token: str, url: str) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()


async def _azure_verify(secret: dict) -> dict:
    token = await _azure_token(secret)
    sub = secret["subscription_id"]
    try:
        await _azure_get(token, f"https://management.azure.com/subscriptions/{sub}?api-version=2022-12-01")
    except Exception as exc:  # noqa: BLE001
        raise _safe("AZURE", "reach subscription") from exc
    return {"connected": True, "details": {"subscription_id": sub}}


async def _azure_execute(action: str, secret: dict, payload: dict) -> str:
    token = await _azure_token(secret)
    sub = secret["subscription_id"]
    base = f"https://management.azure.com/subscriptions/{sub}"
    try:
        if action == "list_resource_groups":
            data = await _azure_get(token, f"{base}/resourcegroups?api-version=2021-04-01")
            return f"Found {len(data.get('value', []))} resource group(s)."
        if action == "list_resources":
            data = await _azure_get(token, f"{base}/resources?api-version=2021-04-01&$top=50")
            return f"Found {len(data.get('value', []))} resource(s) (top 50)."
        if action in ("list_container_apps", "list_app_revisions"):
            data = await _azure_get(
                token,
                f"{base}/providers/Microsoft.App/containerApps?api-version=2023-05-01",
            )
            return f"Found {len(data.get('value', []))} container app(s)."
        if action == "read_diagnostics":
            data = await _azure_get(token, f"{base}/resources?api-version=2021-04-01&$top=1")
            return f"Diagnostics reachable; subscription has {len(data.get('value', []))}+ resource(s)."
        raise _safe("AZURE", f"perform {action}")
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("azure_exec_error", action=action, error=type(exc).__name__)
        raise _safe("AZURE", f"perform {action}") from exc


# --------------------------------------------------------------------------- #
# AWS (customer access key / secret key)
# --------------------------------------------------------------------------- #
def _aws_session(secret: dict):
    import boto3

    return boto3.session.Session(
        aws_access_key_id=secret["access_key"],
        aws_secret_access_key=secret["secret_key"],
        region_name=secret.get("region", "us-east-1"),
    )


async def _aws_verify(secret: dict) -> dict:
    def _run():
        sess = _aws_session(secret)
        ident = sess.client("sts").get_caller_identity()
        return ident.get("Account", "")

    try:
        account = await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        logger.warning("aws_auth_error", error=type(exc).__name__)
        raise _safe("AWS", "authenticate") from exc
    return {"connected": True, "details": {"account": account, "region": secret.get("region", "us-east-1")}}


async def _aws_execute(action: str, secret: dict, payload: dict) -> str:
    def _run():
        sess = _aws_session(secret)
        if action in ("describe_ec2", "describe_resources"):
            r = sess.client("ec2").describe_instances(MaxResults=50)
            n = sum(len(res.get("Instances", [])) for res in r.get("Reservations", []))
            return f"Described {n} EC2 instance(s)."
        if action == "describe_ecs":
            r = sess.client("ecs").list_clusters(maxResults=50)
            return f"Found {len(r.get('clusterArns', []))} ECS cluster(s)."
        if action == "describe_eks":
            r = sess.client("eks").list_clusters(maxResults=50)
            return f"Found {len(r.get('clusters', []))} EKS cluster(s)."
        if action == "read_cloudwatch_metrics":
            r = sess.client("cloudwatch").list_metrics()
            return f"Listed {len(r.get('Metrics', []))} CloudWatch metric(s)."
        raise _safe("AWS", f"perform {action}")

    try:
        return await asyncio.to_thread(_run)
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("aws_exec_error", action=action, error=type(exc).__name__)
        raise _safe("AWS", f"perform {action}") from exc


# --------------------------------------------------------------------------- #
# GitHub (customer token)
# --------------------------------------------------------------------------- #
def _gh_headers(secret: dict) -> dict:
    return {
        "Authorization": f"Bearer {secret['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_base(secret: dict) -> str:
    return (secret.get("base_url") or "https://api.github.com").rstrip("/")


async def _gh_verify(secret: dict) -> dict:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.get(f"{_gh_base(secret)}/user", headers=_gh_headers(secret))
            resp.raise_for_status()
            login = resp.json().get("login", "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("github_auth_error", error=type(exc).__name__)
        raise _safe("GITHUB", "authenticate") from exc
    return {"connected": True, "details": {"login": login}}


async def _gh_execute(action: str, secret: dict, payload: dict) -> str:
    import httpx

    owner = (payload or {}).get("owner") or (payload or {}).get("org")
    repo = (payload or {}).get("repo")
    base = _gh_base(secret)
    try:
        async with httpx.AsyncClient(timeout=20, headers=_gh_headers(secret)) as c:
            if action == "list_repositories":
                url = f"{base}/orgs/{owner}/repos?per_page=50" if owner else f"{base}/user/repos?per_page=50"
                data = (await c.get(url)).json()
                return f"Found {len(data)} repository(ies)."
            if action == "list_pull_requests":
                data = (await c.get(f"{base}/repos/{owner}/{repo}/pulls?state=open&per_page=50")).json()
                return f"Found {len(data)} open pull request(s) in {owner}/{repo}."
            if action == "list_workflow_runs":
                data = (await c.get(f"{base}/repos/{owner}/{repo}/actions/runs?per_page=20")).json()
                return f"Found {data.get('total_count', 0)} workflow run(s) in {owner}/{repo}."
            if action == "list_commits":
                data = (await c.get(f"{base}/repos/{owner}/{repo}/commits?per_page=20")).json()
                return f"Retrieved {len(data)} recent commit(s) in {owner}/{repo}."
            if action == "list_releases":
                data = (await c.get(f"{base}/repos/{owner}/{repo}/releases?per_page=20")).json()
                return f"Found {len(data)} release(s) in {owner}/{repo}."
        raise _safe("GITHUB", f"perform {action}")
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("github_exec_error", action=action, error=type(exc).__name__)
        raise _safe("GITHUB", f"perform {action}") from exc


# --------------------------------------------------------------------------- #
# PostgreSQL (customer database connection, SELECT-only)
# --------------------------------------------------------------------------- #
async def _pg_connect(secret: dict):
    import asyncpg

    return await asyncpg.connect(
        host=secret["host"],
        port=int(secret.get("port", 5432) or 5432),
        user=secret["username"],
        password=secret["password"],
        database=secret["database"],
        timeout=15,
    )


async def _pg_verify(secret: dict) -> dict:
    try:
        conn = await _pg_connect(secret)
        try:
            version = await conn.fetchval("SELECT version()")
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("postgres_auth_error", error=type(exc).__name__)
        raise _safe("POSTGRESQL", "connect") from exc
    server = (version or "PostgreSQL").split(" on ")[0]
    return {"connected": True, "details": {"database": secret["database"], "server": server}}


async def _pg_execute(action: str, secret: dict, payload: dict) -> str:
    if action != "select_query":
        raise _safe("POSTGRESQL", f"perform {action}")
    sql = ((payload or {}).get("sql") or (payload or {}).get("query") or "").strip()
    # Read-only is already validated upstream; re-affirm SELECT/WITH here.
    if not (sql.lower().startswith("select") or sql.lower().startswith("with")):
        raise ConnectorError("Only read-only SELECT statements are permitted.")
    try:
        conn = await _pg_connect(secret)
        try:
            rows = await conn.fetch(sql)
        finally:
            await conn.close()
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("postgres_exec_error", error=type(exc).__name__)
        raise ConnectorError(
            "The query could not be executed. Confirm it is a valid read-only "
            "SELECT and the credential has access."
        ) from exc
    cols = list(rows[0].keys()) if rows else []
    return f"Query returned {len(rows)} row(s). Columns: {', '.join(cols) or 'none'}."


# --------------------------------------------------------------------------- #
# Prometheus (customer endpoint)
# --------------------------------------------------------------------------- #
def _prom_auth(secret: dict) -> dict:
    token = secret.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def _prom_verify(secret: dict) -> dict:
    import httpx

    endpoint = secret["endpoint"].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20, headers=_prom_auth(secret)) as c:
            resp = await c.get(f"{endpoint}/api/v1/status/buildinfo")
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("prometheus_auth_error", error=type(exc).__name__)
        raise _safe("PROMETHEUS", "connect") from exc
    return {"connected": True, "details": {"endpoint": endpoint}}


async def _prom_execute(action: str, secret: dict, payload: dict) -> str:
    import httpx

    if action != "query_metrics":
        raise _safe("PROMETHEUS", f"perform {action}")
    endpoint = secret["endpoint"].rstrip("/")
    query = (payload or {}).get("query") or "up"
    try:
        async with httpx.AsyncClient(timeout=20, headers=_prom_auth(secret)) as c:
            resp = await c.get(f"{endpoint}/api/v1/query", params={"query": query})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("prometheus_exec_error", error=type(exc).__name__)
        raise _safe("PROMETHEUS", "query metrics") from exc
    results = data.get("data", {}).get("result", [])
    return f"Prometheus query '{query}' returned {len(results)} series."


# --------------------------------------------------------------------------- #
# Grafana (customer endpoint + token)
# --------------------------------------------------------------------------- #
async def _grafana_verify(secret: dict) -> dict:
    import httpx

    endpoint = secret["endpoint"].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20, headers={"Authorization": f"Bearer {secret['token']}"}) as c:
            resp = await c.get(f"{endpoint}/api/health")
            resp.raise_for_status()
            version = resp.json().get("version", "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("grafana_auth_error", error=type(exc).__name__)
        raise _safe("GRAFANA", "connect") from exc
    return {"connected": True, "details": {"endpoint": endpoint, "version": version}}


async def _grafana_execute(action: str, secret: dict, payload: dict) -> str:
    import httpx

    if action != "query_dashboard":
        raise _safe("GRAFANA", f"perform {action}")
    endpoint = secret["endpoint"].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20, headers={"Authorization": f"Bearer {secret['token']}"}) as c:
            resp = await c.get(f"{endpoint}/api/search", params={"type": "dash-db", "limit": 50})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("grafana_exec_error", error=type(exc).__name__)
        raise _safe("GRAFANA", "query dashboards") from exc
    return f"Found {len(data)} dashboard(s)."


# --------------------------------------------------------------------------- #
# Datadog (customer api key + app key)
# --------------------------------------------------------------------------- #
def _dd_headers(secret: dict) -> dict:
    return {"DD-API-KEY": secret["api_key"], "DD-APPLICATION-KEY": secret["app_key"]}


def _dd_site(secret: dict) -> str:
    return (secret.get("site") or "https://api.datadoghq.com").rstrip("/")


async def _dd_verify(secret: dict) -> dict:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=20, headers=_dd_headers(secret)) as c:
            resp = await c.get(f"{_dd_site(secret)}/api/v1/validate")
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("datadog_auth_error", error=type(exc).__name__)
        raise _safe("DATADOG", "authenticate") from exc
    return {"connected": True, "details": {"site": _dd_site(secret)}}


async def _dd_execute(action: str, secret: dict, payload: dict) -> str:
    import httpx

    site = _dd_site(secret)
    try:
        async with httpx.AsyncClient(timeout=20, headers=_dd_headers(secret)) as c:
            if action == "list_monitors":
                data = (await c.get(f"{site}/api/v1/monitor?page_size=50")).json()
                return f"Found {len(data)} monitor(s)."
            if action == "list_incidents":
                resp = await c.get(f"{site}/api/v2/incidents?page[size]=50")
                resp.raise_for_status()
                return f"Found {len(resp.json().get('data', []))} incident(s)."
            if action == "query_metrics":
                resp = await c.get(f"{site}/api/v1/metrics")
                resp.raise_for_status()
                return f"Listed {len(resp.json().get('metrics', []))} active metric(s)."
        raise _safe("DATADOG", f"perform {action}")
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("datadog_exec_error", action=action, error=type(exc).__name__)
        raise _safe("DATADOG", f"perform {action}") from exc


async def _jenkins_execute(action: str, secret: dict, payload: dict) -> str:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json
    from app.delivery.pipelines.jenkins_live import JenkinsProvider

    endpoint = (secret.get("endpoint") or "").rstrip("/")
    if not endpoint or not secret.get("username") or not secret.get("api_token"):
        raise _safe("JENKINS", "connect — missing endpoint or credentials")
    auth = (secret["username"], secret["api_token"])
    try:
        if action == "list_jobs":
            data = await asyncio.to_thread(
                get_json, f"{endpoint}/api/json?tree=jobs[name,url,color]", auth=auth,
            )
            jobs = data.get("jobs") or []
            return f"Found {len(jobs)} Jenkins job(s)."
        if action == "list_builds":
            job = (payload or {}).get("job") or (payload or {}).get("pipeline")
            if not job and secret.get("job"):
                job = secret["job"]
            if not job:
                data = await asyncio.to_thread(
                    get_json, f"{endpoint}/api/json?tree=jobs[name]", auth=auth,
                )
                jobs = data.get("jobs") or []
                job = jobs[0]["name"] if jobs else None
            if not job:
                return "No Jenkins jobs found."
            provider = JenkinsProvider()
            runs = await asyncio.to_thread(provider.list_runs, secret, job, limit=10)
            failed = sum(1 for r in runs if r.status == "FAILED")
            return f"Job '{job}': {len(runs)} recent build(s), {failed} failed."
        raise _safe("JENKINS", f"perform {action}")
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("jenkins_exec_error", action=action, error=type(exc).__name__)
        raise _safe("JENKINS", f"perform {action}") from exc


async def _jenkins_verify(secret: dict) -> dict:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    endpoint = (secret.get("endpoint") or "").rstrip("/")
    try:
        data = await asyncio.to_thread(
            get_json, f"{endpoint}/api/json?tree=jobs[name]", auth=(secret["username"], secret["api_token"]),
        )
        count = len(data.get("jobs") or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("jenkins_auth_error", error=type(exc).__name__)
        raise _safe("JENKINS", "authenticate") from exc
    return {"connected": True, "details": {"jobs": count}}


_VERIFIERS = {
    "KUBERNETES": _k8s_verify,
    "AZURE": _azure_verify,
    "AWS": _aws_verify,
    "GITHUB": _gh_verify,
    "JENKINS": _jenkins_verify,
    "POSTGRESQL": _pg_verify,
    "PROMETHEUS": _prom_verify,
    "GRAFANA": _grafana_verify,
    "DATADOG": _dd_verify,
}

_EXECUTORS = {
    "KUBERNETES": _k8s_execute,
    "AZURE": _azure_execute,
    "AWS": _aws_execute,
    "GITHUB": _gh_execute,
    "JENKINS": _jenkins_execute,
    "POSTGRESQL": _pg_execute,
    "PROMETHEUS": _prom_execute,
    "GRAFANA": _grafana_execute,
    "DATADOG": _dd_execute,
}


async def verify_connection(provider: str, secret: dict) -> dict:
    """Live read-only connection test. Returns {connected, provider, details}.

    Raises ConnectorError (customer-safe) on failure.
    """
    fn = _VERIFIERS.get(provider)
    if fn is None:
        raise ConnectorError(f"{provider} does not support live verification yet.")
    result = await fn(secret)
    return {"connected": True, "provider": provider, "details": result.get("details", {})}


async def execute_real(provider: str, action: str, secret: dict, payload: dict | None) -> str:
    """Run a real read-only investigation. Returns a customer-safe summary."""
    fn = _EXECUTORS.get(provider)
    if fn is None:
        raise ConnectorError(f"{provider} does not support live execution yet.")
    return await fn(action, secret, payload or {})
