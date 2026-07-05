"""Sprint 47B - Integration Marketplace API.

* GET    /v1/integrations                   - supported + connected integrations
* POST   /v1/integrations/connect           - connect an integration (encrypted creds)
* POST   /v1/integrations/verify            - read-only connectivity/permission check
* GET    /v1/integrations/connections       - list connections (status/health/sync)
* DELETE /v1/integrations/connections/{id}  - disconnect (revoke credential)

Org-scoped & audited. Secrets are stored only as the 35A AES-256-GCM envelope and
never returned. Verification is strictly read-only.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.integration import (
    ConnectionView,
    ConnectRequest,
    HealthBoardRow,
    MarketplaceResponse,
    SyncResponse,
    UpdateConnectionCredentialsRequest,
    VerifyRequest,
    VerifyResponse,
)
from app.services.integration_health_board import IntegrationHealthBoardService
from app.services.integration_marketplace import IntegrationMarketplaceService
from app.services.integration_sync import IntegrationSyncService

router = APIRouter(prefix="/integrations", tags=["Integration Marketplace"])


@router.get("", response_model=MarketplaceResponse)
async def list_integrations(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IntegrationMarketplaceService(session).list_marketplace(current_user, org_context)


@router.post("/connect", response_model=ConnectionView, status_code=status.HTTP_201_CREATED)
async def connect_integration(
    payload: ConnectRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IntegrationMarketplaceService(session).connect(current_user, org_context, payload)


@router.post("/verify", response_model=VerifyResponse)
async def verify_integration(
    payload: VerifyRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IntegrationMarketplaceService(session).verify(current_user, org_context, payload)


@router.get("/connections", response_model=list[ConnectionView])
async def list_connections(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IntegrationMarketplaceService(session).list_connections(current_user, org_context)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    await IntegrationMarketplaceService(session).disconnect(current_user, org_context, connection_id)


@router.put("/connections/{connection_id}/credentials", response_model=ConnectionView)
async def update_connection_credentials(
    connection_id: str,
    payload: UpdateConnectionCredentialsRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await IntegrationMarketplaceService(session).update_connection_credentials(
        current_user, org_context, connection_id, payload,
    )


@router.get("/connections/health-board", response_model=list[HealthBoardRow])
async def integration_health_board(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    rows = await IntegrationHealthBoardService(session).list_board(current_user, org_context)
    return [HealthBoardRow(**r) for r in rows]


@router.post("/connections/{connection_id}/sync", response_model=SyncResponse)
async def sync_integration_connection(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    result = await IntegrationSyncService(session).sync_connection(
        current_user, org_context, connection_id, sync_runs=True,
    )
    await session.commit()
    return SyncResponse(**result)


# ------------------------------------------------------------------ Sprint 65G
from app.schemas.integration_readiness import (
    CapabilitiesView,
    ConnectionReadinessView,
    ExpiryAckRequest,
    ExpiryReminderView,
    ExpirySnoozeRequest,
    HealthHistoryEntry,
    HealthView,
    IntegrationDashboard,
    ProviderSummary,
    TestNotificationRequest,
    ValidateResponse,
)
from app.services.integration_readiness import IntegrationReadinessService


def _readiness(session: DBSession) -> IntegrationReadinessService:
    return IntegrationReadinessService(session)


@router.get("/providers", response_model=list[ProviderSummary])
async def list_integration_providers(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _readiness(session).list_providers(current_user, org_context)


@router.get("/connections/readiness", response_model=list[ConnectionReadinessView])
async def list_readiness_connections(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    state: str | None = None,
):
    return await _readiness(session).list_connections(current_user, org_context, state=state)


@router.post("/connections/{connection_id}/validate", response_model=ValidateResponse)
async def validate_connection(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).validate_connection(current_user, org_context, connection_id)


@router.get("/connections/{connection_id}/capabilities", response_model=CapabilitiesView)
async def get_connection_capabilities(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).get_capabilities(current_user, org_context, connection_id)


@router.get("/connections/{connection_id}/health", response_model=HealthView)
async def get_connection_health(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).get_health(current_user, org_context, connection_id)


@router.get("/connections/{connection_id}/history", response_model=list[HealthHistoryEntry])
async def get_connection_history(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).get_history(current_user, org_context, connection_id)


@router.get("/connections/{connection_id}/expiry", response_model=list[ExpiryReminderView])
async def get_connection_expiry(
    connection_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).get_expiry(current_user, org_context, connection_id)


@router.post("/connections/{connection_id}/acknowledge-expiry")
async def acknowledge_connection_expiry(
    connection_id: str,
    payload: ExpiryAckRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).acknowledge_expiry(
        current_user, org_context, connection_id, payload.reminder_id,
    )


@router.post("/connections/{connection_id}/snooze-expiry")
async def snooze_connection_expiry(
    connection_id: str,
    payload: ExpirySnoozeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).snooze_expiry(
        current_user, org_context, connection_id,
        reminder_id=payload.reminder_id, days=payload.days,
    )


@router.get("/dashboard", response_model=IntegrationDashboard)
async def integration_dashboard(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    return await _readiness(session).get_dashboard(current_user, org_context)


@router.post("/notifications/test")
async def test_integration_notification(
    payload: TestNotificationRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await _readiness(session).test_notification(
        current_user, org_context, channel=payload.channel, dry_run=payload.dry_run,
    )
