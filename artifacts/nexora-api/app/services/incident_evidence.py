"""Incident operational evidence — logs, metrics, and CI build context for triage."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.delivery.pipelines.jenkins_live import fetch_build_console_excerpt
from app.models.user import User
from app.repositories.incident import IncidentInvestigationRepository, MonitoringAlertRepository
from app.repositories.integration import IntegrationConnectionRepository
from app.security.secrets.service import SecretManagerService
from app.services.observability_platform import ObservabilityPlatformService
from app.tenancy.permissions import can_read_ai_teams


def _service_query(investigation, alerts: list) -> str:
    for alert in alerts:
        if alert.service:
            return str(alert.service)
    title = (investigation.title or "").strip()
    if title.startswith("[") and "]" in title:
        title = title.split("]", 1)[1].strip()
    return title[:120] or "error"


def _jenkins_context_from_alert(alert) -> dict | None:
    if (alert.provider or "").upper() != "JENKINS":
        return None
    labels = alert.labels or {}
    annotations = alert.annotations or {}
    job = labels.get("job") or alert.service
    build_number = labels.get("build_number")
    if not build_number and alert.alert_id and "#" in alert.alert_id:
        build_number = alert.alert_id.split("#", 1)[1]
    if not job or not build_number:
        return None
    return {
        "provider": "JENKINS",
        "job": job,
        "build_number": build_number,
        "url": annotations.get("url"),
        "result": labels.get("result"),
    }


class IncidentEvidenceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.investigations = IncidentInvestigationRepository(session)
        self.alerts = MonitoringAlertRepository(session)
        self.connections = IntegrationConnectionRepository(session)
        self.secrets = SecretManagerService(session)
        self.obs = ObservabilityPlatformService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()
        return org_context.requires_organization

    async def get_evidence(
        self,
        investigation_id: str,
        user: User,
        org_context: OrgContext,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        investigation = await self.investigations.get_for_org(investigation_id, organization_id)
        if investigation is None:
            raise NexoraException("Investigation not found.", status_code=404)

        recent, _ = await self.alerts.list_for_org(organization_id, limit=300)
        linked = [a for a in recent if a.incident_id == investigation_id]
        query = _service_query(investigation, linked)

        logs: dict | None = None
        metrics: list[dict] = []
        build_context: dict | None = None

        try:
            logs = await self.obs.search_logs(user, org_context, query=query, limit=25)
        except Exception:  # noqa: BLE001 — evidence is best-effort
            logs = {"entries": [], "total": 0, "source": "unavailable", "query": query}

        try:
            metrics = await self.obs.top_metrics(user, org_context)
        except Exception:  # noqa: BLE001
            metrics = []

        jenkins_hint = None
        for alert in linked:
            jenkins_hint = _jenkins_context_from_alert(alert)
            if jenkins_hint:
                break
        if jenkins_hint is None and (investigation.suspected_provider or "").upper() == "JENKINS":
            jenkins_hint = {"provider": "JENKINS", "job": query, "build_number": None}

        if jenkins_hint and jenkins_hint.get("build_number"):
            build_context = await self._jenkins_build_context(
                organization_id, user, org_context, jenkins_hint,
            )

        return {
            "investigation_id": investigation_id,
            "service": query,
            "suspected_provider": investigation.suspected_provider,
            "linked_alerts": len(linked),
            "logs": logs,
            "metrics": metrics[:8],
            "build_context": build_context,
        }

    async def _jenkins_build_context(
        self,
        organization_id: str,
        user: User,
        org_context: OrgContext,
        hint: dict,
    ) -> dict:
        conns = await self.connections.list_for_org(organization_id)
        jenkins = next(
            (c for c in conns if (c.integration_key or "").upper() == "JENKINS" and c.credential_id),
            None,
        )
        if jenkins is None:
            return {**hint, "available": False, "reason": "No Jenkins connection with credentials"}
        try:
            _, secret = await self.secrets.resolve_secret(
                jenkins.credential_id,
                user=user,
                org_context=org_context,
                reason="incident build console excerpt",
            )
        except Exception as exc:  # noqa: BLE001
            return {**hint, "available": False, "reason": str(exc)[:200]}
        excerpt = await asyncio.to_thread(
            fetch_build_console_excerpt,
            secret,
            hint["job"],
            hint["build_number"],
            max_chars=4000,
        )
        return {**hint, **excerpt, "connection_name": jenkins.name}
