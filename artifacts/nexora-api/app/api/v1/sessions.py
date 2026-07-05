"""Active session management: list devices, logout one, logout all."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import CurrentUser, DBSession, bearer_scheme
from app.core.security import decode_token
from app.schemas.identity import RevokeResult, SessionListResponse, SessionResponse
from app.services.identity.sessions import SessionService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


async def current_access_jti(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        return None
    return payload.get("jti")


CurrentJti = Annotated[str | None, Depends(current_access_jti)]


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser, session: DBSession, jti: CurrentJti
):
    sessions = await SessionService(session).list_active(current_user.id)
    items: list[SessionResponse] = []
    for sess in sessions:
        resp = SessionResponse.model_validate(sess)
        resp.current = bool(jti and sess.access_jti == jti)
        items.append(resp)
    return SessionListResponse(items=items, total=len(items))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str, current_user: CurrentUser, session: DBSession
):
    ok = await SessionService(session).revoke(
        user_id=current_user.id, session_id=session_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.commit()


@router.post("/logout-all", response_model=RevokeResult)
async def logout_all(
    current_user: CurrentUser, session: DBSession, jti: CurrentJti
):
    svc = SessionService(session)
    keep_id = None
    if jti:
        for sess in await svc.list_active(current_user.id):
            if sess.access_jti == jti:
                keep_id = sess.id
                break
    revoked = await svc.revoke_all(user_id=current_user.id, keep_session_id=keep_id)
    await session.commit()
    return RevokeResult(revoked=revoked)
