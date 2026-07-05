"""Collaborative War Room API — real-time incident response.

REST surface (org-scoped, audited):
* POST   /v1/war-rooms/{id}/join                       - join (presence on)
* POST   /v1/war-rooms/{id}/leave                      - leave
* GET    /v1/war-rooms/{id}/participants               - participants + presence
* GET    /v1/war-rooms/{id}/presence                   - online + roster snapshot
* GET    /v1/war-rooms/{id}/messages                   - live messages (or a thread)
* POST   /v1/war-rooms/{id}/messages                   - post a live message (broadcast)
* GET    /v1/war-rooms/{id}/messages/{mid}/thread      - replies under a message
* POST   /v1/war-rooms/{id}/ai                         - invite an AI participant
* POST   /v1/war-rooms/{id}/uploads                    - upload a file
* GET    /v1/war-rooms/{id}/uploads                    - list attachments
* GET    /v1/war-rooms/{id}/uploads/{aid}              - download an attachment
* POST   /v1/war-rooms/{id}/evidence                   - pin evidence
* GET    /v1/war-rooms/{id}/evidence                   - list evidence
* POST   /v1/war-rooms/{id}/approvals                  - request an approval
* GET    /v1/war-rooms/{id}/approvals                  - list approvals
* POST   /v1/war-rooms/{id}/approvals/{aid}/decision   - approve / reject

Real-time channel:
* WS     /v1/war-rooms/{id}/ws?token=<access_token>    - live bidirectional feed

The room is advisory only: it never executes remediation; humans always decide.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    File,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from jose import JWTError

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.core.config import settings
from app.core.security import decode_token
from app.database.session import AsyncSessionLocal
from app.models.organization import OrganizationRole
from app.realtime import manager
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.user import UserRepository
from app.schemas.war_room_collab import (
    AIPromptRequest,
    ApprovalCreate,
    ApprovalDecision,
    ApprovalView,
    AttachmentView,
    EvidenceCreate,
    EvidenceView,
    LiveMessageCreate,
    LiveMessageView,
    ParticipantView,
    PresenceView,
)
from app.services.war_room_collab import WarRoomCollabService

router = APIRouter(prefix="/war-rooms", tags=["War Room Collaboration"])


# ============================================================ REST endpoints
@router.post("/{war_room_id}/join", response_model=ParticipantView)
async def join_war_room(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await WarRoomCollabService(session).join(current_user, org_context, war_room_id)


@router.post("/{war_room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_war_room(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await WarRoomCollabService(session).leave(current_user, org_context, war_room_id)


@router.get("/{war_room_id}/participants", response_model=list[ParticipantView])
async def list_participants(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await WarRoomCollabService(session).list_participants(current_user, org_context, war_room_id)


@router.get("/{war_room_id}/presence", response_model=PresenceView)
async def get_presence(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await WarRoomCollabService(session).presence(current_user, org_context, war_room_id)


@router.get("/{war_room_id}/messages", response_model=list[LiveMessageView])
async def list_messages(
    war_room_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    parent_message_id: str | None = Query(default=None),
):
    return await WarRoomCollabService(session).list_messages(
        current_user, org_context, war_room_id, parent_message_id=parent_message_id
    )


@router.post("/{war_room_id}/messages", response_model=LiveMessageView, status_code=status.HTTP_201_CREATED)
async def post_message(
    war_room_id: str,
    payload: LiveMessageCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomCollabService(session).post_message(
        current_user, org_context, war_room_id, payload
    )


@router.get("/{war_room_id}/messages/{message_id}/thread", response_model=list[LiveMessageView])
async def list_thread(
    war_room_id: str,
    message_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomCollabService(session).list_thread(
        current_user, org_context, war_room_id, message_id
    )


@router.post("/{war_room_id}/ai", response_model=LiveMessageView, status_code=status.HTTP_201_CREATED)
async def invite_ai(
    war_room_id: str,
    payload: AIPromptRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomCollabService(session).ai_respond(
        current_user, org_context, war_room_id, payload.prompt,
        parent_message_id=payload.parent_message_id,
    )


@router.post("/{war_room_id}/uploads", response_model=AttachmentView, status_code=status.HTTP_201_CREATED)
async def upload_file(
    war_room_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    file: UploadFile = File(...),
    message_id: str | None = Query(default=None),
):
    return await WarRoomCollabService(session).save_upload(
        current_user, org_context, war_room_id, file, message_id=message_id
    )


@router.get("/{war_room_id}/uploads", response_model=list[AttachmentView])
async def list_uploads(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await WarRoomCollabService(session).list_attachments(current_user, org_context, war_room_id)


@router.get("/{war_room_id}/uploads/{attachment_id}")
async def download_upload(
    war_room_id: str,
    attachment_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    att = await WarRoomCollabService(session).get_attachment(
        current_user, org_context, war_room_id, attachment_id
    )
    return FileResponse(att.storage_path, media_type=att.content_type, filename=att.filename)


@router.post("/{war_room_id}/evidence", response_model=EvidenceView, status_code=status.HTTP_201_CREATED)
async def add_evidence(
    war_room_id: str,
    payload: EvidenceCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomCollabService(session).add_evidence(
        current_user, org_context, war_room_id, payload
    )


@router.get("/{war_room_id}/evidence", response_model=list[EvidenceView])
async def list_evidence(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await WarRoomCollabService(session).list_evidence(current_user, org_context, war_room_id)


@router.post("/{war_room_id}/approvals", response_model=ApprovalView, status_code=status.HTTP_201_CREATED)
async def request_approval(
    war_room_id: str,
    payload: ApprovalCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomCollabService(session).request_approval(
        current_user, org_context, war_room_id, payload
    )


@router.get("/{war_room_id}/approvals", response_model=list[ApprovalView])
async def list_approvals(
    war_room_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await WarRoomCollabService(session).list_approvals(current_user, org_context, war_room_id)


@router.post("/{war_room_id}/approvals/{approval_id}/decision", response_model=ApprovalView)
async def decide_approval(
    war_room_id: str,
    approval_id: str,
    payload: ApprovalDecision,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await WarRoomCollabService(session).decide_approval(
        current_user, org_context, war_room_id, approval_id, payload
    )


# ============================================================ WebSocket
async def _authenticate_ws(token: str | None):
    """Resolve (user, OrgContext) from an access token, or None when invalid.

    WebSockets can't use the HTTP bearer dependency, so this mirrors
    ``get_current_user`` + ``get_org_context`` manually.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    if settings.JWT_DENYLIST_ENABLED:
        from app.redis import denylist

        if await denylist.is_revoked(payload.get("jti", "")):
            return None

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(user_id)
        if not user or not user.is_active:
            return None
        org_id = payload.get("organization_id")
        role: OrganizationRole | None = None
        if org_id:
            if user.is_superuser:
                role_value = payload.get("role")
                if role_value:
                    try:
                        role = OrganizationRole(str(role_value))
                    except ValueError:
                        role = None
            else:
                membership = await OrganizationMemberRepository(session).get_membership(
                    str(org_id), user.id
                )
                if membership is None:
                    return None
                role = membership.role
        org_context = OrgContext(
            user=user, organization_id=str(org_id) if org_id else None, role=role
        )
    return user, org_context


async def _broadcast_presence(war_room_id: str) -> None:
    await manager.broadcast(
        war_room_id,
        {"type": "presence", "war_room_id": war_room_id,
         "data": {"online": manager.presence(war_room_id)}},
    )


async def _handle_frame(frame: dict, war_room_id: str, user, org_context, websocket: WebSocket) -> None:
    kind = (frame or {}).get("type")
    if kind == "ping":
        await websocket.send_json({"type": "pong"})
        return
    if kind == "typing":
        await manager.broadcast(war_room_id, {
            "type": "typing", "war_room_id": war_room_id,
            "data": {"user_id": user.id, "user_name": user.full_name or user.username,
                     "is_typing": bool(frame.get("is_typing", True))},
        })
        return
    if kind == "presence":
        await _broadcast_presence(war_room_id)
        return
    if kind == "message":
        payload = LiveMessageCreate(
            content=frame.get("content", ""),
            message_type=frame.get("message_type", "INFO"),
            parent_message_id=frame.get("parent_message_id"),
            mentions=frame.get("mentions", []) or [],
        )
        async with AsyncSessionLocal() as session:
            await WarRoomCollabService(session).post_message(
                user, org_context, war_room_id, payload
            )
        return
    if kind == "ai":
        prompt = frame.get("prompt", "")
        agent = (frame.get("agent") or "COPILOT")
        parent = frame.get("parent_message_id")

        async def on_chunk(chunk: str) -> None:
            await manager.broadcast(war_room_id, {
                "type": "ai_token", "war_room_id": war_room_id,
                "data": {"agent": agent, "chunk": chunk},
            })

        async with AsyncSessionLocal() as session:
            await WarRoomCollabService(session).ai_respond(
                user, org_context, war_room_id, prompt,
                parent_message_id=parent, agent=agent, on_chunk=on_chunk,
            )
        return
    await websocket.send_json({"type": "error", "data": {"detail": f"unknown frame type: {kind}"}})


@router.websocket("/{war_room_id}/ws")
async def war_room_ws(websocket: WebSocket, war_room_id: str):
    if not settings.WAR_ROOM_REALTIME_ENABLED:
        await websocket.close(code=4503)
        return

    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]

    auth = await _authenticate_ws(token)
    if auth is None:
        await websocket.close(code=4401)
        return
    user, org_context = auth

    await websocket.accept()

    # Validate room + read permission, and register the human as a participant.
    try:
        async with AsyncSessionLocal() as session:
            await WarRoomCollabService(session).join(user, org_context, war_room_id)
    except Exception as exc:  # noqa: BLE001 - report and close
        await websocket.send_json({"type": "error", "data": {"detail": str(exc)}})
        await websocket.close(code=4404)
        return

    conn_id = await manager.connect(
        war_room_id, websocket, user_id=user.id,
        user_name=user.full_name or user.username,
        role=org_context.role.value if org_context.role else None,
    )

    try:
        # Send an initial snapshot to the joining socket.
        async with AsyncSessionLocal() as session:
            svc = WarRoomCollabService(session)
            messages = await svc.list_messages(user, org_context, war_room_id)
            participants = await svc.list_participants(user, org_context, war_room_id)
        await websocket.send_json({
            "type": "connected", "war_room_id": war_room_id,
            "data": {
                "user_id": user.id,
                "messages": [m.model_dump(mode="json") for m in messages],
                "participants": [p.model_dump(mode="json") for p in participants],
                "online": manager.presence(war_room_id),
            },
        })
        await _broadcast_presence(war_room_id)

        while True:
            frame = await websocket.receive_json()
            try:
                await _handle_frame(frame, war_room_id, user, org_context, websocket)
            except Exception as exc:  # noqa: BLE001 - keep the socket alive
                await websocket.send_json({"type": "error", "data": {"detail": str(exc)}})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(war_room_id, conn_id)
        try:
            async with AsyncSessionLocal() as session:
                await WarRoomCollabService(session).touch_presence(
                    org_context.organization_id, war_room_id, user.id
                )
        except Exception:  # noqa: BLE001 - best effort
            pass
        await _broadcast_presence(war_room_id)
