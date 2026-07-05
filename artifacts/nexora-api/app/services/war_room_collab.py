"""Collaborative incident response engine for the War Room.

Turns the (advisory, deterministic) AI war room into a real-time collaboration
space shared by humans and AI specialists:

* live messages with threads and @mentions (mentioning an AI agent invites it to
  respond — grounded, cited, hallucination-proof, reusing the Copilot's
  deterministic evidence provider)
* human participants with presence + typing indicators (transport in
  ``app.realtime``)
* file uploads and pinned evidence
* war-room-scoped approvals (advisory only — humans always decide)

Every state change is broadcast to all connected sockets (and, when Redis is
configured, across workers) so every participant sees updates live. Org-scoped
and audited throughout; the room never executes remediation.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NexoraException
from app.database.base import utcnow
from app.models.war_room import (
    WarRoomAgent,
    WarRoomApprovalStatus,
    WarRoomAuthorType,
)
from app.realtime import manager
from app.repositories.audit import AuditLogRepository
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.user import UserRepository
from app.repositories.war_room import WarRoomMessageRepository, WarRoomRepository
from app.repositories.war_room_collab import (
    WarRoomApprovalRepository,
    WarRoomAttachmentRepository,
    WarRoomEvidenceRepository,
    WarRoomParticipantRepository,
)
from app.schemas.war_room_collab import (
    ApprovalView,
    AttachmentView,
    EvidenceView,
    LiveMessageView,
    ParticipantView,
    PresenceUser,
    PresenceView,
)
from app.services.grounded_copilot.evidence import EvidenceProvider
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

# AI agents that can be @mentioned to join the conversation.
_AI_AGENTS = {a.value for a in WarRoomAgent} | {"COPILOT", "AI"}


def _now() -> datetime:
    return datetime.now(UTC)


class WarRoomCollabService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.room_repo = WarRoomRepository(session)
        self.msg_repo = WarRoomMessageRepository(session)
        self.participant_repo = WarRoomParticipantRepository(session)
        self.attachment_repo = WarRoomAttachmentRepository(session)
        self.evidence_repo = WarRoomEvidenceRepository(session)
        self.approval_repo = WarRoomApprovalRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.user_repo = UserRepository(session)

    # ------------------------------------------------------------- guards
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_decide(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError("Approving or rejecting requires elevated permissions.")

    async def _load_room(self, organization_id: str, room_id: str):
        room = await self.room_repo.get_for_org(room_id, organization_id)
        if room is None:
            raise NexoraException("War room not found.", status_code=404)
        return room

    # ------------------------------------------------------------- broadcast
    async def _broadcast(self, room_id: str, event_type: str, data: dict) -> None:
        await manager.broadcast(
            room_id,
            {"type": event_type, "war_room_id": room_id, "data": data, "ts": _now().isoformat()},
        )

    # ------------------------------------------------------------- views
    @staticmethod
    def _message_view(msg) -> LiveMessageView:
        return LiveMessageView.model_validate(msg)

    @staticmethod
    def _attachment_view(att) -> AttachmentView:
        return AttachmentView.model_validate(att)

    @staticmethod
    def _evidence_view(ev) -> EvidenceView:
        return EvidenceView.model_validate(ev)

    @staticmethod
    def _approval_view(ap) -> ApprovalView:
        return ApprovalView.model_validate(ap)

    @staticmethod
    def _participant_view(p, online_ids: set[str]) -> ParticipantView:
        return ParticipantView(
            user_id=p.user_id, user_name=p.user_name, role=p.role,
            is_active=p.is_active, online=p.user_id in online_ids,
            last_seen_at=p.last_seen_at, created_at=p.created_at,
        )

    # ------------------------------------------------------------- mentions
    async def _resolve_mentions(
        self, organization_id: str, tokens: list[str], content: str
    ) -> list[dict]:
        """Resolve mention tokens (user id / username / agent name) to targets.

        Returns ``[{"type": "user"|"agent", "id", "label"}]``. Unknown tokens are
        dropped (no dangling mentions). Agent mentions invite an AI specialist to
        respond.
        """
        resolved: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for raw in tokens or []:
            token = (raw or "").strip().lstrip("@")
            if not token:
                continue
            upper = token.upper()
            if upper in _AI_AGENTS:
                key = ("agent", upper)
                if key not in seen:
                    seen.add(key)
                    resolved.append({"type": "agent", "id": upper, "label": upper})
                continue
            # Human: accept user id or username, but only org members.
            user = await self.user_repo.get_by_id(token)
            if user is None:
                user = await self.user_repo.get_by_username(token)
            if user is None:
                continue
            membership = await self.member_repo.get_membership(organization_id, user.id)
            if membership is None:
                continue
            key = ("user", user.id)
            if key not in seen:
                seen.add(key)
                resolved.append({
                    "type": "user", "id": user.id,
                    "label": user.full_name or user.username,
                })
        return resolved

    async def _validate_parent(self, room, parent_message_id: str | None):
        if not parent_message_id:
            return None
        parent = await self.msg_repo.get_for_room(
            parent_message_id, room.id, room.organization_id
        )
        if parent is None:
            raise NexoraException("Parent message not found in this war room.", status_code=404)
        # Replies attach to the thread root (one level of nesting).
        return parent.parent_message_id or parent.id

    # ------------------------------------------------------------- messages
    async def _persist_message(
        self, room, *, author_type: str, agent: str, content: str, message_type: str,
        user_id: str | None = None, user_name: str | None = None,
        parent_message_id: str | None = None, mentions: list[dict] | None = None,
        confidence: int | None = None, citations: list | None = None,
    ):
        # Concurrency-safe sequencing: MAX(sequence)+1 then insert can collide
        # when two participants post at once. The (war_room_id, sequence) unique
        # constraint rejects the loser; retry with a freshly computed sequence.
        attempts = 0
        while True:
            attempts += 1
            seq = await self.msg_repo.next_sequence(room.id, room.organization_id)
            try:
                async with self.session.begin_nested():
                    msg = await self.msg_repo.create(
                        war_room_id=room.id, organization_id=room.organization_id,
                        agent=agent, message_type=message_type, content=content,
                        confidence=confidence, citations=citations or [], sequence=seq,
                        author_type=author_type, user_id=user_id, user_name=user_name,
                        parent_message_id=parent_message_id, mentions=mentions or [],
                    )
                break
            except IntegrityError:
                if attempts >= 5:
                    raise
        room.message_count = (room.message_count or 0) + 1
        await self.session.flush()
        return msg

    async def post_message(self, user, org_context, room_id: str, payload) -> LiveMessageView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        parent_id = await self._validate_parent(room, payload.parent_message_id)
        mentions = await self._resolve_mentions(organization_id, payload.mentions, payload.content)

        user_name = user.full_name or user.username
        msg = await self._persist_message(
            room, author_type=WarRoomAuthorType.HUMAN.value, agent="HUMAN",
            content=payload.content, message_type=payload.message_type,
            user_id=user.id, user_name=user_name,
            parent_message_id=parent_id, mentions=mentions,
        )
        await self.audit_repo.log(
            action="war_room_message_posted", resource_type="war_room",
            resource_id=room.id, user_id=user.id,
            details={"organization_id": organization_id, "message_id": msg.id,
                     "mentions": len(mentions)},
        )
        await self.session.commit()
        view = self._message_view(msg)
        await self._broadcast(room.id, "message", view.model_dump(mode="json"))

        # @mentioning an AI agent invites it to respond, grounded + cited.
        for target in mentions:
            if target["type"] == "agent":
                await self.ai_respond(
                    user, org_context, room.id, payload.content,
                    parent_message_id=msg.id, agent=target["id"],
                )
        return view

    async def list_messages(
        self, user, org_context, room_id: str, *, parent_message_id: str | None = None
    ) -> list[LiveMessageView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        if parent_message_id:
            rows = await self.msg_repo.list_thread(parent_message_id, organization_id)
        else:
            rows = await self.msg_repo.list_for_room(room.id, organization_id)
        return [self._message_view(m) for m in rows]

    async def list_thread(self, user, org_context, room_id: str, message_id: str) -> list[LiveMessageView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        root = await self.msg_repo.get_for_room(message_id, room.id, organization_id)
        if root is None:
            raise NexoraException("Message not found in this war room.", status_code=404)
        root_id = root.parent_message_id or root.id
        replies = await self.msg_repo.list_thread(root_id, organization_id)
        return [self._message_view(m) for m in replies]

    # ------------------------------------------------------------- AI participant
    async def _ai_answer(self, room, question: str) -> tuple[str, list]:
        """Grounded, cited answer from the Copilot's deterministic evidence
        provider (offline-safe; every citation references a real record)."""
        provider = EvidenceProvider(self.session)
        evidence = await provider.gather_evidence(room.organization_id, question)
        return evidence.get("answer") or "No grounded evidence available.", evidence.get("citations") or []

    async def ai_respond(
        self, user, org_context, room_id: str, prompt: str, *,
        parent_message_id: str | None = None, agent: str = "COPILOT",
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> LiveMessageView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        parent_id = await self._validate_parent(room, parent_message_id)

        answer, citations = await self._ai_answer(room, prompt)
        if on_chunk is not None:
            chunk = max(8, settings.WAR_ROOM_AI_STREAM_CHUNK)
            for i in range(0, len(answer), chunk):
                await on_chunk(answer[i:i + chunk])

        agent_value = agent if agent in _AI_AGENTS else "COPILOT"
        msg = await self._persist_message(
            room, author_type=WarRoomAuthorType.AI.value, agent=agent_value,
            content=answer, message_type="FINDING", citations=list(citations),
            parent_message_id=parent_id,
        )
        await self.audit_repo.log(
            action="war_room_ai_message", resource_type="war_room",
            resource_id=room.id, user_id=user.id,
            details={"organization_id": organization_id, "message_id": msg.id, "agent": agent_value},
        )
        await self.session.commit()
        view = self._message_view(msg)
        await self._broadcast(room.id, "message", view.model_dump(mode="json"))
        return view

    # ------------------------------------------------------------- participants
    async def join(self, user, org_context, room_id: str) -> ParticipantView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        participant = await self.participant_repo.upsert(
            war_room_id=room.id, organization_id=organization_id,
            user_id=user.id, user_name=user.full_name or user.username,
            role=org_context.role.value if org_context.role else None, is_active=True,
        )
        await self.audit_repo.log(
            action="war_room_joined", resource_type="war_room", resource_id=room.id,
            user_id=user.id, details={"organization_id": organization_id},
        )
        await self.session.commit()
        online_ids = {p["user_id"] for p in manager.presence(room.id)}
        view = self._participant_view(participant, online_ids)
        await self._broadcast(room.id, "participant_joined", view.model_dump(mode="json"))
        return view

    async def leave(self, user, org_context, room_id: str) -> None:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        participant = await self.participant_repo.get(room.id, user.id)
        if participant is not None:
            participant.is_active = False
            participant.last_seen_at = utcnow()
            await self.session.flush()
        await self.session.commit()
        await self._broadcast(
            room.id, "participant_left",
            {"user_id": user.id, "user_name": user.full_name or user.username},
        )

    async def touch_presence(self, organization_id: str, room_id: str, user_id: str) -> None:
        """Update a participant's last-seen marker (called on socket disconnect)."""
        participant = await self.participant_repo.get(room_id, user_id)
        if participant is not None:
            participant.last_seen_at = utcnow()
            await self.session.flush()
            await self.session.commit()

    async def presence(self, user, org_context, room_id: str) -> PresenceView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        online = manager.presence(room.id)
        online_ids = {p["user_id"] for p in online}
        participants = await self.participant_repo.list_for_room(room.id, organization_id)
        return PresenceView(
            war_room_id=room.id,
            online=[PresenceUser(**p) for p in online],
            participants=[self._participant_view(p, online_ids) for p in participants],
        )

    async def list_participants(self, user, org_context, room_id: str) -> list[ParticipantView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        online_ids = {p["user_id"] for p in manager.presence(room.id)}
        participants = await self.participant_repo.list_for_room(room.id, organization_id)
        return [self._participant_view(p, online_ids) for p in participants]

    # ------------------------------------------------------------- uploads
    def _upload_dir(self, room_id: str) -> Path:
        base = Path(settings.LOCAL_DATA_DIR) / settings.WAR_ROOM_UPLOAD_DIR / room_id
        base.mkdir(parents=True, exist_ok=True)
        return base

    async def save_upload(
        self, user, org_context, room_id: str, upload: UploadFile, *,
        message_id: str | None = None, kind: str = "UPLOAD",
    ) -> AttachmentView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)

        content_type = upload.content_type or "application/octet-stream"
        if content_type not in settings.WAR_ROOM_ALLOWED_UPLOAD_TYPES:
            raise NexoraException(f"Unsupported file type: {content_type}", status_code=415)
        data = await upload.read()
        if len(data) > settings.WAR_ROOM_MAX_UPLOAD_BYTES:
            raise NexoraException("File exceeds the maximum allowed size.", status_code=413)
        if not data:
            raise NexoraException("Empty upload.", status_code=400)

        suffix = Path(upload.filename or "").suffix[:20]
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        path = self._upload_dir(room.id) / stored_name
        path.write_bytes(data)

        att = await self.attachment_repo.create(
            war_room_id=room.id, organization_id=organization_id,
            message_id=message_id, uploaded_by=user.id,
            filename=Path(upload.filename or stored_name).name,
            content_type=content_type, size_bytes=len(data),
            storage_path=str(path), kind=kind,
        )
        await self.audit_repo.log(
            action="war_room_upload", resource_type="war_room", resource_id=room.id,
            user_id=user.id,
            details={"organization_id": organization_id, "attachment_id": att.id,
                     "size_bytes": len(data), "content_type": content_type},
        )
        await self.session.commit()
        view = self._attachment_view(att)
        await self._broadcast(room.id, "attachment", view.model_dump(mode="json"))
        return view

    async def get_attachment(self, user, org_context, room_id: str, attachment_id: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        att = await self.attachment_repo.get_for_room(attachment_id, room.id, organization_id)
        if att is None:
            raise NexoraException("Attachment not found.", status_code=404)
        if not Path(att.storage_path).exists():
            raise NexoraException("Stored file is no longer available.", status_code=410)
        return att

    async def list_attachments(self, user, org_context, room_id: str) -> list[AttachmentView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        rows = await self.attachment_repo.list_for_room(room.id, organization_id)
        return [self._attachment_view(a) for a in rows]

    # ------------------------------------------------------------- evidence
    async def add_evidence(self, user, org_context, room_id: str, payload) -> EvidenceView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        if payload.attachment_id:
            att = await self.attachment_repo.get_for_room(
                payload.attachment_id, room.id, organization_id
            )
            if att is None:
                raise NexoraException("Referenced attachment not found.", status_code=404)
        ev = await self.evidence_repo.create(
            war_room_id=room.id, organization_id=organization_id,
            title=payload.title, description=payload.description,
            source_type=payload.source_type, source_id=payload.source_id,
            attachment_id=payload.attachment_id, added_by=user.id,
        )
        await self.audit_repo.log(
            action="war_room_evidence_added", resource_type="war_room", resource_id=room.id,
            user_id=user.id,
            details={"organization_id": organization_id, "evidence_id": ev.id,
                     "source_type": payload.source_type},
        )
        await self.session.commit()
        view = self._evidence_view(ev)
        await self._broadcast(room.id, "evidence", view.model_dump(mode="json"))
        return view

    async def list_evidence(self, user, org_context, room_id: str) -> list[EvidenceView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        rows = await self.evidence_repo.list_for_room(room.id, organization_id)
        return [self._evidence_view(e) for e in rows]

    # ------------------------------------------------------------- approvals
    async def request_approval(self, user, org_context, room_id: str, payload) -> ApprovalView:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        ap = await self.approval_repo.create(
            war_room_id=room.id, organization_id=organization_id,
            title=payload.title, description=payload.description,
            kind=payload.kind, payload=payload.payload,
            status=WarRoomApprovalStatus.PENDING.value, requested_by=user.id,
        )
        await self.audit_repo.log(
            action="war_room_approval_requested", resource_type="war_room", resource_id=room.id,
            user_id=user.id,
            details={"organization_id": organization_id, "approval_id": ap.id, "kind": payload.kind},
        )
        await self.session.commit()
        view = self._approval_view(ap)
        await self._broadcast(room.id, "approval_requested", view.model_dump(mode="json"))
        return view

    async def decide_approval(
        self, user, org_context, room_id: str, approval_id: str, decision
    ) -> ApprovalView:
        organization_id = org_context.requires_organization
        self._ensure_decide(user, org_context)
        room = await self._load_room(organization_id, room_id)
        ap = await self.approval_repo.get_for_room(approval_id, room.id, organization_id)
        if ap is None:
            raise NexoraException("Approval not found.", status_code=404)
        if ap.status != WarRoomApprovalStatus.PENDING.value:
            raise NexoraException("Approval has already been decided.", status_code=400)

        verb = (decision.decision or "").strip().upper()
        if verb in ("APPROVE", "APPROVED"):
            ap.status = WarRoomApprovalStatus.APPROVED.value
        elif verb in ("REJECT", "REJECTED"):
            ap.status = WarRoomApprovalStatus.REJECTED.value
        else:
            raise NexoraException("decision must be APPROVE or REJECT.", status_code=422)
        ap.decided_by = user.id
        ap.decided_at = utcnow()
        ap.reason = decision.reason
        await self.session.flush()
        await self.audit_repo.log(
            action="war_room_approval_decided", resource_type="war_room", resource_id=room.id,
            user_id=user.id,
            details={"organization_id": organization_id, "approval_id": ap.id,
                     "status": ap.status},
        )
        await self.session.commit()
        view = self._approval_view(ap)
        await self._broadcast(room.id, "approval_decided", view.model_dump(mode="json"))
        return view

    async def list_approvals(self, user, org_context, room_id: str) -> list[ApprovalView]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        room = await self._load_room(organization_id, room_id)
        rows = await self.approval_repo.list_for_room(room.id, organization_id)
        return [self._approval_view(a) for a in rows]
