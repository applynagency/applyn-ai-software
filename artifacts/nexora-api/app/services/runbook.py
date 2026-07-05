"""Sprint 45A — Intelligent Runbook engine.

Generates investigation + remediation runbooks for a class of incident by mining
existing, read-only incident intelligence:

* 40A RCA / investigation  → known root causes + suspected triggers
* 40B timeline             → classification signals
* 41A recommendations      → recovery / follow-up steps
* 41B/41C remediation      → proven rollback / mitigation steps
* 44A postmortems          → lessons-learned for the recovery checklist

Each runbook has investigation steps, validation steps, rollback steps and a
recovery checklist. Runbooks can be manually edited and are versioned. Generation
never mutates incidents — it only reads them and writes its own record. Org-scoped
and audited; no secrets.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.incident import RemediationActionStatus
from app.models.runbook import RunbookCategory, RunbookSource, RunbookStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    IncidentInvestigationRepository,
    IncidentRecommendationRepository,
    IncidentRemediationActionRepository,
    IncidentTimelineEventRepository,
)
from app.repositories.postmortem import PostmortemRepository
from app.repositories.runbook import RunbookRepository
from app.schemas.runbook import RunbookResponse
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

# Classification keywords, evaluated most-specific first.
_CATEGORY_ORDER = [
    RunbookCategory.CRASHLOOPBACKOFF,
    RunbookCategory.DEPLOYMENT_FAILURE,
    RunbookCategory.CAPACITY,
    RunbookCategory.LATENCY_SPIKE,
    RunbookCategory.ERROR_SPIKE,
    RunbookCategory.KUBERNETES,
]
_CATEGORY_KEYWORDS = {
    RunbookCategory.CRASHLOOPBACKOFF: [
        "crashloop", "crash loop", "crashloopbackoff", "back-off", "backoff",
        "oomkilled", "oom killed", "container restart", "restarting", "exit code 137",
    ],
    RunbookCategory.DEPLOYMENT_FAILURE: [
        "deploy", "deployment fail", "rollout fail", "failed release", "bad deploy",
        "release", "rollback", "canary fail", "pipeline fail",
    ],
    RunbookCategory.CAPACITY: [
        "capacity", "cpu ", "memory", "disk", "saturation", "throttl", "scal",
        "exhaust", "quota", "out of memory", "resource limit", "no space",
    ],
    RunbookCategory.LATENCY_SPIKE: [
        "latency", "slow", "p95", "p99", "response time", "timeout",
        "degraded performance", "high response",
    ],
    RunbookCategory.ERROR_SPIKE: [
        "error rate", "5xx", "error spike", "elevated error", "high error",
        "exception", "errors", "failures",
    ],
    RunbookCategory.KUBERNETES: [
        "kubernetes", "k8s", "kubelet", "pod ", "replicaset", "namespace",
        "node not ready", "evicted", "rollout", "ingress",
    ],
}

_ROLLBACK_HINTS = ("rollback", "roll back", "revert", "scale", "restart", "undo", "failover", "fail over")


def _clip(text: str | None, n: int = 220) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _dedup_extend(base: list[str], extra: list[str], cap: int) -> list[str]:
    seen = {s.strip().lower() for s in base}
    out = list(base)
    for item in extra:
        key = item.strip().lower()
        if key and key not in seen:
            out.append(item)
            seen.add(key)
        if len(out) >= cap:
            break
    return out


class RunbookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RunbookRepository(session)
        self.inv_repo = IncidentInvestigationRepository(session)
        self.timeline_repo = IncidentTimelineEventRepository(session)
        self.rec_repo = IncidentRecommendationRepository(session)
        self.action_repo = IncidentRemediationActionRepository(session)
        self.pm_repo = PostmortemRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ------------------------------------------------------------------ classify
    @staticmethod
    def classify(haystack: str) -> str:
        h = (haystack or "").lower()
        for cat in _CATEGORY_ORDER:
            if any(kw in h for kw in _CATEGORY_KEYWORDS[cat]):
                return cat.value
        return RunbookCategory.GENERAL.value

    async def _incident_haystack(self, organization_id: str, inv) -> str:
        parts = [
            inv.title or "", inv.summary or "", inv.root_cause or "",
            getattr(inv, "suspected_trigger", "") or "",
            getattr(inv, "suspected_provider", "") or "",
        ]
        timeline = await self.timeline_repo.list_for_investigation(inv.id, organization_id)
        for e in timeline:
            parts.append(e.title or "")
            parts.append(e.provider or "")
        return " ".join(parts)

    # ------------------------------------------------------------------ generate
    async def generate(self, user, org_context, req) -> RunbookResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        category = None
        service = req.service
        seed_inv = None
        if req.investigation_id:
            seed_inv = await self.inv_repo.get_for_org(req.investigation_id, organization_id)
            if seed_inv is None:
                raise NexoraException("Incident not found.", status_code=404)
            haystack = await self._incident_haystack(organization_id, seed_inv)
            category = self.classify(haystack)
        elif req.category:
            category = req.category.upper()
            if category not in {c.value for c in RunbookCategory}:
                raise NexoraException(
                    f"Invalid category. One of {[c.value for c in RunbookCategory]}.",
                    status_code=400,
                )
        else:
            raise NexoraException(
                "Provide either 'category' or 'investigation_id'.", status_code=400
            )

        # Gather incidents of this category to learn from.
        incidents_all, _ = await self.inv_repo.list_for_org(organization_id, limit=500)
        matching = []
        for inv in incidents_all:
            h = await self._incident_haystack(organization_id, inv)
            if self.classify(h) == category:
                matching.append(inv)

        composed = await self._compose(organization_id, category, service, matching, req.title)

        existing = await self.repo.find_canonical(organization_id, category, service)
        if existing is not None:
            await self.repo.update(
                existing,
                version=existing.version + 1,
                status=RunbookStatus.REGENERATED.value,
                source=RunbookSource.GENERATED.value,
                updated_by=user.id,
                **composed,
            )
            runbook = existing
            created = False
        else:
            runbook = await self.repo.create(
                organization_id=organization_id,
                version=1,
                status=RunbookStatus.GENERATED.value,
                source=RunbookSource.GENERATED.value,
                created_by=user.id,
                updated_by=user.id,
                **composed,
            )
            created = True

        await self.audit_repo.log(
            action="runbook_generated" if created else "runbook_regenerated",
            resource_type="runbook",
            resource_id=runbook.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "category": category,
                "service": service,
                "version": runbook.version,
                "source_incidents": composed["source_incident_count"],
            },
        )
        await self.session.commit()
        return RunbookResponse.model_validate(runbook)

    # --------------------------------------------------------------------- list
    async def list(self, user, org_context, *, search=None, category=None, offset=0, limit=50):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows, total = await self.repo.search(
            organization_id, search=search, category=category, offset=offset, limit=limit
        )
        await self.audit_repo.log(
            action="runbook_searched",
            resource_type="runbook",
            resource_id=organization_id,
            user_id=user.id,
            details={"organization_id": organization_id, "search": search, "category": category, "results": len(rows)},
        )
        await self.session.commit()
        return rows, total

    async def get(self, user, org_context, runbook_id: str) -> RunbookResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rb = await self.repo.get_for_org(runbook_id, organization_id)
        if rb is None:
            raise NexoraException("Runbook not found.", status_code=404)
        return RunbookResponse.model_validate(rb)

    # --------------------------------------------------------------------- edit
    async def update(self, user, org_context, runbook_id: str, data) -> RunbookResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        rb = await self.repo.get_for_org(runbook_id, organization_id)
        if rb is None:
            raise NexoraException("Runbook not found.", status_code=404)

        if data.title is not None:
            rb.title = data.title
        if data.category is not None:
            cat = data.category.upper()
            if cat not in {c.value for c in RunbookCategory}:
                raise NexoraException("Invalid category.", status_code=400)
            rb.category = cat
        if data.service is not None:
            rb.service = data.service or None
        if data.summary is not None:
            rb.summary = data.summary
        if data.investigation_steps is not None:
            rb.investigation_steps = data.investigation_steps
        if data.validation_steps is not None:
            rb.validation_steps = data.validation_steps
        if data.rollback_steps is not None:
            rb.rollback_steps = data.rollback_steps
        if data.recovery_checklist is not None:
            rb.recovery_checklist = data.recovery_checklist

        rb.content_markdown = self._render_markdown(
            rb.title, rb.category, rb.service, rb.summary,
            rb.investigation_steps or [], rb.validation_steps or [],
            rb.rollback_steps or [], rb.recovery_checklist or [],
        )
        rb.search_text = self._search_text(
            rb.title, rb.category, rb.service, rb.summary,
            rb.investigation_steps or [], rb.validation_steps or [],
            rb.rollback_steps or [], rb.recovery_checklist or [],
        )
        rb.version = rb.version + 1
        rb.status = RunbookStatus.EDITED.value
        rb.source = RunbookSource.MANUAL.value
        rb.updated_by = user.id

        await self.audit_repo.log(
            action="runbook_updated",
            resource_type="runbook",
            resource_id=rb.id,
            user_id=user.id,
            details={"organization_id": organization_id, "version": rb.version},
        )
        await self.session.commit()
        await self.session.refresh(rb)
        return RunbookResponse.model_validate(rb)

    # ----------------------------------------------------------------- compose
    async def _compose(self, organization_id, category, service, incidents, title_override) -> dict:
        tmpl = _TEMPLATES.get(category, _TEMPLATES[RunbookCategory.GENERAL.value])
        investigation = list(tmpl["investigation"])
        validation = list(tmpl["validation"])
        rollback = list(tmpl["rollback"])
        recovery = list(tmpl["recovery"])

        learned_investigation: list[str] = []
        learned_rollback: list[str] = []
        learned_recovery: list[str] = []
        source_ids: list[str] = []

        for inv in incidents[:25]:
            source_ids.append(inv.id)
            if (inv.root_cause or "").strip():
                learned_investigation.append(
                    f"Known cause from past incident \"{_clip(inv.title, 80)}\": {_clip(inv.root_cause)}"
                )
            recs = await self.rec_repo.list_for_investigation(inv.id, organization_id)
            for r in recs:
                learned_recovery.append(f"Recommended remediation: {_clip(r.title, 140)}")
            actions = await self.action_repo.list_for_investigation(inv.id, organization_id)
            for a in actions:
                hint = (a.action_type or "") + " " + (a.title or "")
                if a.status == RemediationActionStatus.COMPLETED.value or any(
                    h in hint.lower() for h in _ROLLBACK_HINTS
                ):
                    learned_rollback.append(
                        f"Proven remediation ({a.action_type}): {_clip(a.title, 140)}"
                    )
            pm = await self.pm_repo.get_for_investigation(inv.id, organization_id)
            if pm is not None and getattr(pm, "lessons_learned", None):
                for line in (pm.lessons_learned or "").splitlines():
                    line = line.lstrip("- ").strip()
                    if line:
                        learned_recovery.append(f"Lesson learned: {_clip(line, 160)}")

        investigation = _dedup_extend(investigation, learned_investigation, cap=16)
        rollback = _dedup_extend(rollback, learned_rollback, cap=14)
        recovery = _dedup_extend(recovery, learned_recovery, cap=16)

        cat_label = category.replace("_", " ").title()
        n = len(source_ids)
        title = title_override or (
            f"{cat_label} Runbook" + (f" — {service}" if service else "")
        )
        if n:
            summary = (
                f"Investigation and remediation runbook for {cat_label} incidents"
                + (f" affecting {service}" if service else "")
                + f", synthesized from {n} past incident(s) and their RCA, recommendations, "
                "remediation actions, and postmortems."
            )
        else:
            summary = (
                f"Investigation and remediation runbook for {cat_label} incidents"
                + (f" affecting {service}" if service else "")
                + ". Generated from category best-practices; no matching past incidents yet — "
                "it will incorporate learnings as incidents accrue."
            )

        content_markdown = self._render_markdown(
            title, category, service, summary, investigation, validation, rollback, recovery
        )
        search_text = self._search_text(
            title, category, service, summary, investigation, validation, rollback, recovery
        )
        return {
            "title": title,
            "category": category,
            "service": service,
            "summary": summary,
            "investigation_steps": investigation,
            "validation_steps": validation,
            "rollback_steps": rollback,
            "recovery_checklist": recovery,
            "content_markdown": content_markdown,
            "search_text": search_text,
            "source_incident_ids": source_ids,
            "source_incident_count": n,
        }

    @staticmethod
    def _search_text(title, category, service, summary, inv, val, rb, rec) -> str:
        parts = [title or "", category or "", service or "", summary or ""]
        parts += inv + val + rb + rec
        return " ".join(parts).lower()

    @staticmethod
    def _render_markdown(title, category, service, summary, inv, val, rb, rec) -> str:
        def block(name, items):
            if not items:
                return [f"## {name}", "_None._", ""]
            lines = [f"## {name}"]
            lines += [f"{i}. {step}" for i, step in enumerate(items, 1)]
            lines.append("")
            return lines

        parts = [
            f"# {title}",
            "",
            f"**Category:** {category}"
            + (f"  |  **Service:** {service}" if service else "")
            + "",
            "",
            summary or "",
            "",
        ]
        parts += block("Investigation Steps", inv)
        parts += block("Validation Steps", val)
        parts += block("Rollback Steps", rb)
        parts += block("Recovery Checklist", rec)
        parts += [
            "---",
            "_Generated by the Intelligent Runbooks engine from past incident "
            "intelligence. Advisory only — it does not execute any action._",
        ]
        return "\n".join(parts)


_TEMPLATES: dict[str, dict[str, list[str]]] = {
    RunbookCategory.KUBERNETES.value: {
        "investigation": [
            "Confirm the affected cluster, namespace, and workload (Deployment/StatefulSet/DaemonSet).",
            "List unhealthy pods: `kubectl get pods -n <ns>` (not Running/Ready).",
            "Inspect pod events: `kubectl describe pod <pod> -n <ns>` (scheduling, image pull, probe failures).",
            "Review recent rollouts: `kubectl rollout history deployment/<name> -n <ns>`.",
            "Check node health: `kubectl get nodes` / `kubectl describe node <node>` for pressure or taints.",
        ],
        "validation": [
            "Desired vs available replicas match: `kubectl get deploy <name> -n <ns>`.",
            "Readiness/liveness probes are passing.",
            "No new warning events for the workload.",
        ],
        "rollback": [
            "Roll back the workload to the last healthy revision: `kubectl rollout undo deployment/<name> -n <ns>`.",
            "If a node is unhealthy: `kubectl cordon <node>` then `kubectl drain <node>`.",
            "Restore a known-good replica count if autoscaling misbehaved.",
        ],
        "recovery": [
            "All pods Running and Ready.",
            "`kubectl rollout status deployment/<name> -n <ns>` reports success.",
            "Error rate and latency back to baseline.",
            "Capture the failing manifest/diff for the postmortem.",
        ],
    },
    RunbookCategory.CRASHLOOPBACKOFF.value: {
        "investigation": [
            "Identify crash-looping pods: `kubectl get pods -n <ns>` (CrashLoopBackOff/Error).",
            "Read current and previous logs: `kubectl logs <pod> -n <ns> --previous`.",
            "Describe the pod for restart count, last state, and exit code: `kubectl describe pod <pod> -n <ns>`.",
            "Check for OOMKilled (exit code 137) — compare memory limits vs usage.",
            "Validate config/secret/env references and mounted volumes required at startup.",
        ],
        "validation": [
            "Container starts and passes its readiness probe.",
            "Restart count stabilizes (no new restarts over several minutes).",
            "Startup logs show successful initialization.",
        ],
        "rollback": [
            "Roll back to the last image/revision that started cleanly: `kubectl rollout undo deployment/<name> -n <ns>`.",
            "If OOMKilled, raise memory request/limit to a safe value and redeploy.",
            "Revert the bad config / disable the failing feature flag the container needs at startup.",
        ],
        "recovery": [
            "Zero new restarts over a sustained window.",
            "Pod Running/Ready and serving traffic.",
            "Resource limits validated against observed usage.",
            "Document the crash cause and exit code in the postmortem.",
        ],
    },
    RunbookCategory.DEPLOYMENT_FAILURE.value: {
        "investigation": [
            "Identify the failing deployment/release: version, provider, environment.",
            "Diff the change-set against the last successful deploy (commits, migrations, config).",
            "Review deploy/pipeline logs for the first error.",
            "Determine whether a database migration or infrastructure change is in the release.",
            "Correlate the deploy timestamp with the first error/latency signal.",
        ],
        "validation": [
            "Confirm the version actually running is the intended one.",
            "Smoke-test critical endpoints / health checks.",
            "Verify migrations applied cleanly (or were safely skipped).",
        ],
        "rollback": [
            "Roll back to the last known-good version/artifact.",
            "If a migration ran, apply the reverse migration or restore from backup per the data runbook.",
            "Revert risky config / feature flags introduced by the release.",
            "Re-run deployment safety/guardrail checks before re-attempting.",
        ],
        "recovery": [
            "Service healthy on a known-good version.",
            "Error rate and latency back to baseline.",
            "Rollback verified; the bad artifact quarantined.",
            "File a follow-up to add a pre-deploy check that would have caught this.",
        ],
    },
    RunbookCategory.LATENCY_SPIKE.value: {
        "investigation": [
            "Identify which endpoints/services show elevated p95/p99 latency and since when.",
            "Check whether the spike aligns with a deploy, traffic surge, or dependency slowdown.",
            "Inspect downstream dependencies (DB, cache, upstream services) for saturation or slow queries.",
            "Review CPU/memory/thread-pool/connection-pool saturation on the service.",
            "Look for GC pauses, lock contention, or N+1 query patterns.",
        ],
        "validation": [
            "p95/p99 latency returning toward baseline.",
            "Dependency latencies within normal ranges.",
            "Saturation metrics (CPU, pool utilization) healthy.",
        ],
        "rollback": [
            "If a recent deploy caused it, roll back to the previous version.",
            "Scale out the service / increase pool sizes to relieve saturation.",
            "Shed or rate-limit non-critical traffic; enable caching for hot paths.",
        ],
        "recovery": [
            "Latency SLO back within target.",
            "No dependency saturation.",
            "Autoscaling thresholds reviewed for the observed load.",
            "Capture slow traces/queries for follow-up optimization.",
        ],
    },
    RunbookCategory.ERROR_SPIKE.value: {
        "investigation": [
            "Identify the error class (5xx, exceptions) and the endpoints/services affected.",
            "Pull a sample of error logs/stack traces for the dominant error signature.",
            "Correlate the spike start with deploys, config changes, or dependency failures.",
            "Check dependency health (DB, auth, third-party APIs) and circuit-breaker state.",
            "Determine the blast radius: which downstream consumers are impacted.",
        ],
        "validation": [
            "Error rate dropping back to baseline.",
            "Dominant error signature no longer in fresh logs.",
            "Dependent services recovered.",
        ],
        "rollback": [
            "Roll back the suspected change/deploy.",
            "Fail over or disable the failing dependency/integration if isolated.",
            "Toggle off the offending feature flag.",
        ],
        "recovery": [
            "Error-rate SLO back within target.",
            "No elevated errors across dependent services.",
            "Alerting thresholds validated.",
            "File a follow-up to add a regression test for the error path.",
        ],
    },
    RunbookCategory.CAPACITY.value: {
        "investigation": [
            "Identify the saturated resource (CPU, memory, disk, network, pods/nodes) and its trend.",
            "Determine whether it is organic growth, a leak, a traffic surge, or a misconfiguration.",
            "Check autoscaling status and limits (HPA / cluster autoscaler / quotas).",
            "Review the capacity forecast and saturation/exhaustion projection for the resource.",
            "Inspect noisy-neighbor or runaway workloads consuming the resource.",
        ],
        "validation": [
            "Utilization back below the saturation threshold.",
            "Autoscaling reacted appropriately and headroom is restored.",
            "No requests being throttled/evicted.",
        ],
        "rollback": [
            "Scale up/out the saturated resource to restore headroom.",
            "Roll back a change that increased resource consumption, if identified.",
            "Raise quotas/limits to a safe level or evict noisy-neighbor workloads.",
        ],
        "recovery": [
            "Utilization within a healthy range with adequate headroom.",
            "Autoscaling and limits tuned for observed demand.",
            "Capacity forecast updated.",
            "Open a follow-up for right-sizing / capacity planning.",
        ],
    },
    RunbookCategory.GENERAL.value: {
        "investigation": [
            "Establish the timeline: when did the incident begin and what was the first symptom?",
            "Identify the affected service(s), environment, and blast radius.",
            "Review recent changes (deploys, config, infra) preceding the incident.",
            "Gather logs, metrics, and traces around the onset.",
            "Form and test a hypothesis for the most likely cause.",
        ],
        "validation": [
            "The suspected cause explains the observed symptoms.",
            "Key health metrics are returning to baseline.",
        ],
        "rollback": [
            "Revert the most likely triggering change.",
            "Restore the service to its last known-good state.",
        ],
        "recovery": [
            "Service health and SLOs back within target.",
            "Root cause documented.",
            "Follow-up actions filed.",
        ],
    },
}
