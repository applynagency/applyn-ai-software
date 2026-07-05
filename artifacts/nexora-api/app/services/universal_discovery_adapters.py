"""Sprint 58A.2.1 — Universal Discovery adapters (read-only, secret-safe).

One adapter per non-infrastructure provider (GitHub, GitLab, Jira, Slack,
Microsoft Teams). Each takes a decrypted credential ``dict`` (resolved
transiently from the 35A store by the caller) and returns a list of fully
normalized :class:`UniversalResource` objects spanning its discovery domains.

Infrastructure providers (AWS / Azure / Kubernetes) keep using the existing
58A.2 adapters; :func:`run_universal_provider` wraps their ``NormalizedResource``
output into the Universal Resource Model so a single boundary covers every
connected provider — *no integration left behind*.

GUARANTEES (inherited from the 58A.1 HTTP layer that this reuses):
  * READ-ONLY. Only list/get/describe calls are made; nothing is ever created,
    modified or deleted on the customer's systems.
  * SECRET-SAFE. No secret material is placed in any returned field, log line or
    exception message — only customer-safe identity/metadata.
  * BOUNDED. Every remote call uses a connect/read timeout, is retried up to 3x
    with exponential backoff on transient errors only, and result sets are
    paginated/capped so a scan can never run unbounded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.core.logging import get_logger
from app.services.discovery_adapters import (
    DISCOVERY_ADAPTERS,
    NormalizedResource,
    discover_provider,
)

# Reuse the hardened, TLS-verified HTTP + retry layer from integration
# verification (58A.1). These are internal helpers of the same application.
from app.services.integration_verification import (
    _aad_token,
    _basic_auth,
    _Failed,
    _gh_base,
    _gl_base,
    _http_request,
    _Retryable,
    _Timeout,
    _Unauthorized,
    _with_retry,
)

logger = get_logger(__name__)

# Bounds — keep every scan safe and quick.
_PAGE = 50
_MAX_REPOS = 15        # per-repo deep reads (branches/envs/deploys) are capped
_MAX_PROJECTS = 15
_MAX_TEAMS = 15
_MAX_JIRA_PROJECTS = 25


class UniversalAdapterError(Exception):
    """Raised when an adapter cannot complete its primary (auth) read. The
    message is customer-safe — it never contains secret material."""


@dataclass
class UniversalResource:
    """The Universal Resource Model (one normalized discovered object)."""

    provider: str
    domain: str
    resource_type: str
    resource_id: str
    resource_name: str
    display_name: str | None = None
    parent_id: str | None = None
    relationships: list[dict] = field(default_factory=list)
    owner: str | None = None
    region: str | None = None
    account: str | None = None
    environment: str | None = None
    tags: dict = field(default_factory=dict)
    health: str = "UNKNOWN"
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def node_key(provider: str, domain: str, resource_type: str, resource_id: str) -> str:
    """Stable knowledge-graph key for a discovered object."""
    return f"{provider}:{domain}:{resource_type}:{resource_id}"


# --------------------------------------------------------------------------- #
# HTTP convenience wrappers (retry + best-effort)
# --------------------------------------------------------------------------- #
async def _call(method: str, url: str, **kw) -> dict:
    return await _with_retry(lambda: _http_request(method, url, **kw))


async def _safe(method: str, url: str, default, **kw):
    """Best-effort read: returns ``default`` instead of raising on any provider
    error so one missing scope never aborts a whole provider's discovery."""
    try:
        data = await _call(method, url, **kw)
        return data["_json"]
    except (_Unauthorized, _Failed, _Timeout, _Retryable):
        return default
    except Exception as exc:  # noqa: BLE001 - never surface provider internals
        logger.info("universal_discovery_subread_skipped", url_host=url.split("/")[2] if "//" in url else "?",
                    error=type(exc).__name__)
        return default


def _list(value) -> list:
    return value if isinstance(value, list) else []


# =========================================================================== #
# GitHub — Repository Discovery + Deployment Discovery
# =========================================================================== #
async def discover_github(secret: dict) -> list[UniversalResource]:
    base = _gh_base(secret)
    headers = {
        "Authorization": f"Bearer {secret['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        me = await _call("GET", f"{base}/user", headers=headers)
    except _Unauthorized:
        raise UniversalAdapterError("GitHub rejected the supplied token.") from None
    except (_Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach GitHub for discovery.") from None
    login = me["_json"].get("login", "")
    out: list[UniversalResource] = []

    # Organizations
    orgs = _list(await _safe("GET", f"{base}/user/orgs?per_page={_PAGE}", [], headers=headers))
    for o in orgs:
        if not isinstance(o, dict):
            continue
        out.append(UniversalResource(
            provider="GITHUB", domain="REPOSITORY", resource_type="ORGANIZATION",
            resource_id=str(o.get("id") or o.get("login")), resource_name=o.get("login", ""),
            display_name=o.get("login", ""), owner=o.get("login", ""), account=o.get("login", ""),
            metadata={"description": o.get("description")},
        ))

    # Repositories (+ deep deployment reads for the first N)
    repos = _list(await _safe(
        "GET", f"{base}/user/repos?per_page={_PAGE}&sort=updated", [], headers=headers))
    for idx, repo in enumerate(repos):
        if not isinstance(repo, dict):
            continue
        full = repo.get("full_name", "")
        owner_login = (repo.get("owner") or {}).get("login", "")
        repo_id = str(repo.get("id") or full)
        repo_key = node_key("GITHUB", "REPOSITORY", "REPOSITORY", repo_id)
        topics = _list(repo.get("topics"))
        out.append(UniversalResource(
            provider="GITHUB", domain="REPOSITORY", resource_type="REPOSITORY",
            resource_id=repo_id, resource_name=full, display_name=repo.get("name", ""),
            parent_id=owner_login or None, owner=owner_login,
            account=owner_login, status="archived" if repo.get("archived") else "active",
            health="HEALTHY", tags={t: "true" for t in topics},
            created_at=repo.get("created_at"), updated_at=repo.get("pushed_at") or repo.get("updated_at"),
            relationships=([{"target_name": owner_login, "target_type": "ORGANIZATION",
                             "type": "OWNED_BY"}] if owner_login else []),
            metadata={
                "visibility": repo.get("visibility") or ("private" if repo.get("private") else "public"),
                "default_branch": repo.get("default_branch"),
                "language": repo.get("language"), "topics": topics,
                "open_issues": repo.get("open_issues_count"), "forks": repo.get("forks_count"),
            },
        ))

        if idx >= _MAX_REPOS:
            continue

        for br in _list(await _safe("GET", f"{base}/repos/{full}/branches?per_page=20", [], headers=headers)):
            if not isinstance(br, dict):
                continue
            out.append(UniversalResource(
                provider="GITHUB", domain="REPOSITORY", resource_type="BRANCH",
                resource_id=f"{full}@{br.get('name')}", resource_name=br.get("name", ""),
                parent_id=full, owner=owner_login,
                relationships=[{"target_key": repo_key, "type": "BRANCH_OF"}],
                metadata={"protected": br.get("protected", False)},
            ))

        envs = await _safe("GET", f"{base}/repos/{full}/environments", {}, headers=headers)
        for env in _list((envs or {}).get("environments")):
            if not isinstance(env, dict):
                continue
            out.append(UniversalResource(
                provider="GITHUB", domain="DEPLOYMENT", resource_type="ENVIRONMENT",
                resource_id=f"{full}/{env.get('name')}", resource_name=env.get("name", ""),
                parent_id=full, owner=owner_login, environment=env.get("name"),
                relationships=[{"target_key": repo_key, "type": "ENVIRONMENT_OF"}],
            ))

        for wf in _list((await _safe(
                "GET", f"{base}/repos/{full}/actions/workflows?per_page=20", {}, headers=headers)
            ).get("workflows")):
            if not isinstance(wf, dict):
                continue
            out.append(UniversalResource(
                provider="GITHUB", domain="DEPLOYMENT", resource_type="WORKFLOW",
                resource_id=str(wf.get("id") or wf.get("path")), resource_name=wf.get("name", ""),
                parent_id=full, owner=owner_login, status=wf.get("state"),
                relationships=[{"target_key": repo_key, "type": "WORKFLOW_OF"}],
                metadata={"path": wf.get("path")},
            ))

        for run in _list((await _safe(
                "GET", f"{base}/repos/{full}/actions/runs?per_page=10", {}, headers=headers)
            ).get("workflow_runs")):
            if not isinstance(run, dict):
                continue
            concl = run.get("conclusion")
            out.append(UniversalResource(
                provider="GITHUB", domain="DEPLOYMENT", resource_type="WORKFLOW_RUN",
                resource_id=str(run.get("id")), resource_name=run.get("name") or str(run.get("id")),
                parent_id=full, owner=owner_login, status=concl or run.get("status"),
                health="HEALTHY" if concl == "success" else ("DEGRADED" if concl else "UNKNOWN"),
                updated_at=run.get("updated_at"),
                relationships=[{"target_key": repo_key, "type": "RUN_OF"}],
                metadata={"event": run.get("event"), "branch": run.get("head_branch")},
            ))

        for dep in _list(await _safe("GET", f"{base}/repos/{full}/deployments?per_page=10", [],
                                     headers=headers)):
            if not isinstance(dep, dict):
                continue
            out.append(UniversalResource(
                provider="GITHUB", domain="DEPLOYMENT", resource_type="DEPLOYMENT",
                resource_id=str(dep.get("id")), resource_name=f"{full}#{dep.get('id')}",
                parent_id=full, owner=owner_login, environment=dep.get("environment"),
                created_at=dep.get("created_at"), updated_at=dep.get("updated_at"),
                relationships=[{"target_key": repo_key, "type": "DEPLOYS"}],
                metadata={"ref": dep.get("ref"), "task": dep.get("task")},
            ))

        for rel in _list(await _safe("GET", f"{base}/repos/{full}/releases?per_page=10", [],
                                     headers=headers)):
            if not isinstance(rel, dict):
                continue
            out.append(UniversalResource(
                provider="GITHUB", domain="REPOSITORY", resource_type="RELEASE",
                resource_id=str(rel.get("id")), resource_name=rel.get("tag_name") or rel.get("name", ""),
                parent_id=full, owner=owner_login, created_at=rel.get("published_at"),
                relationships=[{"target_key": repo_key, "type": "RELEASE_OF"}],
                metadata={"draft": rel.get("draft"), "prerelease": rel.get("prerelease")},
            ))

    logger.info("universal_discovery_github_done", login_present=bool(login), resources=len(out))
    return out


# =========================================================================== #
# GitLab — Repository Discovery + Deployment Discovery
# =========================================================================== #
async def discover_gitlab(secret: dict) -> list[UniversalResource]:
    base = _gl_base(secret)
    headers = {"Authorization": f"Bearer {secret['token']}"}
    try:
        await _call("GET", f"{base}/api/v4/user", headers=headers)
    except _Unauthorized:
        raise UniversalAdapterError("GitLab rejected the supplied token.") from None
    except (_Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach GitLab for discovery.") from None
    out: list[UniversalResource] = []

    for g in _list(await _safe(
            "GET", f"{base}/api/v4/groups?per_page={_PAGE}&min_access_level=10", [], headers=headers)):
        if not isinstance(g, dict):
            continue
        out.append(UniversalResource(
            provider="GITLAB", domain="REPOSITORY", resource_type="GROUP",
            resource_id=str(g.get("id")), resource_name=g.get("full_path", ""),
            display_name=g.get("name", ""), owner=g.get("full_path", ""),
            metadata={"visibility": g.get("visibility")},
        ))

    projects = _list(await _safe(
        "GET", f"{base}/api/v4/projects?membership=true&per_page={_PAGE}&order_by=last_activity_at",
        [], headers=headers))
    for idx, p in enumerate(projects):
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id"))
        proj_key = node_key("GITLAB", "REPOSITORY", "PROJECT", pid)
        ns = (p.get("namespace") or {}).get("full_path", "")
        out.append(UniversalResource(
            provider="GITLAB", domain="REPOSITORY", resource_type="PROJECT",
            resource_id=pid, resource_name=p.get("path_with_namespace", ""),
            display_name=p.get("name", ""), parent_id=ns or None, owner=ns,
            status="archived" if p.get("archived") else "active", health="HEALTHY",
            created_at=p.get("created_at"), updated_at=p.get("last_activity_at"),
            relationships=([{"target_name": ns, "target_type": "GROUP", "type": "OWNED_BY"}] if ns else []),
            metadata={"visibility": p.get("visibility"), "default_branch": p.get("default_branch"),
                      "container_registry_enabled": p.get("container_registry_enabled")},
        ))
        if idx >= _MAX_PROJECTS:
            continue

        for br in _list(await _safe("GET", f"{base}/api/v4/projects/{pid}/repository/branches?per_page=20",
                                    [], headers=headers)):
            if not isinstance(br, dict):
                continue
            out.append(UniversalResource(
                provider="GITLAB", domain="REPOSITORY", resource_type="BRANCH",
                resource_id=f"{pid}@{br.get('name')}", resource_name=br.get("name", ""),
                parent_id=pid, owner=ns,
                relationships=[{"target_key": proj_key, "type": "BRANCH_OF"}],
                metadata={"protected": br.get("protected", False)},
            ))

        for mr in _list(await _safe(
                "GET", f"{base}/api/v4/projects/{pid}/merge_requests?state=opened&per_page=20",
                [], headers=headers)):
            if not isinstance(mr, dict):
                continue
            out.append(UniversalResource(
                provider="GITLAB", domain="REPOSITORY", resource_type="MERGE_REQUEST",
                resource_id=f"{pid}!{mr.get('iid')}", resource_name=mr.get("title", ""),
                parent_id=pid, owner=(mr.get("author") or {}).get("username"),
                status=mr.get("state"), updated_at=mr.get("updated_at"),
                relationships=[{"target_key": proj_key, "type": "MERGE_REQUEST_OF"}],
            ))

        for env in _list(await _safe("GET", f"{base}/api/v4/projects/{pid}/environments?per_page=20",
                                     [], headers=headers)):
            if not isinstance(env, dict):
                continue
            out.append(UniversalResource(
                provider="GITLAB", domain="DEPLOYMENT", resource_type="ENVIRONMENT",
                resource_id=f"{pid}/env/{env.get('id')}", resource_name=env.get("name", ""),
                parent_id=pid, owner=ns, environment=env.get("name"), status=env.get("state"),
                relationships=[{"target_key": proj_key, "type": "ENVIRONMENT_OF"}],
            ))

        for pipe in _list(await _safe("GET", f"{base}/api/v4/projects/{pid}/pipelines?per_page=10",
                                      [], headers=headers)):
            if not isinstance(pipe, dict):
                continue
            st = pipe.get("status")
            out.append(UniversalResource(
                provider="GITLAB", domain="DEPLOYMENT", resource_type="PIPELINE",
                resource_id=f"{pid}/pipe/{pipe.get('id')}", resource_name=f"pipeline-{pipe.get('id')}",
                parent_id=pid, owner=ns, status=st,
                health="HEALTHY" if st == "success" else ("DEGRADED" if st in ("failed",) else "UNKNOWN"),
                updated_at=pipe.get("updated_at"), metadata={"ref": pipe.get("ref")},
                relationships=[{"target_key": proj_key, "type": "PIPELINE_OF"}],
            ))

        for dep in _list(await _safe("GET", f"{base}/api/v4/projects/{pid}/deployments?per_page=10",
                                     [], headers=headers)):
            if not isinstance(dep, dict):
                continue
            out.append(UniversalResource(
                provider="GITLAB", domain="DEPLOYMENT", resource_type="DEPLOYMENT",
                resource_id=f"{pid}/dep/{dep.get('id')}", resource_name=f"deploy-{dep.get('id')}",
                parent_id=pid, owner=ns, environment=(dep.get("environment") or {}).get("name"),
                status=dep.get("status"), updated_at=dep.get("updated_at"),
                relationships=[{"target_key": proj_key, "type": "DEPLOYS"}],
            ))

    logger.info("universal_discovery_gitlab_done", resources=len(out))
    return out


# =========================================================================== #
# Jira — Business Discovery
# =========================================================================== #
async def discover_jira(secret: dict) -> list[UniversalResource]:
    base = secret["base_url"].rstrip("/")
    auth = _basic_auth(secret["email"], secret["api_token"])
    try:
        await _call("GET", f"{base}/rest/api/3/myself", auth=auth)
    except _Unauthorized:
        raise UniversalAdapterError("Jira rejected the supplied credentials.") from None
    except (_Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach Jira for discovery.") from None
    out: list[UniversalResource] = []

    search = await _safe("GET", f"{base}/rest/api/3/project/search?maxResults={_PAGE}", {}, auth=auth)
    projects = _list((search or {}).get("values"))
    for idx, proj in enumerate(projects):
        if not isinstance(proj, dict):
            continue
        key = proj.get("key", "")
        proj_key = node_key("JIRA", "BUSINESS", "PROJECT", key)
        ptype = (proj.get("projectTypeKey") or "").lower()
        is_incident = ptype in ("service_desk", "servicedesk") or "incident" in (proj.get("name", "").lower())
        out.append(UniversalResource(
            provider="JIRA", domain="BUSINESS",
            resource_type="INCIDENT_PROJECT" if is_incident else "PROJECT",
            resource_id=key, resource_name=proj.get("name", ""), display_name=proj.get("name", ""),
            owner=(proj.get("lead") or {}).get("displayName"),
            metadata={"project_type": proj.get("projectTypeKey"), "style": proj.get("style"),
                      "is_incident_project": is_incident},
        ))
        if idx >= _MAX_JIRA_PROJECTS:
            continue
        for comp in _list(await _safe("GET", f"{base}/rest/api/3/project/{key}/components", [], auth=auth)):
            if not isinstance(comp, dict):
                continue
            out.append(UniversalResource(
                provider="JIRA", domain="BUSINESS", resource_type="COMPONENT",
                resource_id=str(comp.get("id")), resource_name=comp.get("name", ""),
                parent_id=key, owner=(comp.get("lead") or {}).get("displayName"),
                relationships=[{"target_key": proj_key, "type": "COMPONENT_OF"}],
                metadata={"description": comp.get("description")},
            ))
        for ver in _list(await _safe("GET", f"{base}/rest/api/3/project/{key}/versions", [], auth=auth)):
            if not isinstance(ver, dict):
                continue
            out.append(UniversalResource(
                provider="JIRA", domain="BUSINESS", resource_type="VERSION",
                resource_id=str(ver.get("id")), resource_name=ver.get("name", ""),
                parent_id=key, status="released" if ver.get("released") else "unreleased",
                relationships=[{"target_key": proj_key, "type": "VERSION_OF"}],
            ))

    for it in _list(await _safe("GET", f"{base}/rest/api/3/issuetype", [], auth=auth)):
        if not isinstance(it, dict):
            continue
        out.append(UniversalResource(
            provider="JIRA", domain="BUSINESS", resource_type="ISSUE_TYPE",
            resource_id=str(it.get("id")), resource_name=it.get("name", ""),
            metadata={"subtask": it.get("subtask")},
        ))
    for st in _list(await _safe("GET", f"{base}/rest/api/3/status", [], auth=auth)):
        if not isinstance(st, dict):
            continue
        out.append(UniversalResource(
            provider="JIRA", domain="BUSINESS", resource_type="STATUS",
            resource_id=str(st.get("id")), resource_name=st.get("name", ""),
            metadata={"category": (st.get("statusCategory") or {}).get("key")},
        ))
    for pr in _list(await _safe("GET", f"{base}/rest/api/3/priority", [], auth=auth)):
        if not isinstance(pr, dict):
            continue
        out.append(UniversalResource(
            provider="JIRA", domain="BUSINESS", resource_type="PRIORITY",
            resource_id=str(pr.get("id")), resource_name=pr.get("name", ""),
        ))
    boards = await _safe("GET", f"{base}/rest/agile/1.0/board?maxResults={_PAGE}", {}, auth=auth)
    for bd in _list((boards or {}).get("values")):
        if not isinstance(bd, dict):
            continue
        loc = bd.get("location") or {}
        out.append(UniversalResource(
            provider="JIRA", domain="BUSINESS", resource_type="BOARD",
            resource_id=str(bd.get("id")), resource_name=bd.get("name", ""),
            parent_id=loc.get("projectKey"),
            metadata={"board_type": bd.get("type")},
            relationships=([{"target_key": node_key("JIRA", "BUSINESS", "PROJECT", loc["projectKey"]),
                             "type": "BOARD_OF"}] if loc.get("projectKey") else []),
        ))

    logger.info("universal_discovery_jira_done", resources=len(out))
    return out


# =========================================================================== #
# Slack — Collaboration Discovery
# =========================================================================== #
async def _slack_get(token: str, method_path: str, params: dict) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    data = await _call("GET", f"https://slack.com/api/{method_path}", headers=headers, params=params)
    body = data["_json"]
    if not body.get("ok"):
        err = body.get("error", "")
        if err in {"invalid_auth", "not_authed", "account_inactive", "token_revoked", "token_expired"}:
            raise _Unauthorized()
        raise _Failed()
    return body


async def discover_slack(secret: dict) -> list[UniversalResource]:
    token = secret["bot_token"]
    headers = {"Authorization": f"Bearer {token}"}
    try:
        auth = (await _call("POST", "https://slack.com/api/auth.test", headers=headers))["_json"]
    except (_Unauthorized, _Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach Slack for discovery.") from None
    if not auth.get("ok"):
        raise UniversalAdapterError("Slack rejected the supplied token.")
    team = auth.get("team", "")
    team_id = auth.get("team_id", "")
    out: list[UniversalResource] = [UniversalResource(
        provider="SLACK", domain="COLLABORATION", resource_type="WORKSPACE",
        resource_id=team_id or team, resource_name=team, display_name=team, account=team_id,
        metadata={"url": auth.get("url"), "bot_id": auth.get("bot_id"), "bot_user": auth.get("user")},
    )]
    ws_key = node_key("SLACK", "COLLABORATION", "WORKSPACE", team_id or team)

    async def _slack_safe(method_path, params):
        try:
            return await _slack_get(token, method_path, params)
        except (_Unauthorized, _Failed, _Timeout, _Retryable):
            return {}

    chans = await _slack_safe("conversations.list",
                              {"types": "public_channel,private_channel", "limit": _PAGE,
                               "exclude_archived": "true"})
    for ch in _list(chans.get("channels")):
        if not isinstance(ch, dict):
            continue
        name = ch.get("name", "")
        is_incident = any(t in name.lower() for t in ("incident", "inc-", "outage", "sev"))
        out.append(UniversalResource(
            provider="SLACK", domain="COLLABORATION",
            resource_type="INCIDENT_CHANNEL" if is_incident else "CHANNEL",
            resource_id=ch.get("id", ""), resource_name=name, display_name=name, parent_id=team_id,
            status="private" if ch.get("is_private") else "public",
            relationships=[{"target_key": ws_key, "type": "CHANNEL_OF"}],
            metadata={"is_private": ch.get("is_private"), "members": ch.get("num_members"),
                      "is_incident_channel": is_incident, "topic": (ch.get("topic") or {}).get("value")},
        ))

    members = await _slack_safe("users.list", {"limit": _PAGE})
    for m in _list(members.get("members"))[:_PAGE]:
        if not isinstance(m, dict) or m.get("deleted"):
            continue
        out.append(UniversalResource(
            provider="SLACK", domain="COLLABORATION",
            resource_type="BOT" if m.get("is_bot") else "MEMBER",
            resource_id=m.get("id", ""), resource_name=m.get("name", ""),
            display_name=(m.get("profile") or {}).get("real_name") or m.get("name", ""),
            parent_id=team_id, owner=(m.get("profile") or {}).get("email"),
            relationships=[{"target_key": ws_key, "type": "MEMBER_OF"}],
            metadata={"is_admin": m.get("is_admin"), "is_bot": m.get("is_bot")},
        ))

    groups = await _slack_safe("usergroups.list", {})
    for ug in _list(groups.get("usergroups")):
        if not isinstance(ug, dict):
            continue
        out.append(UniversalResource(
            provider="SLACK", domain="COLLABORATION", resource_type="USER_GROUP",
            resource_id=ug.get("id", ""), resource_name=ug.get("handle") or ug.get("name", ""),
            display_name=ug.get("name", ""), parent_id=team_id,
            relationships=[{"target_key": ws_key, "type": "GROUP_OF"}],
            metadata={"user_count": ug.get("user_count")},
        ))

    logger.info("universal_discovery_slack_done", resources=len(out))
    return out


# =========================================================================== #
# Microsoft Teams — Collaboration Discovery (Microsoft Graph, app credentials)
# =========================================================================== #
async def discover_teams(secret: dict) -> list[UniversalResource]:
    tenant_id = secret["tenant_id"]
    try:
        token = await _aad_token(tenant_id, secret["client_id"], secret["client_secret"],
                                 "https://graph.microsoft.com/.default")
    except _Unauthorized:
        raise UniversalAdapterError("Microsoft rejected the Teams app credentials.") from None
    except (_Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach Microsoft Graph for discovery.") from None
    headers = {"Authorization": f"Bearer {token}"}
    out: list[UniversalResource] = []

    org = await _safe("GET", "https://graph.microsoft.com/v1.0/organization", {}, headers=headers)
    org_name = ""
    org_values = _list((org or {}).get("value"))
    if org_values:
        org_name = org_values[0].get("displayName", "")
    out.append(UniversalResource(
        provider="MICROSOFT_TEAMS", domain="COLLABORATION", resource_type="TENANT",
        resource_id=tenant_id, resource_name=org_name or tenant_id, display_name=org_name,
        account=tenant_id, metadata={"application": secret["client_id"]},
    ))
    tenant_key = node_key("MICROSOFT_TEAMS", "COLLABORATION", "TENANT", tenant_id)

    teams = await _safe("GET", f"https://graph.microsoft.com/v1.0/teams?$top={_PAGE}", {}, headers=headers)
    for idx, team in enumerate(_list((teams or {}).get("value"))):
        if not isinstance(team, dict):
            continue
        tid = team.get("id", "")
        name = team.get("displayName", "")
        team_key = node_key("MICROSOFT_TEAMS", "COLLABORATION", "TEAM", tid)
        is_incident = any(t in name.lower() for t in ("incident", "outage", "sev", "response"))
        out.append(UniversalResource(
            provider="MICROSOFT_TEAMS", domain="COLLABORATION",
            resource_type="INCIDENT_TEAM" if is_incident else "TEAM",
            resource_id=tid, resource_name=name, display_name=name, parent_id=tenant_id,
            relationships=[{"target_key": tenant_key, "type": "TEAM_OF"}],
            metadata={"description": team.get("description"), "is_incident_team": is_incident},
        ))
        if idx >= _MAX_TEAMS:
            continue
        for ch in _list((await _safe(
                "GET", f"https://graph.microsoft.com/v1.0/teams/{tid}/channels", {}, headers=headers)
            ).get("value")):
            if not isinstance(ch, dict):
                continue
            out.append(UniversalResource(
                provider="MICROSOFT_TEAMS", domain="COLLABORATION", resource_type="CHANNEL",
                resource_id=ch.get("id", ""), resource_name=ch.get("displayName", ""),
                parent_id=tid, relationships=[{"target_key": team_key, "type": "CHANNEL_OF"}],
                metadata={"membership_type": ch.get("membershipType")},
            ))
        for app in _list((await _safe(
                "GET", f"https://graph.microsoft.com/v1.0/teams/{tid}/installedApps?"
                       "$expand=teamsAppDefinition", {}, headers=headers)
            ).get("value")):
            if not isinstance(app, dict):
                continue
            defn = app.get("teamsAppDefinition") or {}
            out.append(UniversalResource(
                provider="MICROSOFT_TEAMS", domain="COLLABORATION", resource_type="APP",
                resource_id=app.get("id", ""), resource_name=defn.get("displayName", "app"),
                parent_id=tid, relationships=[{"target_key": team_key, "type": "APP_OF"}],
            ))

    logger.info("universal_discovery_teams_done", resources=len(out))
    return out


# =========================================================================== #
# Infrastructure providers — wrap existing 58A.2 NormalizedResource output
# =========================================================================== #
def _infra_to_universal(normalized: list[NormalizedResource]) -> list[UniversalResource]:
    out: list[UniversalResource] = []
    for r in normalized:
        rels: list[dict] = []
        for rel in r.relationships or []:
            target = rel.get("target_name")
            if target:
                rels.append({"target_name": target, "type": rel.get("type") or "DEPENDS_ON"})
        out.append(UniversalResource(
            provider=r.provider, domain="INFRASTRUCTURE", resource_type=r.resource_type,
            resource_id=r.resource_id, resource_name=r.resource_name,
            display_name=r.service_name or r.resource_name, owner=r.owner,
            region=r.region, account=r.account, environment=r.environment,
            tags=r.tags or {}, health=r.health, relationships=rels,
            created_at=r.created_at, updated_at=r.updated_at,
            metadata={**(r.metadata or {}), "service_name": r.service_name},
        ))
    return out


# =========================================================================== #
# Jenkins — CI/CD job discovery
# =========================================================================== #
async def discover_jenkins(secret: dict) -> list[UniversalResource]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json
    from app.delivery.pipelines.jenkins_live import _flatten_jobs

    endpoint = (secret.get("endpoint") or "").rstrip("/")
    user = secret.get("username")
    token = secret.get("api_token")
    if not endpoint or not user or not token:
        return []
    url = f"{endpoint}/api/json?tree=jobs[name,fullName,color,_class,jobs[name,fullName,color,_class]]"
    try:
        data = await asyncio.to_thread(get_json, url, auth=(user, token))
    except Exception as exc:  # noqa: BLE001
        logger.info("universal_discovery_jenkins_failed", error=type(exc).__name__)
        raise UniversalAdapterError("Could not reach Jenkins for discovery.") from None
    out: list[UniversalResource] = []
    for full_name, job in _flatten_jobs(data.get("jobs", []))[:_MAX_REPOS]:
        color = (job.get("color") or "").replace("_anime", "")
        health = "HEALTHY" if color in ("blue", "yellow") else "DEGRADED" if color == "red" else "UNKNOWN"
        out.append(UniversalResource(
            provider="JENKINS", domain="CI_CD", resource_type="JOB",
            resource_id=full_name, resource_name=full_name.split("/")[-1],
            display_name=full_name, health=health, status=color or None,
            metadata={"url": job.get("url")},
        ))
    logger.info("universal_discovery_jenkins_done", resources=len(out))
    return out


# =========================================================================== #
# CircleCI — project discovery
# =========================================================================== #
async def discover_circleci(secret: dict) -> list[UniversalResource]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    token = secret.get("api_token")
    if not token:
        return []
    headers = {"Circle-Token": token}
    try:
        collabs = await asyncio.to_thread(
            get_json, "https://circleci.com/api/v2/me/collaborations", headers=headers,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("universal_discovery_circleci_failed", error=type(exc).__name__)
        raise UniversalAdapterError("Could not reach CircleCI for discovery.") from None
    out: list[UniversalResource] = []
    items = collabs if isinstance(collabs, list) else collabs.get("items", [])
    for collab in (items or [])[:_MAX_PROJECTS]:
        if not isinstance(collab, dict):
            continue
        slug = collab.get("vcs_url") or collab.get("slug") or collab.get("name") or ""
        out.append(UniversalResource(
            provider="CIRCLECI", domain="CI_CD", resource_type="PROJECT",
            resource_id=slug or str(collab.get("id", "")), resource_name=slug.split("/")[-1] if slug else "project",
            display_name=slug or "project", metadata={"org": collab.get("organization_name")},
        ))
    logger.info("universal_discovery_circleci_done", resources=len(out))
    return out


# =========================================================================== #
# Azure DevOps — project & pipeline discovery
# =========================================================================== #
async def discover_azure_devops(secret: dict) -> list[UniversalResource]:
    import asyncio
    import base64

    from app.delivery.pipelines.ci_http import get_json

    org = secret.get("organization")
    pat = secret.get("pat")
    if not org or not pat:
        return []
    raw = base64.b64encode(f":{pat}".encode()).decode()
    headers = {"Authorization": f"Basic {raw}"}
    base = f"https://dev.azure.com/{org}"
    try:
        projects = await asyncio.to_thread(
            get_json, f"{base}/_apis/projects?api-version=7.0", headers=headers,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("universal_discovery_azure_devops_failed", error=type(exc).__name__)
        raise UniversalAdapterError("Could not reach Azure DevOps for discovery.") from None
    out: list[UniversalResource] = []
    for proj in (projects.get("value") or [])[:_MAX_PROJECTS]:
        if not isinstance(proj, dict):
            continue
        pname = proj.get("name") or ""
        pid = str(proj.get("id") or pname)
        out.append(UniversalResource(
            provider="AZURE_DEVOPS", domain="CI_CD", resource_type="PROJECT",
            resource_id=pid, resource_name=pname, display_name=pname,
            metadata={"state": proj.get("state")},
        ))
        try:
            pl_data = await asyncio.to_thread(
                get_json, f"{base}/{pname}/_apis/pipelines?api-version=7.0", headers=headers,
            )
            for pl in (pl_data.get("value") or [])[:25]:
                if not isinstance(pl, dict):
                    continue
                out.append(UniversalResource(
                    provider="AZURE_DEVOPS", domain="CI_CD", resource_type="PIPELINE",
                    resource_id=f"{pname}:{pl.get('id')}", resource_name=pl.get("name") or str(pl.get("id")),
                    display_name=pl.get("name"), parent_id=pid,
                    relationships=[{"target_key": f"AZURE_DEVOPS:CI_CD:PROJECT:{pid}", "type": "PIPELINE_OF"}],
                ))
        except Exception:  # noqa: BLE001
            continue
    logger.info("universal_discovery_azure_devops_done", resources=len(out))
    return out


# =========================================================================== #
# Argo CD — GitOps application discovery
# =========================================================================== #
async def discover_argocd(secret: dict) -> list[UniversalResource]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    try:
        data = await _call("GET", f"{endpoint}/api/v1/applications", headers=headers)
    except _Unauthorized:
        raise UniversalAdapterError("Argo CD rejected the supplied token.") from None
    except (_Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach Argo CD for discovery.") from None
    out: list[UniversalResource] = []
    for app in _list(data["_json"].get("items"))[:_MAX_PROJECTS]:
        if not isinstance(app, dict):
            continue
        meta = app.get("metadata") or {}
        status = app.get("status") or {}
        health = (status.get("health") or {}).get("status", "UNKNOWN")
        sync = (status.get("sync") or {}).get("status")
        out.append(UniversalResource(
            provider="ARGOCD", domain="GITOPS", resource_type="APPLICATION",
            resource_id=meta.get("name", ""), resource_name=meta.get("name", ""),
            display_name=meta.get("name"), health=health, status=sync,
            metadata={"namespace": meta.get("namespace"), "project": (app.get("spec") or {}).get("project")},
        ))
    logger.info("universal_discovery_argocd_done", resources=len(out))
    return out


# =========================================================================== #
# Terraform Cloud — workspace discovery
# =========================================================================== #
async def discover_terraform(secret: dict) -> list[UniversalResource]:
    org = secret.get("organization")
    token = secret.get("token")
    if not org or not token:
        return []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/vnd.api+json"}
    try:
        data = await _call(
            "GET",
            f"https://app.terraform.io/api/v2/organizations/{org}/workspaces?page[size]=50",
            headers=headers,
        )
    except _Unauthorized:
        raise UniversalAdapterError("Terraform Cloud rejected the supplied token.") from None
    except (_Failed, _Timeout, _Retryable):
        raise UniversalAdapterError("Could not reach Terraform Cloud for discovery.") from None
    out: list[UniversalResource] = []
    for ws in _list(data["_json"].get("data"))[:_MAX_PROJECTS]:
        if not isinstance(ws, dict):
            continue
        attrs = ws.get("attributes") or {}
        out.append(UniversalResource(
            provider="TERRAFORM", domain="IAC", resource_type="WORKSPACE",
            resource_id=ws.get("id", attrs.get("name", "")), resource_name=attrs.get("name", ""),
            display_name=attrs.get("name"), status=attrs.get("locked") and "LOCKED" or "READY",
            metadata={"terraform_version": attrs.get("terraform-version"), "vcs_repo": (attrs.get("vcs-repo") or {}).get("identifier")},
        ))
    logger.info("universal_discovery_terraform_done", resources=len(out))
    return out


# =========================================================================== #
# Bitbucket — repository discovery
# =========================================================================== #
async def discover_bitbucket(secret: dict) -> list[UniversalResource]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    user = secret.get("username")
    pwd = secret.get("app_password")
    if not user or not pwd:
        return []
    auth = (user, pwd)
    try:
        me = await asyncio.to_thread(get_json, "https://api.bitbucket.org/2.0/user", auth=auth)
    except Exception as exc:  # noqa: BLE001
        logger.info("universal_discovery_bitbucket_failed", error=type(exc).__name__)
        raise UniversalAdapterError("Could not reach Bitbucket for discovery.") from None
    out: list[UniversalResource] = []
    repos = await asyncio.to_thread(
        get_json, "https://api.bitbucket.org/2.0/repositories?pagelen=50&role=member", auth=auth,
    )
    for repo in (repos.get("values") or [])[:_MAX_REPOS]:
        if not isinstance(repo, dict):
            continue
        full = repo.get("full_name") or ""
        out.append(UniversalResource(
            provider="BITBUCKET", domain="REPOSITORY", resource_type="REPOSITORY",
            resource_id=str(repo.get("uuid") or full), resource_name=repo.get("name") or full,
            display_name=full, owner=(repo.get("owner") or {}).get("display_name"),
            metadata={"language": repo.get("language"), "private": repo.get("is_private")},
        ))
    logger.info("universal_discovery_bitbucket_done", user=me.get("username"), resources=len(out))
    return out


# =========================================================================== #
# Grafana — dashboard discovery
# =========================================================================== #
async def discover_grafana(secret: dict) -> list[UniversalResource]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    data = await _safe("GET", f"{endpoint}/api/search?type=dash-db&limit={_PAGE}", [], headers=headers)
    out: list[UniversalResource] = []
    for dash in _list(data)[:_PAGE]:
        if not isinstance(dash, dict):
            continue
        out.append(UniversalResource(
            provider="GRAFANA", domain="OBSERVABILITY", resource_type="DASHBOARD",
            resource_id=str(dash.get("uid") or dash.get("id")), resource_name=dash.get("title") or "",
            display_name=dash.get("title"), metadata={"url": dash.get("url"), "type": dash.get("type")},
        ))
    logger.info("universal_discovery_grafana_done", resources=len(out))
    return out


# =========================================================================== #
# Datadog — monitor discovery
# =========================================================================== #
async def discover_datadog(secret: dict) -> list[UniversalResource]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    site = (secret.get("site") or "https://api.datadoghq.com").rstrip("/")
    if not site.startswith("http"):
        site = f"https://api.{site.strip('.')}"
    headers = {"DD-API-KEY": secret.get("api_key", ""), "DD-APPLICATION-KEY": secret.get("app_key", "")}
    try:
        monitors = await asyncio.to_thread(get_json, f"{site}/api/v1/monitor", headers=headers)
    except Exception as exc:  # noqa: BLE001
        raise UniversalAdapterError("Could not reach Datadog for discovery.") from None
    out: list[UniversalResource] = []
    for mon in (monitors if isinstance(monitors, list) else [])[:_PAGE]:
        if not isinstance(mon, dict):
            continue
        out.append(UniversalResource(
            provider="DATADOG", domain="OBSERVABILITY", resource_type="MONITOR",
            resource_id=str(mon.get("id")), resource_name=mon.get("name") or str(mon.get("id")),
            display_name=mon.get("name"), status=mon.get("overall_state"),
            metadata={"type": mon.get("type")},
        ))
    return out


# =========================================================================== #
# New Relic — entity discovery (NerdGraph)
# =========================================================================== #
async def discover_newrelic(secret: dict) -> list[UniversalResource]:
    api_key = secret.get("api_key")
    if not api_key:
        return []
    query = {"query": "{ actor { entitySearch(query: \"type IN ('APPLICATION','HOST')\") { results { entities { guid name entityType } } } } }"}
    data = await _call(
        "POST", "https://api.newrelic.com/graphql",
        headers={"API-Key": api_key, "Content-Type": "application/json"},
        json_body=query,
    )
    entities = (
        (((data["_json"].get("data") or {}).get("actor") or {}).get("entitySearch") or {}).get("results") or {}
    ).get("entities") or []
    out: list[UniversalResource] = []
    for ent in _list(entities)[:_PAGE]:
        if not isinstance(ent, dict):
            continue
        out.append(UniversalResource(
            provider="NEW_RELIC", domain="OBSERVABILITY", resource_type=ent.get("entityType") or "ENTITY",
            resource_id=ent.get("guid", ""), resource_name=ent.get("name") or "",
            display_name=ent.get("name"),
        ))
    return out


# =========================================================================== #
# Loki — label discovery
# =========================================================================== #
async def discover_loki(secret: dict) -> list[UniversalResource]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    if not endpoint:
        return []
    labels = await _safe("GET", f"{endpoint}/loki/api/v1/labels", [], headers={})
    out: list[UniversalResource] = []
    for label in _list(labels)[:_PAGE]:
        out.append(UniversalResource(
            provider="LOKI", domain="OBSERVABILITY", resource_type="LOG_LABEL",
            resource_id=str(label), resource_name=str(label), display_name=str(label),
        ))
    return out


# =========================================================================== #
# Elasticsearch — index discovery
# =========================================================================== #
async def discover_elastic(secret: dict) -> list[UniversalResource]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    api_key = secret.get("api_key")
    if not endpoint or not api_key:
        return []
    headers = {"Authorization": f"ApiKey {api_key}"}
    indices = await _safe("GET", f"{endpoint}/_cat/indices?format=json", [], headers=headers)
    out: list[UniversalResource] = []
    for idx in _list(indices)[:_PAGE]:
        if not isinstance(idx, dict):
            continue
        name = idx.get("index") or ""
        health = (idx.get("health") or "unknown").upper()
        out.append(UniversalResource(
            provider="ELASTIC", domain="OBSERVABILITY", resource_type="INDEX",
            resource_id=name, resource_name=name, display_name=name,
            health="HEALTHY" if health == "GREEN" else "DEGRADED",
            metadata={"docs": idx.get("docs.count"), "store": idx.get("store.size")},
        ))
    return out


# =========================================================================== #
# SonarQube — project discovery
# =========================================================================== #
async def discover_sonarqube(secret: dict) -> list[UniversalResource]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []
    auth = (token, "")
    try:
        data = await asyncio.to_thread(
            get_json, f"{endpoint}/api/projects/search?ps={_PAGE}", auth=auth,
        )
    except Exception as exc:  # noqa: BLE001
        raise UniversalAdapterError("Could not reach SonarQube for discovery.") from None
    out: list[UniversalResource] = []
    for proj in (data.get("components") or [])[:_PAGE]:
        if not isinstance(proj, dict):
            continue
        out.append(UniversalResource(
            provider="SONARQUBE", domain="QUALITY", resource_type="PROJECT",
            resource_id=proj.get("key", ""), resource_name=proj.get("name") or proj.get("key", ""),
            display_name=proj.get("name"), metadata={"qualifier": proj.get("qualifier")},
        ))
    return out


# =========================================================================== #
# HashiCorp Vault — secret engine discovery (metadata only)
# =========================================================================== #
async def discover_vault(secret: dict) -> list[UniversalResource]:
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    token = secret.get("token")
    if not endpoint or not token:
        return []
    headers = {"X-Vault-Token": token}
    data = await _safe("GET", f"{endpoint}/v1/sys/mounts", {}, headers=headers)
    out: list[UniversalResource] = []
    for path, mount in (data.items() if isinstance(data, dict) else []):
        if not isinstance(mount, dict) or path == "request_id":
            continue
        clean = path.rstrip("/")
        out.append(UniversalResource(
            provider="HASHICORP_VAULT", domain="SECRETS", resource_type="SECRET_ENGINE",
            resource_id=clean, resource_name=clean, display_name=clean,
            metadata={"type": mount.get("type"), "description": mount.get("description")},
        ))
    return out[:_PAGE]


# =========================================================================== #
# PagerDuty — service discovery
# =========================================================================== #
async def discover_pagerduty(secret: dict) -> list[UniversalResource]:
    api_key = secret.get("api_key")
    if not api_key:
        return []
    headers = {"Authorization": f"Token token={api_key}", "Accept": "application/vnd.pagerduty+json;version=2"}
    data = await _safe("GET", "https://api.pagerduty.com/services?limit=50", {}, headers=headers)
    out: list[UniversalResource] = []
    for svc in _list((data.get("services") if isinstance(data, dict) else data))[:_PAGE]:
        if not isinstance(svc, dict):
            continue
        out.append(UniversalResource(
            provider="PAGERDUTY", domain="INCIDENT", resource_type="SERVICE",
            resource_id=svc.get("id", ""), resource_name=svc.get("name") or "",
            display_name=svc.get("name"), status=svc.get("status"),
        ))
    return out


# =========================================================================== #
# Opsgenie — team/service discovery
# =========================================================================== #
async def discover_opsgenie(secret: dict) -> list[UniversalResource]:
    import asyncio

    from app.delivery.pipelines.ci_http import get_json

    api_key = secret.get("api_key")
    if not api_key:
        return []
    headers = {"Authorization": f"GenieKey {api_key}"}
    try:
        teams = await asyncio.to_thread(get_json, "https://api.opsgenie.com/v2/teams", headers=headers)
    except Exception as exc:  # noqa: BLE001
        raise UniversalAdapterError("Could not reach Opsgenie for discovery.") from None
    out: list[UniversalResource] = []
    for team in (teams.get("data") or [])[:_PAGE]:
        if not isinstance(team, dict):
            continue
        out.append(UniversalResource(
            provider="OPSGENIE", domain="INCIDENT", resource_type="TEAM",
            resource_id=team.get("id", ""), resource_name=team.get("name") or "",
            display_name=team.get("name"),
        ))
    return out


# --------------------------------------------------------------------------- #
# Registry + single discovery boundary
# --------------------------------------------------------------------------- #
UNIVERSAL_ADAPTERS = {
    "GITHUB": discover_github,
    "GITLAB": discover_gitlab,
    "BITBUCKET": discover_bitbucket,
    "JIRA": discover_jira,
    "SLACK": discover_slack,
    "MICROSOFT_TEAMS": discover_teams,
    "JENKINS": discover_jenkins,
    "CIRCLECI": discover_circleci,
    "AZURE_DEVOPS": discover_azure_devops,
    "ARGOCD": discover_argocd,
    "TERRAFORM": discover_terraform,
    "GRAFANA": discover_grafana,
    "DATADOG": discover_datadog,
    "NEW_RELIC": discover_newrelic,
    "LOKI": discover_loki,
    "ELASTIC": discover_elastic,
    "SONARQUBE": discover_sonarqube,
    "HASHICORP_VAULT": discover_vault,
    "PAGERDUTY": discover_pagerduty,
    "OPSGENIE": discover_opsgenie,
}

# Every connected provider's discovery domains (for the dashboard / status panel).
PROVIDER_DOMAINS: dict[str, list[str]] = {
    "AWS": ["INFRASTRUCTURE"],
    "AZURE": ["INFRASTRUCTURE"],
    "GCP": ["INFRASTRUCTURE"],
    "KUBERNETES": ["INFRASTRUCTURE"],
    "GITHUB": ["REPOSITORY", "DEPLOYMENT"],
    "GITLAB": ["REPOSITORY", "DEPLOYMENT"],
    "BITBUCKET": ["REPOSITORY"],
    "JIRA": ["BUSINESS"],
    "SLACK": ["COLLABORATION"],
    "MICROSOFT_TEAMS": ["COLLABORATION"],
    "JENKINS": ["CI_CD"],
    "CIRCLECI": ["CI_CD"],
    "AZURE_DEVOPS": ["CI_CD"],
    "ARGOCD": ["GITOPS"],
    "TERRAFORM": ["IAC"],
    "GRAFANA": ["OBSERVABILITY"],
    "DATADOG": ["OBSERVABILITY"],
    "NEW_RELIC": ["OBSERVABILITY"],
    "LOKI": ["OBSERVABILITY"],
    "ELASTIC": ["OBSERVABILITY"],
    "PROMETHEUS": ["OBSERVABILITY"],
    "SONARQUBE": ["QUALITY"],
    "HASHICORP_VAULT": ["SECRETS"],
    "PAGERDUTY": ["INCIDENT"],
    "OPSGENIE": ["INCIDENT"],
    "CLOUDWATCH": ["OBSERVABILITY"],
    "ALERTMANAGER": ["OBSERVABILITY"],
    "SPLUNK": ["OBSERVABILITY"],
    "SERVICENOW": ["INCIDENT"],
    "OPENTELEMETRY": ["OBSERVABILITY"],
}


def supports_universal_discovery(integration_key: str) -> bool:
    return integration_key in UNIVERSAL_ADAPTERS or integration_key in DISCOVERY_ADAPTERS


def domains_for(integration_key: str) -> list[str]:
    return PROVIDER_DOMAINS.get(integration_key, [])


async def run_universal_provider(integration_key: str, secret: dict) -> list[UniversalResource]:
    """Run read-only discovery for ``integration_key`` across all its domains.

    Infrastructure providers reuse the existing 58A.2 adapters (wrapped into the
    Universal Resource Model); everyone else uses the dedicated adapters above.
    Raises :class:`UniversalAdapterError` (customer-safe) on failure.
    """
    if integration_key in DISCOVERY_ADAPTERS:
        normalized = await discover_provider(integration_key, secret)
        return _infra_to_universal(normalized)
    adapter = UNIVERSAL_ADAPTERS.get(integration_key)
    if adapter is None:
        raise UniversalAdapterError(f"{integration_key} does not support discovery yet.")
    return await adapter(secret)
