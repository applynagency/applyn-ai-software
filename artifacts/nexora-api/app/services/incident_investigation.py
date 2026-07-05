"""Sprint 40A — Incident Investigation Engine.

Lets an AI Team agent investigate a production incident by reading from the
team's connected, read-only tools (Sprint 39B/39C) across multiple systems,
correlating what it finds, and synthesizing a Root Cause Analysis report
(summary + timeline + findings + root cause + recommendations).

Strictly investigation-only:
  * Only read-only allow-listed tool actions are ever run (validated again here
    via the registry — defense in depth).
  * No remediation, deployments, scaling, mutations, or autonomous actions.
  * Only tools explicitly assigned to the investigating agent are used, so the
    existing tool permission model is enforced unchanged.
  * Customer-safe text only — no secrets are stored, logged, or returned.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.core.logging import get_logger
from app.models.incident import (
    IncidentInvestigationStatus,
    IncidentInvestigationStepStatus,
)
from app.models.user import User
from app.repositories.ai_team import AITeamAgentToolRepository, AITeamRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    DeploymentChangeEventRepository,
    IncidentInvestigationRepository,
    IncidentInvestigationStepRepository,
    IncidentRecommendationRepository,
    IncidentTimelineEventRepository,
)
from app.schemas.incident import (
    DeploymentChangeEventResponse,
    IncidentChangesResponse,
    IncidentDetailResponse,
    IncidentInvestigateRequest,
    IncidentListResponse,
    IncidentRecommendationResponse,
    IncidentRecommendationsResponse,
    IncidentResponse,
    IncidentStepResponse,
    IncidentTimelineEventResponse,
    IncidentTimelineResponse,
    IncidentTriggerAnalysis,
    SuspectedChange,
)
from app.services import (
    change_intelligence,
    incident_correlation,
    remediation_recommendations,
)
from app.services.ai_team_runner import AITeamAgentRunner
from app.services.ai_team_tools import AITeamToolService
from app.services.remediation_actions import RemediationActionService
from app.services.tool_registry import sanitize_payload
from app.tenancy.guards import get_ai_team_agent_for_org, get_ai_team_for_org
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = get_logger(__name__)

# Ordered, incident-oriented investigation plan. Only read-only allow-listed
# actions appear here; each is re-validated by the registry before running.
# (action, label, default_payload)
INVESTIGATION_PLAN: dict[str, list[tuple[str, str, dict]]] = {
    "KUBERNETES": [
        ("get_pods", "pod status", {}),
        ("get_events", "cluster events", {}),
        ("get_deployments", "deployment status", {}),
    ],
    "PROMETHEUS": [("query_metrics", "service metrics", {"query": "up"})],
    "GRAFANA": [("query_dashboard", "dashboards", {})],
    "DATADOG": [
        ("list_incidents", "active incidents", {}),
        ("list_monitors", "monitor status", {}),
    ],
    "GITHUB": [
        ("list_workflow_runs", "recent CI workflow runs", {}),
        ("list_releases", "recent releases", {}),
    ],
    "JENKINS": [
        ("list_jobs", "jenkins jobs", {}),
        ("list_builds", "recent builds", {}),
    ],
    "AZURE": [("read_diagnostics", "resource diagnostics", {})],
    "AWS": [("read_cloudwatch_metrics", "CloudWatch metrics", {})],
}

# Order providers are investigated in (most-to-least proximate to runtime).
_PROVIDER_ORDER = ["KUBERNETES", "PROMETHEUS", "GRAFANA", "DATADOG", "GITHUB", "JENKINS", "AZURE", "AWS"]

# Cap total tool reads per investigation to keep it bounded.
_MAX_STEPS = 14

# Signal keywords that hint at a likely root-cause area in read results.
_SIGNAL_WORDS = (
    "error", "fail", "crash", "oom", "restart", "unavailable", "timeout",
    "latency", "down", "alert", "incident", "500", "503", "throttl",
    "saturat", "pending", "evict", "could not",
)


class IncidentInvestigationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IncidentInvestigationRepository(session)
        self.step_repo = IncidentInvestigationStepRepository(session)
        self.event_repo = IncidentTimelineEventRepository(session)
        self.change_repo = DeploymentChangeEventRepository(session)
        self.rec_repo = IncidentRecommendationRepository(session)
        self.action_service = RemediationActionService(session)
        self.assign_repo = AITeamAgentToolRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.tool_service = AITeamToolService(session)
        self.runner = AITeamAgentRunner(session)

    # ------------------------------------------------------------- guards
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

    async def _resolve_default_team(self, organization_id: str):
        """Sprint 54B.1 — fall back to the org's default team when team_id omitted."""
        team_repo = AITeamRepository(self.session)
        team = await team_repo.get_default_for_org(organization_id)
        if team is None:
            raise NexoraException(
                "No team_id was provided and this organization has no default team. "
                "Complete onboarding (which provisions the default 'SRE Team') or pass "
                "an explicit team_id.",
                status_code=400,
            )
        return team

    # ------------------------------------------------------------- run
    async def investigate(
        self,
        data: IncidentInvestigateRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> IncidentDetailResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)

        if data.team_id:
            team = await get_ai_team_for_org(self.session, data.team_id, org_context)
        else:
            team = await self._resolve_default_team(organization_id)

        # Resolve the investigating agent (explicit, or the team's first active).
        if data.agent_id:
            agent = await get_ai_team_agent_for_org(self.session, data.agent_id, org_context)
            if agent.team_id != team.id:
                raise NexoraException("Agent does not belong to this team.", status_code=400)
        else:
            active = [a for a in team.agents if a.is_active]
            if not active:
                raise NexoraException(
                    "This team has no active agent to run the investigation.",
                    status_code=400,
                )
            agent = active[0]

        title = (data.title or "").strip() or self._derive_title(data.prompt)
        context = sanitize_payload(data.context) if data.context else {}

        investigation = await self.repo.create(
            organization_id=organization_id,
            team_id=team.id,
            agent_id=agent.id,
            title=title[:255],
            prompt=data.prompt,
            status=IncidentInvestigationStatus.RUNNING.value,
            created_by=current_user.id,
        )
        await self.audit_repo.log(
            action="incident_investigation_started",
            resource_type="incident_investigation",
            resource_id=investigation.id,
            user_id=current_user.id,
            details={"team_id": team.id, "agent_id": agent.id, "title": title[:120]},
        )

        # Only active tools assigned to the investigating agent are usable.
        assigned = await self.assign_repo.list_tools_for_agent(agent.id, organization_id)
        usable = [t for t in assigned if t.is_active and t.provider in INVESTIGATION_PLAN]
        # Deterministic, incident-oriented ordering.
        usable.sort(key=lambda t: _PROVIDER_ORDER.index(t.provider))

        steps_out: list = []
        step_order = 0
        try:
            for tool in usable:
                for action, _label, default_payload in INVESTIGATION_PLAN[tool.provider]:
                    if step_order >= _MAX_STEPS:
                        break
                    payload = {**default_payload, **(data.context or {})}
                    run = await self.tool_service.run_readonly_action(
                        tool=tool,
                        agent=agent,
                        action=action,
                        payload=payload or None,
                        current_user=current_user,
                        org_context=org_context,
                    )
                    completed = run.status == "COMPLETED"
                    step = await self.step_repo.create(
                        investigation_id=investigation.id,
                        organization_id=organization_id,
                        step_order=step_order,
                        tool_provider=tool.provider,
                        action=action,
                        status=(
                            IncidentInvestigationStepStatus.COMPLETED.value
                            if completed
                            else IncidentInvestigationStepStatus.FAILED.value
                        ),
                        result_summary=run.response_summary or run.error_message,
                        execution_time_ms=run.execution_time_ms,
                    )
                    steps_out.append(step)
                    step_order += 1
                if step_order >= _MAX_STEPS:
                    break

            # Sprint 40B — reconstruct a chronological timeline from the providers
            # the agent can read, persist it, and correlate the triggering change.
            providers = sorted({t.provider for t in usable})
            events_out = await self._collect_timeline(investigation, organization_id, providers)
            analysis = incident_correlation.correlate(events_out)

            # Sprint 40C — collect read-only deployment/change signals and correlate
            # the change most likely to have triggered the incident.
            changes_out = await self._collect_changes(investigation, organization_id, providers)
            change_analysis = change_intelligence.correlate_changes(
                changes_out, analysis.get("first_failure_at")
            )

            # Sprint 41A — generate ranked, recommendation-only remediation advice
            # from the RCA/timeline/change evidence. Nothing is ever executed.
            recommendations_out = await self._collect_recommendations(
                investigation,
                organization_id,
                timeline_events=events_out,
                change_analysis=change_analysis,
                timeline_confidence=analysis.get("confidence_score"),
            )

            # Sprint 41B — turn actionable recommendations into approval-gated
            # remediation actions. They are created PENDING_APPROVAL only; nothing
            # is ever executed without explicit human approval.
            actions_out = await self.action_service.generate_for_investigation(
                investigation=investigation,
                organization_id=organization_id,
                recommendations=recommendations_out,
                user_id=current_user.id,
                context=context,
            )

            report = await self._synthesize_report(data.prompt, agent, usable, steps_out)
            report = self._apply_correlation(report, events_out, analysis)
            investigation = await self.repo.update(
                investigation,
                status=IncidentInvestigationStatus.COMPLETED.value,
                summary=report["summary"],
                root_cause=report["root_cause"],
                recommendations=report["recommendations"],
                confidence_score=analysis["confidence_score"],
                suspected_trigger=analysis["suspected_trigger"],
                suspected_provider=analysis["suspected_provider"],
            )
            await self.audit_repo.log(
                action="incident_investigation_completed",
                resource_type="incident_investigation",
                resource_id=investigation.id,
                user_id=current_user.id,
                details={
                    "team_id": team.id,
                    "agent_id": agent.id,
                    "steps": len(steps_out),
                    "providers": sorted({s.tool_provider for s in steps_out}),
                    "timeline_events": len(events_out),
                    "change_events": len(changes_out),
                    "recommendations": len(recommendations_out),
                    "remediation_actions": len(actions_out),
                    "confidence_score": analysis["confidence_score"],
                    "suspected_provider": analysis["suspected_provider"],
                    "change_confidence": change_analysis["confidence_score"],
                },
            )
        except Exception as exc:  # noqa: BLE001 - never leak internals
            investigation = await self.repo.update(
                investigation,
                status=IncidentInvestigationStatus.FAILED.value,
                summary="The investigation could not be completed.",
            )
            await self.audit_repo.log(
                action="incident_investigation_failed",
                resource_type="incident_investigation",
                resource_id=investigation.id,
                user_id=current_user.id,
                details={"team_id": team.id, "agent_id": agent.id},
                status="failure",
            )
            await self.session.commit()
            logger.error("incident_investigation_failed", error=type(exc).__name__)
            raise NexoraException(
                "The investigation could not be completed.", status_code=502
            ) from exc

        await self.session.commit()
        logger.info(
            "incident_investigation_completed",
            investigation_id=investigation.id,
            steps=len(steps_out),
        )
        return self._to_detail(investigation, steps_out)

    # ------------------------------------------------------------- reads
    async def list_investigations(
        self, current_user: User, org_context: OrgContext, *, offset: int = 0, limit: int = 50
    ) -> IncidentListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.repo.list_for_org(
            organization_id, offset=offset, limit=limit
        )
        return IncidentListResponse(
            items=[IncidentResponse.model_validate(i) for i in items], total=total
        )

    async def get_investigation(
        self, investigation_id: str, current_user: User, org_context: OrgContext
    ) -> IncidentDetailResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        investigation = await self.repo.get_for_org(investigation_id, organization_id)
        if investigation is None:
            raise NexoraException("Investigation not found.", status_code=404)
        steps = await self.step_repo.list_for_investigation(investigation.id, organization_id)
        return self._to_detail(investigation, steps)

    async def get_timeline(
        self, investigation_id: str, current_user: User, org_context: OrgContext
    ) -> IncidentTimelineResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        investigation = await self.repo.get_for_org(investigation_id, organization_id)
        if investigation is None:
            raise NexoraException("Investigation not found.", status_code=404)
        steps = await self.step_repo.list_for_investigation(investigation.id, organization_id)
        events = await self.event_repo.list_for_investigation(investigation.id, organization_id)
        analysis = incident_correlation.correlate(events)
        return IncidentTimelineResponse(
            investigation_id=investigation.id,
            status=investigation.status,
            steps=[IncidentStepResponse.model_validate(s) for s in steps],
            timeline=[IncidentTimelineEventResponse.model_validate(e) for e in events],
            trigger_analysis=IncidentTriggerAnalysis(**analysis),
            confidence_score=analysis["confidence_score"],
        )

    async def get_changes(
        self, investigation_id: str, current_user: User, org_context: OrgContext
    ) -> IncidentChangesResponse:
        """Sprint 40C — deployment change intelligence for an incident."""
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        investigation = await self.repo.get_for_org(investigation_id, organization_id)
        if investigation is None:
            raise NexoraException("Investigation not found.", status_code=404)
        changes = await self.change_repo.list_for_investigation(investigation.id, organization_id)
        # Failure reference time comes from the 40B timeline (read-only recompute).
        events = await self.event_repo.list_for_investigation(investigation.id, organization_id)
        first_failure_at = incident_correlation.correlate(events).get("first_failure_at")
        result = change_intelligence.correlate_changes(changes, first_failure_at)
        suspected = (
            SuspectedChange(**result["suspected_change"])
            if result.get("suspected_change")
            else None
        )
        return IncidentChangesResponse(
            investigation_id=investigation.id,
            changes=[DeploymentChangeEventResponse.model_validate(c) for c in changes],
            suspected_change=suspected,
            confidence_score=result["confidence_score"],
            latest_commit=result.get("latest_commit"),
            latest_merge=result.get("latest_merge"),
            latest_release=result.get("latest_release"),
        )

    async def get_recommendations(
        self, investigation_id: str, current_user: User, org_context: OrgContext
    ) -> IncidentRecommendationsResponse:
        """Sprint 41A — ranked remediation recommendations (advisory only)."""
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        investigation = await self.repo.get_for_org(investigation_id, organization_id)
        if investigation is None:
            raise NexoraException("Investigation not found.", status_code=404)
        recs = await self.rec_repo.list_for_investigation(investigation.id, organization_id)
        return IncidentRecommendationsResponse(
            investigation_id=investigation.id,
            recommendations=[IncidentRecommendationResponse.model_validate(r) for r in recs],
        )

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _derive_title(prompt: str) -> str:
        first = (prompt or "").strip().splitlines()[0] if prompt.strip() else "Incident"
        return (first[:80] + "…") if len(first) > 80 else first or "Incident"

    @staticmethod
    def _findings(steps) -> list[str]:
        out = []
        for s in steps:
            text = (s.result_summary or "").strip() or "(no result)"
            out.append(f"{s.tool_provider} · {s.action}: {text}")
        return out

    async def _collect_timeline(self, investigation, organization_id: str, providers: list[str]):
        """Sprint 40B — collect read-only provider events and persist them.

        Events are reconstructed deterministically from the providers the agent
        can read (anchored to the investigation start). When a live integration
        is configured the same shape is produced from the connector's read-only
        event APIs. No secrets are read, logged, or stored.
        """
        base_time = investigation.created_at
        events = incident_correlation.build_events(providers, base_time)
        persisted = []
        for ev in events:
            row = await self.event_repo.create(
                investigation_id=investigation.id,
                organization_id=organization_id,
                provider=ev["provider"],
                event_type=ev["event_type"],
                event_timestamp=ev["event_timestamp"],
                title=ev["title"],
                description=ev["description"],
                severity=ev["severity"],
                event_metadata=ev["event_metadata"],
            )
            persisted.append(row)
        persisted.sort(key=lambda e: e.event_timestamp)
        return persisted

    async def _collect_changes(self, investigation, organization_id: str, providers: list[str]):
        """Sprint 40C — collect read-only deployment/change events and persist them.

        Captures what changed, when, who, and which version across Git/CI and
        the deploy platforms the agent can read. When a live integration is
        configured the same shape is produced from the connector's read-only
        APIs. No secrets are read, logged, or stored.
        """
        base_time = investigation.created_at
        changes = change_intelligence.build_changes(providers, base_time)
        persisted = []
        for ch in changes:
            row = await self.change_repo.create(
                investigation_id=investigation.id,
                organization_id=organization_id,
                provider=ch["provider"],
                change_type=ch["change_type"],
                change_timestamp=ch["change_timestamp"],
                actor=ch["actor"],
                title=ch["title"],
                description=ch["description"],
                version=ch["version"],
                event_metadata=ch["event_metadata"],
            )
            persisted.append(row)
        persisted.sort(key=lambda c: c.change_timestamp)
        return persisted

    async def _collect_recommendations(
        self,
        investigation,
        organization_id: str,
        *,
        timeline_events,
        change_analysis,
        timeline_confidence,
    ):
        """Sprint 41A — generate + persist ranked remediation recommendations.

        Advisory only: the engine analyzes the RCA/timeline/change evidence and
        suggests what to do next. The platform never executes, deploys, rolls
        back, scales, or mutates anything.
        """
        recs = remediation_recommendations.generate(
            timeline_events=timeline_events,
            change_analysis=change_analysis,
            timeline_confidence=timeline_confidence,
        )
        persisted = []
        for r in recs:
            row = await self.rec_repo.create(
                investigation_id=investigation.id,
                organization_id=organization_id,
                recommendation_type=r["recommendation_type"],
                title=r["title"],
                description=r["description"],
                risk_level=r["risk_level"],
                confidence_score=r["confidence_score"],
                estimated_recovery_minutes=r["estimated_recovery_minutes"],
                recommendation_order=r["recommendation_order"],
                event_metadata=r["event_metadata"],
            )
            persisted.append(row)
        persisted.sort(key=lambda x: x.recommendation_order)
        return persisted

    def _apply_correlation(self, report: dict, events, analysis: dict) -> dict:
        """Sprint 40B — extend the 40A RCA report with timeline/trigger/impact/confidence."""
        if not events:
            return report

        lines = [
            f"- {e.event_timestamp.strftime('%H:%M')} · {e.provider} · "
            f"[{e.severity}] {e.title}"
            for e in events
        ]
        timeline_section = "### Timeline\n" + "\n".join(lines)

        if analysis["suspected_trigger"]:
            trigger_section = (
                "### Trigger Analysis\n"
                f"Most likely initiating change: {analysis['suspected_trigger']} "
                f"({analysis['suspected_provider']}).\n{analysis['reason']}"
            )
            # Prefer the correlation-derived root cause when a trigger is found.
            report["root_cause"] = (
                f"Most likely trigger: {analysis['suspected_trigger']} "
                f"({analysis['suspected_provider']}). {analysis['reason']} "
                f"Confidence: {analysis['confidence_score']}%."
            )
        else:
            trigger_section = (
                "### Trigger Analysis\n"
                "No initiating change could be correlated from the collected events."
            )

        impacted = analysis["impacted_systems"]
        impact_section = "### Impact Analysis\n" + (
            f"Affected systems: {', '.join(impacted)}." if impacted
            else "No downstream failures or alerts were correlated."
        )

        confidence_section = (
            "### Confidence Score\n"
            f"{analysis['confidence_score']}% — {analysis['reason']}"
        )

        report["summary"] = "\n\n".join(
            [report["summary"], timeline_section, trigger_section, impact_section, confidence_section]
        )
        return report

    async def _synthesize_report(self, prompt, agent, usable_tools, steps) -> dict:
        providers = sorted({s.tool_provider for s in steps})
        ok = sum(1 for s in steps if s.status == "COMPLETED")
        failed = sum(1 for s in steps if s.status != "COMPLETED")
        findings = self._findings(steps)

        if not steps:
            summary = (
                f'Investigated "{prompt.strip()}". No connected read-only tools are '
                "assigned to the investigating agent, so no live evidence could be "
                "collected."
            )
            root_cause = (
                "No root cause could be determined — the agent has no investigation "
                "tools connected (Kubernetes, Prometheus, Grafana, Datadog, GitHub, "
                "Azure, or AWS)."
            )
            recommendations = (
                "Connect read-only tools to this agent (Settings → AI Tools) and "
                "re-run the investigation. No changes were made to any system."
            )
            return {"summary": summary, "root_cause": root_cause, "recommendations": recommendations}

        summary = (
            f'Investigated "{prompt.strip()}". Ran {len(steps)} read-only check(s) '
            f"across {len(providers)} system(s): {', '.join(providers)}. "
            f"{ok} succeeded, {failed} could not complete."
        )

        # Correlate: surface the strongest signal among the collected results.
        signal_step = None
        for s in steps:
            blob = f"{s.result_summary or ''}".lower()
            if s.status != "COMPLETED" or any(w in blob for w in _SIGNAL_WORDS):
                signal_step = s
                break
        if signal_step is not None:
            root_cause = (
                f"The evidence most strongly implicates {signal_step.tool_provider} "
                f"({signal_step.action}). Observed: "
                f"{(signal_step.result_summary or 'the check did not complete').strip()} "
                "Correlate this signal with the timeline below to confirm the failing "
                "component before any remediation."
            )
        else:
            root_cause = (
                "No single definitive root cause was isolated from the read-only "
                "evidence collected. The signals did not point to one failing "
                "component — widen the time window or connect additional tools "
                "(metrics, logs, recent releases) for deeper correlation."
            )

        recs: list[str] = []
        if "KUBERNETES" in providers:
            recs.append(
                "Review pod restart counts and recent deployment/rollout events in the "
                "affected namespace."
            )
        if any(p in providers for p in ("PROMETHEUS", "GRAFANA", "DATADOG")):
            recs.append(
                "Correlate the error spike with latency/saturation metrics and active "
                "monitors around the incident start time."
            )
        if "GITHUB" in providers:
            recs.append(
                "Inspect the most recent release and CI workflow runs preceding the "
                "incident for a likely regression."
            )
        if any(p in providers for p in ("AZURE", "AWS")):
            recs.append(
                "Check platform diagnostics / CloudWatch alarms for infrastructure-level "
                "faults (capacity, networking, dependencies)."
            )
        recs.append(
            "This was a read-only investigation — no changes were made. Validate the "
            "suspected cause before taking any remediation action."
        )
        recommendations = "\n".join(f"- {r}" for r in recs)

        # Enrich the summary with an AI narrative when an LLM is configured. This
        # never overrides the deterministic RCA fields (keeps behavior testable
        # offline) — it augments the human-readable summary.
        narrative = await self._ai_narrative(prompt, agent, findings)
        if narrative:
            summary = f"{summary}\n\nAI analysis:\n{narrative}"

        return {"summary": summary, "root_cause": root_cause, "recommendations": recommendations}

    async def _ai_narrative(self, prompt, agent, findings) -> str | None:
        evidence = "\n".join(f"- {f}" for f in findings) or "(no evidence collected)"
        instructions = (
            (agent.instructions or "You are an incident investigator.").strip()
            + "\n\nYou are performing a READ-ONLY incident investigation. Using only the "
            "evidence provided, write a concise root cause analysis. Do not suggest or "
            "perform any changes, deployments, or mutations."
        )
        analysis_prompt = (
            f"Incident: {prompt.strip()}\n\n"
            f"Read-only evidence collected from connected tools:\n{evidence}\n\n"
            "Provide a short analysis: the most likely root cause and why."
        )
        try:
            text = await self.runner.run(
                instructions=instructions,
                prompt=analysis_prompt,
                model=agent.model,
                temperature=min(agent.temperature, 0.4),
                max_tokens=min(agent.max_tokens, 600),
                organization_id=getattr(agent, "organization_id", None),
            )
            return (text or "").strip() or None
        except Exception:  # noqa: BLE001 - narrative is best-effort
            logger.warning("incident_ai_narrative_skipped")
            return None

    def _to_detail(self, investigation, steps) -> IncidentDetailResponse:
        detail = IncidentDetailResponse.model_validate(investigation)
        detail.findings = self._findings(steps)
        detail.steps = [IncidentStepResponse.model_validate(s) for s in steps]
        return detail
