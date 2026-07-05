"""Sprint 46D - AI Incident War Room engine.

A deterministic (no-LLM), rules-based multi-agent collaboration that convenes
specialist agents on an incident and produces a consensus RCA plus an advisory
remediation plan. Each agent reads existing, read-only incident intelligence:

* CTO        - business / customer impact via 44B blast radius
* SRE        - incident severity, status, alert volume, service health (42C)
* Kubernetes - workload-level signals (CrashLoopBackOff, OOMKilled, rollouts)
* GitHub     - recent deploy/change events (40C) as candidate triggers
* Database   - datastore signals (locks, pools, slow queries) + 44B datastores
* Security   - security indicators (auth, intrusion, CVE, DDoS)

The agents share findings, challenge them, propose hypotheses and remediation,
then the room synthesizes consensus.

SAFETY: advisory only. The room NEVER executes, deploys, rolls back, or mutates
anything. Human approval is always mandatory - a convened room rests in
AWAITING_APPROVAL. Customer-safe text only; never secrets.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.models.war_room import WarRoomAgent, WarRoomMessageType, WarRoomStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    DeploymentChangeEventRepository,
    IncidentInvestigationRepository,
    IncidentRecommendationRepository,
    IncidentTimelineEventRepository,
    MonitoringAlertRepository,
)
from app.repositories.slo import ServiceRepository, ServiceSLORepository
from app.repositories.war_room import WarRoomMessageRepository, WarRoomRepository
from app.schemas.war_room import (
    MessageView,
    RemediationStep,
    WarRoomResponse,
)
from app.services.dependency_graph import DependencyGraphService
from app.services.graph import GraphService
from app.services.service_health import ServiceHealthService
from app.tenancy.permissions import can_read_ai_teams

logger = structlog.get_logger(__name__)

_K8S = ["crashloop", "oomkill", "kubelet", "replica", "rollout", "container",
        "kubernetes", "k8s", "evicted", "readiness", "liveness", "pod ", " pod"]
_DB = ["database", "postgres", "mysql", "mariadb", "mongo", "redis", "deadlock",
       "connection pool", "slow query", "replication", "datastore", " sql", "cache"]
_SEC = ["unauthorized", "401", "403", "breach", "cve", "vulnerab", "ddos", "attack",
        "intrusion", "credential leak", "exfiltrat", "rate limit", "malicious"]
_DEPLOY = ["deploy", "release", "rollout", "version", "commit", "merge", "pipeline"]

_REC_AGENT = {
    "Kubernetes": WarRoomAgent.KUBERNETES.value,
    "Deployment": WarRoomAgent.GITHUB.value,
    "Database": WarRoomAgent.DATABASE.value,
    "Infrastructure": WarRoomAgent.SRE.value,
    "Monitoring": WarRoomAgent.SRE.value,
    "Application": WarRoomAgent.SRE.value,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(v)))


def _matches(haystack: str, kws: list[str]) -> list[str]:
    return [k.strip() for k in kws if k in haystack]


class WarRoomService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.room_repo = WarRoomRepository(session)
        self.msg_repo = WarRoomMessageRepository(session)
        self.incident_repo = IncidentInvestigationRepository(session)
        self.timeline_repo = IncidentTimelineEventRepository(session)
        self.change_repo = DeploymentChangeEventRepository(session)
        self.rec_repo = IncidentRecommendationRepository(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.service_repo = ServiceRepository(session)
        self.slo_repo = ServiceSLORepository(session)
        self.graph = GraphService(session)
        self.health = ServiceHealthService(session)
        self.depgraph = DependencyGraphService(session)

    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # --------------------------------------------------------------- public
    async def create(self, user, org_context, *, incident_id, title) -> WarRoomResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        incident = None
        if incident_id:
            incident = await self.incident_repo.get_for_org(incident_id, organization_id)
            if incident is None:
                raise NexoraException("Incident not found.", status_code=404)

        room_title = title or (f"War Room: {incident.title}" if incident else "Incident War Room")
        room = await self.room_repo.create(
            organization_id=organization_id,
            incident_id=incident_id,
            title=room_title,
            status=WarRoomStatus.OPEN.value,
            requires_approval=True,
            confidence_score=0,
            message_count=1,
        )
        opener = (
            f"War room convened for '{incident.title}'."
            if incident else "War room convened (no incident linked)."
        ) + " Specialist agents (CTO, SRE, Kubernetes, GitHub, Database, Security) standing by."
        await self.msg_repo.create(
            war_room_id=room.id, organization_id=organization_id,
            agent=WarRoomAgent.SYSTEM.value, message_type=WarRoomMessageType.INFO.value,
            content=opener, sequence=0, citations=[],
        )
        await self.audit_repo.log(
            action="war_room_created", resource_type="war_room", resource_id=room.id,
            user_id=user.id,
            details={"organization_id": organization_id, "incident_id": incident_id},
        )
        await self.session.commit()
        msgs = await self.msg_repo.list_for_room(room.id, organization_id)
        return self._to_response(room, msgs)

    async def list(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.room_repo.list_for_org(organization_id)

    async def get(self, user, org_context, room_id: str) -> WarRoomResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self.room_repo.get_for_org(room_id, organization_id)
        if room is None:
            raise NexoraException("War room not found.", status_code=404)
        msgs = await self.msg_repo.list_for_room(room.id, organization_id)
        return self._to_response(room, msgs)

    async def execute(self, user, org_context, room_id: str) -> WarRoomResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self.room_repo.get_for_org(room_id, organization_id)
        if room is None:
            raise NexoraException("War room not found.", status_code=404)
        if room.status != WarRoomStatus.OPEN.value:
            raise NexoraException(
                "War room has already been convened. Create a new room to re-run.",
                status_code=400,
            )

        ctx = await self._gather(organization_id, room.incident_id)
        messages, rca, plan, confidence = self._run_discussion(ctx)

        seq = 1
        for msg in messages:
            await self.msg_repo.create(
                war_room_id=room.id, organization_id=organization_id,
                agent=msg["agent"], message_type=msg["type"], content=msg["content"],
                confidence=msg.get("confidence"), citations=msg.get("citations") or [],
                sequence=seq,
            )
            seq += 1

        agents = [WarRoomAgent.CTO.value, WarRoomAgent.SRE.value, WarRoomAgent.KUBERNETES.value,
                  WarRoomAgent.GITHUB.value, WarRoomAgent.DATABASE.value, WarRoomAgent.SECURITY.value]
        room.status = WarRoomStatus.AWAITING_APPROVAL.value
        room.consensus_rca = rca
        room.remediation_plan = [s.model_dump() for s in plan]
        room.confidence_score = confidence
        room.participating_agents = agents
        room.message_count = seq
        room.summary = (
            f"Consensus reached with {confidence}% confidence across {len(agents)} agents. "
            f"{len(plan)} remediation step(s) proposed - all require human approval before execution."
        )
        await self.session.flush()

        await self.audit_repo.log(
            action="war_room_executed", resource_type="war_room", resource_id=room.id,
            user_id=user.id,
            details={"organization_id": organization_id, "incident_id": room.incident_id,
                     "confidence": confidence, "remediation_steps": len(plan),
                     "autonomous_execution": False},
        )
        await self.session.commit()
        msgs = await self.msg_repo.list_for_room(room.id, organization_id)
        return self._to_response(room, msgs)

    # ------------------------------------------------------------- gather
    async def _gather(self, organization_id, incident_id) -> dict:
        ctx: dict = {"incident": None, "timeline": [], "changes": [], "recs": [],
                     "alerts": [], "origin": None, "affected": 0, "blast_level": "LOW",
                     "health_score": None}
        incident = None
        if incident_id:
            incident = await self.incident_repo.get_for_org(incident_id, organization_id)
        ctx["incident"] = incident

        all_alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=2000)
        if incident:
            ctx["timeline"] = await self.timeline_repo.list_for_investigation(incident.id, organization_id)
            ctx["changes"] = await self.change_repo.list_for_investigation(incident.id, organization_id)
            ctx["recs"] = await self.rec_repo.list_for_investigation(incident.id, organization_id)
            ctx["alerts"] = [a for a in all_alerts if a.incident_id == incident.id]
        else:
            ctx["alerts"] = all_alerts

        # blast radius (44B) - reuse origin resolution + graph, no audit/commit
        if incident:
            origin_name, _ = await self.depgraph._resolve_origin_service(organization_id, incident)
            services = await self.service_repo.list_for_org(organization_id)
            by_name = {s.name: s for s in services}
            origin = by_name.get(origin_name) if origin_name else None
            ctx["origin"] = origin
            if origin:
                g = await self.graph.service_adjacency(organization_id)
                _, transitive = g.dependents(origin.id)
                ctx["affected"] = len(transitive)
                ctx["blast_level"] = self._blast_level(origin, len(transitive), incident.severity)
                slos = await self.slo_repo.list_for_service(origin.id, organization_id)
                health = await self.health._compute(organization_id, origin, slos, full=False)
                ctx["health_score"] = health.health_score

        # build searchable haystack of customer-safe evidence text
        parts = []
        if incident:
            parts += [incident.title or "", incident.summary or "", incident.root_cause or "",
                      incident.suspected_trigger or ""]
        parts += [a.alert_name or "" for a in ctx["alerts"]]
        parts += [a.description or "" for a in ctx["alerts"]]
        parts += [t.title or "" for t in ctx["timeline"]]
        parts += [c.title or "" for c in ctx["changes"]]
        ctx["haystack"] = " ".join(parts).lower()
        return ctx

    @staticmethod
    def _blast_level(origin, affected, severity) -> str:
        sev = (severity or "").upper()
        if affected >= 5 or (origin.tier == "TIER_1" and (affected > 0 or sev in ("CRITICAL", "HIGH"))):
            return "CRITICAL"
        if affected >= 2 or sev in ("CRITICAL", "HIGH"):
            return "HIGH"
        if affected == 1:
            return "MEDIUM"
        return "LOW"

    # ------------------------------------------------------------- discussion
    def _run_discussion(self, ctx):
        incident = ctx["incident"]
        hay = ctx["haystack"]
        alerts = ctx["alerts"]
        changes = ctx["changes"]
        msgs: list[dict] = []

        def cite():
            c = []
            if incident:
                c.append(f"incident:{incident.id}")
            return c

        k8s_hits = _matches(hay, _K8S)
        db_hits = _matches(hay, _DB)
        sec_hits = _matches(hay, _SEC)
        deploy_hits = _matches(hay, _DEPLOY) or bool(changes)

        # ---- FINDINGS -------------------------------------------------------
        sev = (incident.severity if incident else None) or "UNKNOWN"
        status = incident.status if incident else "n/a"
        msgs.append({"agent": WarRoomAgent.SRE.value, "type": WarRoomMessageType.FINDING.value,
                     "confidence": _clamp(70 + (10 if incident and incident.root_cause else 0)),
                     "citations": cite(),
                     "content": (
                         f"Incident severity {sev}, status {status}. {len(alerts)} alert(s) and "
                         f"{len(ctx['timeline'])} timeline event(s) on record"
                         + (f"; current service health score {ctx['health_score']}/100." if ctx['health_score'] is not None else ".")
                     )})

        if k8s_hits:
            msgs.append({"agent": WarRoomAgent.KUBERNETES.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 65, "citations": cite(),
                         "content": f"Kubernetes-level signals detected ({', '.join(sorted(set(k8s_hits)))}). "
                                    "Workload fault is plausible (failed rollout, CrashLoopBackOff, OOMKilled, probe failures)."})
        else:
            msgs.append({"agent": WarRoomAgent.KUBERNETES.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 60, "citations": cite(),
                         "content": "No Kubernetes-level indicators in the evidence; cluster scheduling and pods appear healthy."})

        if changes:
            latest = changes[-1]
            msgs.append({"agent": WarRoomAgent.GITHUB.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 72, "citations": cite(),
                         "content": f"{len(changes)} recent change/deploy event(s) correlated. Latest: '{latest.title}'"
                                    + (f" by {latest.actor}" if latest.actor else "")
                                    + (f" (version {latest.version})" if latest.version else "")
                                    + ". A recent change is a leading candidate trigger."})
        else:
            msgs.append({"agent": WarRoomAgent.GITHUB.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 55, "citations": cite(),
                         "content": "No deployments or code changes correlate to the incident window; change-induced regression is unlikely."})

        if db_hits:
            msgs.append({"agent": WarRoomAgent.DATABASE.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 62, "citations": cite(),
                         "content": f"Datastore indicators present ({', '.join(sorted(set(db_hits)))}). "
                                    "Check connection-pool exhaustion, slow queries, locks/deadlocks and replication lag."})
        else:
            msgs.append({"agent": WarRoomAgent.DATABASE.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 55, "citations": cite(),
                         "content": "No database-layer indicators detected; datastore is not an obvious contributor."})

        if sec_hits:
            msgs.append({"agent": WarRoomAgent.SECURITY.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 64, "citations": cite(),
                         "content": f"Security indicators present ({', '.join(sorted(set(sec_hits)))}). "
                                    "Treat as a possible security vector; recommend security on-call review."})
        else:
            msgs.append({"agent": WarRoomAgent.SECURITY.value, "type": WarRoomMessageType.FINDING.value,
                         "confidence": 60, "citations": cite(),
                         "content": "No security indicators (auth, intrusion, CVE, DDoS); ruling out a malicious vector for now."})

        msgs.append({"agent": WarRoomAgent.CTO.value, "type": WarRoomMessageType.FINDING.value,
                     "confidence": 68, "citations": cite(),
                     "content": (
                         f"Customer/business impact assessed as {ctx['blast_level']}: "
                         f"{ctx['affected']} dependent service(s) potentially affected"
                         + (f" (origin '{ctx['origin'].name}', {ctx['origin'].tier})." if ctx['origin'] else ".")
                     )})

        # ---- CHALLENGES -----------------------------------------------------
        if changes:
            msgs.append({"agent": WarRoomAgent.SRE.value, "type": WarRoomMessageType.CHALLENGE.value,
                         "confidence": None, "citations": cite(),
                         "content": "Challenge: GitHub points to a recent deploy, but we must confirm the change "
                                    "preceded the first alert before treating correlation as causation."})
        if k8s_hits and changes:
            msgs.append({"agent": WarRoomAgent.KUBERNETES.value, "type": WarRoomMessageType.CHALLENGE.value,
                         "confidence": None, "citations": cite(),
                         "content": "Challenge: a rollout is present - re-examining whether the new revision's probes/"
                                    "resource limits caused the workload fault, versus an unrelated cluster event."})
        if not sec_hits:
            msgs.append({"agent": WarRoomAgent.SECURITY.value, "type": WarRoomMessageType.CHALLENGE.value,
                         "confidence": None, "citations": cite(),
                         "content": "No objection from security; the evidence does not support a malicious-activity hypothesis."})
        msgs.append({"agent": WarRoomAgent.CTO.value, "type": WarRoomMessageType.CHALLENGE.value,
                     "confidence": None, "citations": cite(),
                     "content": "Challenge to the room: can we rule out coincidental correlation before we commit to a single root cause?"})

        # ---- HYPOTHESES (ranked) -------------------------------------------
        hyps: list[tuple[str, str, int]] = []
        if incident and incident.root_cause:
            hyps.append((WarRoomAgent.SRE.value,
                         f"Prior RCA already identified: {incident.root_cause}", 82))
        if changes:
            hyps.append((WarRoomAgent.GITHUB.value,
                         "A recent deployment/change introduced a regression (most recent change is the prime suspect).", 74))
        if k8s_hits:
            hyps.append((WarRoomAgent.KUBERNETES.value,
                         "A Kubernetes workload fault (failed rollout / CrashLoopBackOff / OOMKilled) degraded the service.", 66))
        if db_hits:
            hyps.append((WarRoomAgent.DATABASE.value,
                         "A datastore bottleneck (pool exhaustion / slow queries / locks) is degrading dependent services.", 62))
        if sec_hits:
            hyps.append((WarRoomAgent.SECURITY.value,
                         "A security event (abuse / DDoS / unauthorized access) is driving the disruption.", 60))
        if ctx["health_score"] is not None and ctx["health_score"] < 80:
            hyps.append((WarRoomAgent.SRE.value,
                         f"Service degradation/saturation (health score {ctx['health_score']}/100) indicates resource pressure.", 64))
        if not hyps:
            hyps.append((WarRoomAgent.SRE.value,
                         "Insufficient correlated evidence; transient degradation is the leading explanation pending more data.", 50))
        hyps.sort(key=lambda h: h[2], reverse=True)
        for agent, text, conf in hyps:
            msgs.append({"agent": agent, "type": WarRoomMessageType.HYPOTHESIS.value,
                         "confidence": conf, "citations": cite(), "content": f"Hypothesis: {text}"})
        primary_agent, primary_text, primary_conf = hyps[0]

        # ---- REMEDIATION ----------------------------------------------------
        plan: list[RemediationStep] = []
        order = 1
        recs = ctx["recs"]
        if recs:
            for r in recs:
                owner = _REC_AGENT.get(r.recommendation_type, WarRoomAgent.SRE.value)
                msgs.append({"agent": owner, "type": WarRoomMessageType.REMEDIATION.value,
                             "confidence": r.confidence_score, "citations": cite(),
                             "content": f"Proposed remediation: {r.title}"
                                        + (f" - {r.description}" if r.description else "")})
                plan.append(RemediationStep(
                    order=order, owner_agent=owner,
                    priority="HIGH" if r.risk_level == "LOW" else "MEDIUM",
                    action=r.title, rationale=(r.description or "Derived from incident recommendation."),
                    risk_level=r.risk_level, requires_approval=True))
                order += 1
        else:
            defaults = self._default_remediation(primary_agent, k8s_hits, db_hits, sec_hits, bool(changes))
            for owner, action, rationale, risk in defaults:
                msgs.append({"agent": owner, "type": WarRoomMessageType.REMEDIATION.value,
                             "confidence": primary_conf, "citations": cite(),
                             "content": f"Proposed remediation: {action}"})
                plan.append(RemediationStep(
                    order=order, owner_agent=owner, priority="HIGH" if order == 1 else "MEDIUM",
                    action=action, rationale=rationale, risk_level=risk, requires_approval=True))
                order += 1
        # always close with a validation step
        plan.append(RemediationStep(
            order=order, owner_agent=WarRoomAgent.SRE.value, priority="LOW",
            action="Monitor error rate, latency, and health after any approved action; confirm full recovery.",
            rationale="Validate that the approved remediation resolved the incident without regressions.",
            risk_level="LOW", requires_approval=True))

        # ---- CONSENSUS ------------------------------------------------------
        confidence = self._consensus_confidence(primary_conf, hyps, incident)
        msgs.append({"agent": WarRoomAgent.CTO.value, "type": WarRoomMessageType.CONSENSUS.value,
                     "confidence": confidence, "citations": cite(),
                     "content": (
                         f"Consensus reached ({confidence}% confidence). Primary root cause: {primary_text} "
                         f"{len(plan)} remediation step(s) proposed. ALL actions require explicit human approval - "
                         "the war room will not execute anything autonomously."
                     )})

        rca = self._render_rca(ctx, primary_text, hyps, confidence)
        return msgs, rca, plan, confidence

    @staticmethod
    def _default_remediation(primary_agent, k8s, db, sec, has_change):
        steps = []
        if has_change or primary_agent == WarRoomAgent.GITHUB.value:
            steps.append((WarRoomAgent.GITHUB.value,
                          "Roll back to the last known-good release and re-deploy behind a canary with automated rollback.",
                          "A recent change is the prime suspect; reverting fastest restores service.", "MEDIUM"))
        if k8s or primary_agent == WarRoomAgent.KUBERNETES.value:
            steps.append((WarRoomAgent.KUBERNETES.value,
                          "Roll back the workload to the previous healthy revision; verify probes and resource limits.",
                          "Restores a healthy pod template if the rollout/limits caused the fault.", "MEDIUM"))
        if db or primary_agent == WarRoomAgent.DATABASE.value:
            steps.append((WarRoomAgent.DATABASE.value,
                          "Relieve the datastore: scale/failover, tune the connection pool, terminate long-running queries.",
                          "Mitigates pool exhaustion, locks, and slow-query pressure.", "HIGH"))
        if sec or primary_agent == WarRoomAgent.SECURITY.value:
            steps.append((WarRoomAgent.SECURITY.value,
                          "Engage security on-call: block offending sources, rotate exposed credentials, enable rate limiting.",
                          "Contains a potential security vector while preserving forensic evidence.", "HIGH"))
        if not steps:
            steps.append((WarRoomAgent.SRE.value,
                          "Scale the affected service, drain unhealthy instances, and closely monitor recovery.",
                          "Safe, reversible mitigation when no single root cause dominates.", "MEDIUM"))
        return steps

    @staticmethod
    def _consensus_confidence(primary_conf, hyps, incident) -> int:
        conf = primary_conf
        # agreement bonus: more than one strong hypothesis raises confidence slightly
        strong = sum(1 for _, _, c in hyps if c >= 60)
        if strong >= 2:
            conf += 5
        if incident and incident.confidence_score:
            conf = round((conf + incident.confidence_score) / 2)
        return _clamp(conf)

    @staticmethod
    def _render_rca(ctx, primary_text, hyps, confidence) -> str:
        incident = ctx["incident"]
        L = ["# War Room Consensus RCA"]
        if incident:
            L.append(f"Incident: {incident.title} (severity {incident.severity or 'n/a'})")
        L += [
            f"Consensus confidence: {confidence}%",
            "",
            "## Primary Root Cause",
            primary_text,
            "",
            "## Customer / Business Impact",
            f"Blast radius: {ctx['blast_level']} - {ctx['affected']} dependent service(s)"
            + (f" (origin '{ctx['origin'].name}', {ctx['origin'].tier})." if ctx['origin'] else "."),
            "",
            "## Considered Hypotheses (ranked)",
        ]
        for agent, text, conf in hyps:
            L.append(f"- [{agent}] {text} (confidence {conf}%)")
        L += ["", "## Approval",
              "This RCA and the accompanying remediation plan are advisory. Human approval is "
              "mandatory before any remediation is executed; the war room performs no autonomous actions."]
        return "\n".join(L)

    # ------------------------------------------------------------- shaping
    @staticmethod
    def _to_response(room, messages) -> WarRoomResponse:
        plan = [RemediationStep(**s) for s in (room.remediation_plan or [])]
        return WarRoomResponse(
            id=room.id, organization_id=room.organization_id, incident_id=room.incident_id,
            title=room.title, status=room.status, summary=room.summary,
            consensus_rca=room.consensus_rca, remediation_plan=plan,
            confidence_score=room.confidence_score,
            participating_agents=room.participating_agents or [],
            requires_approval=room.requires_approval, autonomous_execution=False,
            message_count=room.message_count,
            messages=[MessageView.model_validate(m) for m in messages],
            created_at=room.created_at,
        )
