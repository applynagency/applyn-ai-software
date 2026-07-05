"""Sprint 58A.2 — real, read-only discovery provider adapters.

Each adapter takes a decrypted credential ``dict`` (resolved transiently from the
35A encrypted store by the caller) and returns a list of fully-normalized
``NormalizedResource`` objects describing the live infrastructure it can read.

GUARANTEES (enforced here):
  * READ-ONLY. Adapters only list/describe; they never create, modify, scale, or
    delete any cloud/cluster resource.
  * SECRET-SAFE. No secret material is ever placed in a returned field, log line,
    or exception message — only customer-safe identity/metadata.
  * BOUNDED. Every remote call uses a connect/read timeout; sync SDK calls run in
    a worker thread so the event loop is never blocked.

Every normalized resource carries the Sprint 58A.2 required shape:
  provider, account, region, resource_id, resource_type, resource_name, tags,
  relationships, health, owner, created_at, updated_at.

``relationships`` reference targets by their *service name* so the discovery
engine can turn them into Dependency Graph edges (the catalog is keyed by name).
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field

from app.core.logging import get_logger
from app.security.ssrf import SSRFError, safe_http_client

logger = get_logger(__name__)

_TIMEOUT = 15.0  # seconds per remote call
_PAGE = 100      # max items per resource type (keeps scans bounded)

# Providers that can be discovered live in this sprint.
DISCOVERY_PROVIDERS = {"AWS", "AZURE", "GCP", "KUBERNETES"}

# Fine-grained resource types that should become Service Catalog entries.
SERVICE_LIKE_TYPES = {
    "RDS", "ALB", "LAMBDA", "APP_SERVICE", "SQL_DATABASE", "STATEFULSET",
    # plus the legacy discovery taxonomy already treated as service-like
    "DEPLOYMENT", "SERVICE", "DATABASE", "LOAD_BALANCER", "CONTAINER_APP", "ECS", "EKS",
}


class AdapterError(Exception):
    """Raised when an adapter cannot complete a read. Message is customer-safe."""


@dataclass
class NormalizedResource:
    provider: str
    account: str
    region: str
    resource_id: str
    resource_type: str
    resource_name: str
    tags: dict = field(default_factory=dict)
    relationships: list[dict] = field(default_factory=list)
    health: str = "UNKNOWN"
    owner: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # pipeline helpers (not part of the required output but used internally)
    service_name: str | None = None
    environment: str | None = None
    metadata: dict = field(default_factory=dict)

    def fingerprint_fields(self) -> dict:
        """The subset that, when changed, counts as a MODIFIED resource."""
        return {
            "health": self.health, "region": self.region, "account": self.account,
            "owner": self.owner, "tags": self.tags, "updated_at": self.updated_at,
            "service_name": self.service_name, "environment": self.environment,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def _owner_from_tags(tags: dict) -> str | None:
    for k in ("Owner", "owner", "team", "Team", "owner_team"):
        if tags.get(k):
            return str(tags[k])
    return None


def _iso(dt) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except (AttributeError, ValueError):
        return str(dt)


# =========================================================================== #
# AWS — EC2, RDS, ALB, Lambda, VPC, EKS, S3, CloudWatch
# =========================================================================== #
def _aws_collect(secret: dict) -> list[NormalizedResource]:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    region = secret.get("region") or "us-east-1"
    cfg = Config(connect_timeout=_TIMEOUT, read_timeout=_TIMEOUT, retries={"max_attempts": 1})
    session = boto3.session.Session(
        aws_access_key_id=secret["access_key"],
        aws_secret_access_key=secret["secret_key"],
        region_name=region,
    )
    try:
        account = session.client("sts", config=cfg).get_caller_identity().get("Account", "")
    except (ClientError, BotoCoreError) as exc:
        raise AdapterError("Could not authenticate to AWS for discovery.") from exc

    out: list[NormalizedResource] = []

    def _mk(rtype, rid, name, **kw):
        tags = kw.pop("tags", {}) or {}
        out.append(NormalizedResource(
            provider="AWS", account=account, region=region, resource_id=rid,
            resource_type=rtype, resource_name=name or rid, tags=tags,
            owner=_owner_from_tags(tags), **kw,
        ))

    def _tagdict(items):
        return {t.get("Key"): t.get("Value") for t in (items or []) if t.get("Key")}

    # EC2
    try:
        ec2 = session.client("ec2", config=cfg)
        reservations = ec2.describe_instances(MaxResults=_PAGE).get("Reservations", [])
        for res in reservations:
            for inst in res.get("Instances", []):
                tags = _tagdict(inst.get("Tags"))
                state = (inst.get("State") or {}).get("Name", "")
                _mk("EC2", inst.get("InstanceId", ""), tags.get("Name") or inst.get("InstanceId", ""),
                    tags=tags, health="HEALTHY" if state == "running" else "DEGRADED",
                    created_at=_iso(inst.get("LaunchTime")),
                    metadata={"instance_type": inst.get("InstanceType"), "state": state,
                              "vpc_id": inst.get("VpcId")})
        # VPC
        for vpc in ec2.describe_vpcs().get("Vpcs", [])[:_PAGE]:
            tags = _tagdict(vpc.get("Tags"))
            _mk("VPC", vpc.get("VpcId", ""), tags.get("Name") or vpc.get("VpcId", ""), tags=tags,
                health="HEALTHY" if vpc.get("State") == "available" else "DEGRADED",
                metadata={"cidr": vpc.get("CidrBlock"), "is_default": vpc.get("IsDefault")})
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_ec2_skipped", error=type(exc).__name__)

    # RDS (service-like)
    try:
        rds = session.client("rds", config=cfg)
        for db in rds.describe_db_instances(MaxRecords=_PAGE).get("DBInstances", []):
            name = db.get("DBInstanceIdentifier", "")
            _mk("RDS", db.get("DBInstanceArn", name), name, service_name=name,
                health="HEALTHY" if db.get("DBInstanceStatus") == "available" else "DEGRADED",
                created_at=_iso(db.get("InstanceCreateTime")),
                metadata={"engine": db.get("Engine"), "status": db.get("DBInstanceStatus"),
                          "multi_az": db.get("MultiAZ")})
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_rds_skipped", error=type(exc).__name__)

    # ALB / ELBv2 (service-like load balancers)
    try:
        elb = session.client("elbv2", config=cfg)
        for lb in elb.describe_load_balancers(PageSize=_PAGE).get("LoadBalancers", []):
            name = lb.get("LoadBalancerName", "")
            _mk("ALB", lb.get("LoadBalancerArn", name), name, service_name=name,
                health="HEALTHY" if (lb.get("State") or {}).get("Code") == "active" else "DEGRADED",
                created_at=_iso(lb.get("CreatedTime")),
                metadata={"type": lb.get("Type"), "scheme": lb.get("Scheme"), "vpc_id": lb.get("VpcId")},
                relationships=([{"target_name": lb.get("VpcId"), "type": "NETWORK"}]
                               if lb.get("VpcId") else []))
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_alb_skipped", error=type(exc).__name__)

    # Lambda (service-like)
    try:
        lam = session.client("lambda", config=cfg)
        for fn in lam.list_functions(MaxItems=_PAGE).get("Functions", []):
            name = fn.get("FunctionName", "")
            _mk("LAMBDA", fn.get("FunctionArn", name), name, service_name=name, health="HEALTHY",
                updated_at=fn.get("LastModified"),
                metadata={"runtime": fn.get("Runtime"), "memory": fn.get("MemorySize")})
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_lambda_skipped", error=type(exc).__name__)

    # EKS (service-like clusters)
    try:
        eks = session.client("eks", config=cfg)
        for cname in eks.list_clusters(maxResults=_PAGE).get("clusters", []):
            _mk("EKS", cname, cname, service_name=cname, health="HEALTHY")
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_eks_skipped", error=type(exc).__name__)

    # S3
    try:
        s3 = session.client("s3", config=cfg)
        for b in s3.list_buckets().get("Buckets", [])[:_PAGE]:
            _mk("S3", b.get("Name", ""), b.get("Name", ""), health="HEALTHY",
                created_at=_iso(b.get("CreationDate")))
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_s3_skipped", error=type(exc).__name__)

    # CloudWatch (alarms as monitoring resources)
    try:
        cw = session.client("cloudwatch", config=cfg)
        for al in cw.describe_alarms(MaxRecords=_PAGE).get("MetricAlarms", []):
            state = al.get("StateValue", "")
            _mk("CLOUDWATCH", al.get("AlarmArn", al.get("AlarmName", "")), al.get("AlarmName", ""),
                health="DEGRADED" if state == "ALARM" else "HEALTHY",
                metadata={"state": state, "metric": al.get("MetricName")})
    except (ClientError, BotoCoreError) as exc:
        logger.info("aws_discovery_cloudwatch_skipped", error=type(exc).__name__)

    return out


async def discover_aws(secret: dict) -> list[NormalizedResource]:
    return await asyncio.to_thread(_aws_collect, secret)


# =========================================================================== #
# Azure — VM, App Service, AKS, SQL, Storage, Load Balancer
# =========================================================================== #
async def _aad_token(secret: dict) -> str:
    import httpx

    tenant = secret["tenant_id"]
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    try:
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.post(url, data={
                "grant_type": "client_credentials",
                "client_id": secret["client_id"],
                "client_secret": secret["client_secret"],
                "scope": "https://management.azure.com/.default",
            })
    except SSRFError as exc:
        raise AdapterError("Blocked request to a disallowed address during discovery.") from exc
    except httpx.HTTPError as exc:
        raise AdapterError("Could not reach Azure AD for discovery.") from exc
    if resp.status_code >= 400:
        raise AdapterError("Could not authenticate to Azure for discovery.")
    token = resp.json().get("access_token")
    if not token:
        raise AdapterError("Azure did not return an access token.")
    return token


async def _arm_list(token: str, sub: str, path: str, api_version: str) -> list[dict]:
    import httpx

    url = f"https://management.azure.com/subscriptions/{sub}{path}"
    params = {"api-version": api_version}
    try:
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as c:
            resp = await c.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
    except SSRFError as exc:
        raise AdapterError("Blocked request to a disallowed address during discovery.") from exc
    except httpx.HTTPError as exc:
        raise AdapterError("Could not reach the Azure management API.") from exc
    if resp.status_code in (401, 403):
        raise AdapterError("Azure denied access to a resource type during discovery.")
    if resp.status_code >= 400:
        return []
    return (resp.json().get("value") or [])[:_PAGE]


_AZURE_KINDS = [
    ("/providers/Microsoft.Compute/virtualMachines", "2023-03-01", "VM", False),
    ("/providers/Microsoft.Web/sites", "2022-03-01", "APP_SERVICE", True),
    ("/providers/Microsoft.ContainerService/managedClusters", "2023-05-01", "AKS", False),
    ("/providers/Microsoft.Sql/servers", "2021-11-01", "SQL_DATABASE", True),
    ("/providers/Microsoft.Storage/storageAccounts", "2023-01-01", "STORAGE", False),
    ("/providers/Microsoft.Network/loadBalancers", "2023-05-01", "LOAD_BALANCER", True),
]


async def discover_azure(secret: dict) -> list[NormalizedResource]:
    token = await _aad_token(secret)
    sub = secret["subscription_id"]
    out: list[NormalizedResource] = []
    for path, api_version, rtype, service_like in _AZURE_KINDS:
        for item in await _arm_list(token, sub, path, api_version):
            tags = item.get("tags") or {}
            name = item.get("name", "")
            loc = item.get("location", "")
            props = item.get("properties") or {}
            state = props.get("provisioningState", "")
            out.append(NormalizedResource(
                provider="AZURE", account=sub, region=loc, resource_id=item.get("id", name),
                resource_type=rtype, resource_name=name, tags=tags, owner=_owner_from_tags(tags),
                service_name=name if service_like else None,
                health="HEALTHY" if state in ("Succeeded", "") else "DEGRADED",
                metadata={"provisioning_state": state, "kind": item.get("kind")},
            ))
    return out


# =========================================================================== #
# Kubernetes — Namespaces, Pods, Deployments, DaemonSets, StatefulSets,
# Services, Ingress, ConfigMaps, Secrets (metadata only)
# =========================================================================== #
def _k8s_collect(secret: dict) -> list[NormalizedResource]:
    import yaml
    from kubernetes import client, config
    from kubernetes.client.exceptions import ApiException

    raw = secret.get("kubeconfig")
    if not raw:
        raise AdapterError("No kubeconfig supplied for Kubernetes discovery.")
    try:
        cfg = yaml.safe_load(raw)
        loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
        configuration = client.Configuration()
        loader.load_and_set(configuration)
        api = client.ApiClient(configuration)
    except Exception as exc:  # noqa: BLE001 - malformed kubeconfig
        raise AdapterError("Could not load the supplied kubeconfig.") from exc

    cluster = ""
    current = cfg.get("current-context")
    for ctx in cfg.get("contexts", []):
        if ctx.get("name") == current:
            cluster = ctx.get("context", {}).get("cluster", "")
    cluster = cluster or "kubernetes"
    core = client.CoreV1Api(api)
    apps = client.AppsV1Api(api)
    net = client.NetworkingV1Api(api)
    out: list[NormalizedResource] = []

    def _mk(rtype, rid, name, *, ns=None, health="HEALTHY", created=None, rels=None, meta=None):
        out.append(NormalizedResource(
            provider="KUBERNETES", account=cluster, region=ns or "cluster",
            resource_id=rid, resource_type=rtype, resource_name=name,
            service_name=name if rtype in ("SERVICE", "DEPLOYMENT", "STATEFULSET") else None,
            environment=ns, health=health, created_at=created, relationships=rels or [],
            metadata=meta or {},
        ))

    try:
        for ns in core.list_namespace(limit=_PAGE, _request_timeout=_TIMEOUT).items:
            m = ns.metadata
            _mk("NAMESPACE", m.uid, m.name, ns=m.name, created=_iso(m.creation_timestamp),
                health="HEALTHY" if (ns.status and ns.status.phase == "Active") else "DEGRADED")
    except ApiException as exc:
        raise AdapterError("Kubernetes denied namespace listing.") from exc
    except Exception as exc:  # noqa: BLE001 - transport
        raise AdapterError("Could not reach the Kubernetes API server.") from exc

    def _safe(fn, label):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - per-type best effort
            logger.info("k8s_discovery_skipped", kind=label, error=type(exc).__name__)
            return []

    for d in _safe(lambda: apps.list_deployment_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                   "deployment"):
        m = d.metadata
        ready = (d.status.ready_replicas or 0) if d.status else 0
        desired = (d.spec.replicas or 0) if d.spec else 0
        _mk("DEPLOYMENT", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp),
            health="HEALTHY" if ready >= desired and desired > 0 else "DEGRADED",
            meta={"ready": ready, "desired": desired})

    for s in _safe(lambda: apps.list_stateful_set_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                   "statefulset"):
        m = s.metadata
        _mk("STATEFULSET", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp))

    for ds in _safe(lambda: apps.list_daemon_set_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                    "daemonset"):
        m = ds.metadata
        _mk("DAEMONSET", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp))

    for svc in _safe(lambda: core.list_service_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                     "service"):
        m = svc.metadata
        sel = (svc.spec.selector if svc.spec else None) or {}
        rels = [{"target_name": v, "type": "NETWORK"} for v in sel.values()][:5]
        _mk("SERVICE", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp),
            rels=rels, meta={"type": svc.spec.type if svc.spec else None})

    for pod in _safe(lambda: core.list_pod_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                     "pod"):
        m = pod.metadata
        phase = pod.status.phase if pod.status else ""
        _mk("POD", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp),
            health="HEALTHY" if phase == "Running" else "DEGRADED", meta={"phase": phase})

    for ing in _safe(lambda: net.list_ingress_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                     "ingress"):
        m = ing.metadata
        _mk("INGRESS", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp))

    for cm in _safe(lambda: core.list_config_map_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                    "configmap"):
        m = cm.metadata
        _mk("CONFIGMAP", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp),
            meta={"keys": list((cm.data or {}).keys())})

    # Secrets: METADATA ONLY — never read or return secret values.
    for sec in _safe(lambda: core.list_secret_for_all_namespaces(limit=_PAGE, _request_timeout=_TIMEOUT).items,
                     "secret"):
        m = sec.metadata
        _mk("SECRET", m.uid, m.name, ns=m.namespace, created=_iso(m.creation_timestamp),
            meta={"type": sec.type, "key_count": len(sec.data or {})})

    return out


async def discover_kubernetes(secret: dict) -> list[NormalizedResource]:
    return await asyncio.to_thread(_k8s_collect, secret)


# =========================================================================== #
# GCP — Compute instances + GKE clusters (REST, service-account JWT)
# =========================================================================== #
async def discover_gcp(secret: dict) -> list[NormalizedResource]:
    from app.services.gcp_auth import gcp_access_token, parse_service_account

    try:
        sa, project = parse_service_account(secret)
    except ValueError as exc:
        raise AdapterError("Invalid GCP service account configuration.") from exc
    if not project:
        raise AdapterError("GCP project_id is required for discovery.")

    try:
        token = await asyncio.to_thread(gcp_access_token, sa)
    except Exception as exc:  # noqa: BLE001
        logger.info("gcp_discovery_auth_failed", error=type(exc).__name__)
        raise AdapterError("Could not authenticate to GCP for discovery.") from exc

    headers = {"Authorization": f"Bearer {token}"}
    out: list[NormalizedResource] = []

    async def _fetch(url: str) -> dict:
        async with safe_http_client(timeout=_TIMEOUT, verify=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                raise AdapterError("GCP denied access for discovery.")
            if resp.status_code >= 400:
                return {}
            return resp.json()

    agg = await _fetch(
        f"https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/instances",
    )
    for _zone, zdata in (agg.get("items") or {}).items():
        if not isinstance(zdata, dict):
            continue
        zone = _zone.replace("zones/", "")
        for inst in (zdata.get("instances") or [])[:_PAGE]:
            if not isinstance(inst, dict):
                continue
            name = inst.get("name", "")
            out.append(NormalizedResource(
                provider="GCP", account=project, region=zone,
                resource_id=str(inst.get("id") or name), resource_type="COMPUTE_INSTANCE",
                resource_name=name, service_name=name,
                health="HEALTHY" if inst.get("status") == "RUNNING" else "DEGRADED",
                tags={k: v for k, v in (inst.get("labels") or {}).items()},
                metadata={"machine_type": inst.get("machineType", "").split("/")[-1]},
            ))

    clusters = await _fetch(
        f"https://container.googleapis.com/v1/projects/{project}/locations/-/clusters",
    )
    for cl in (clusters.get("clusters") or [])[:_PAGE]:
        if not isinstance(cl, dict):
            continue
        name = cl.get("name", "")
        out.append(NormalizedResource(
            provider="GCP", account=project, region=cl.get("location", ""),
            resource_id=name, resource_type="GKE_CLUSTER", resource_name=name,
            service_name=name,
            health="HEALTHY" if cl.get("status") == "RUNNING" else "DEGRADED",
            metadata={"node_count": cl.get("currentNodeCount")},
        ))

    logger.info("gcp_discovery_done", project=project, resources=len(out))
    return out[:_PAGE * 2]


# --------------------------------------------------------------------------- #
DISCOVERY_ADAPTERS = {
    "AWS": discover_aws,
    "AZURE": discover_azure,
    "GCP": discover_gcp,
    "KUBERNETES": discover_kubernetes,
}


def provider_supports_discovery(integration_key: str) -> bool:
    return integration_key in DISCOVERY_ADAPTERS


async def discover_provider(integration_key: str, secret: dict) -> list[NormalizedResource]:
    """Run the read-only discovery adapter for ``integration_key``.

    Raises AdapterError (customer-safe) on failure.
    """
    adapter = DISCOVERY_ADAPTERS.get(integration_key)
    if adapter is None:
        raise AdapterError(f"{integration_key} does not support live discovery.")
    return await adapter(secret)
