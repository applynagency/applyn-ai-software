"""Sprint 46D - AI Incident War Room API.

* POST /v1/war-rooms              - convene a war room (optionally linked to an incident)
* GET  /v1/war-rooms              - list war rooms
* GET  /v1/war-rooms/{id}         - full room (messages, consensus RCA, remediation plan)
* POST /v1/war-rooms/{id}/execute - run the multi-agent discussion -> consensus -> AWAITING_APPROVAL

Advisory only: the war room never executes remediation and always requires human
approval. Read-only over existing incident intelligence; org-scoped and audited.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.war_room import WarRoomCreate, WarRoomResponse, WarRoomSummary
from app.services.war_room import WarRoomService

router = APIRouter(prefix="/war-rooms", tags=["AI Incident War Room"])


@router.post("", response_model=WarRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_war_room(
    payload: WarRoomCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomService(session).create(
        current_user, org_context, incident_id=payload.incident_id, title=payload.title
    )


@router.get("", response_model=list[WarRoomSummary])
async def list_war_rooms(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    rows = await WarRoomService(session).list(current_user, org_context)
    return [WarRoomSummary.model_validate(r) for r in rows]


@router.get("/{war_room_id}", response_model=WarRoomResponse)
async def get_war_room(
    war_room_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomService(session).get(current_user, org_context, war_room_id)


@router.post("/{war_room_id}/execute", response_model=WarRoomResponse)
async def execute_war_room(
    war_room_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomService(session).execute(current_user, org_context, war_room_id)
