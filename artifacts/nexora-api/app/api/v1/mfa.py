"""Multi-factor authentication (TOTP) enrollment and management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.identity import (
    MfaConfirmRequest,
    MfaEnrollResponse,
    MfaStatusResponse,
    RecoveryCodesResponse,
)
from app.services.identity.mfa import MfaError, MfaService

router = APIRouter(prefix="/auth/mfa", tags=["MFA"])


@router.get("/status", response_model=MfaStatusResponse)
async def mfa_status(current_user: CurrentUser, session: DBSession):
    svc = MfaService(session)
    enabled = await svc.is_enrolled(current_user.id)
    remaining = await svc.remaining_recovery_codes(current_user.id) if enabled else 0
    return MfaStatusResponse(enabled=enabled, recovery_codes_remaining=remaining)


@router.post("/enroll", response_model=MfaEnrollResponse)
async def enroll_mfa(current_user: CurrentUser, session: DBSession):
    try:
        result = await MfaService(session).begin_enrollment(current_user)
    except MfaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return MfaEnrollResponse(secret=result.secret, otpauth_uri=result.otpauth_uri)


@router.post("/confirm", response_model=RecoveryCodesResponse)
async def confirm_mfa(
    payload: MfaConfirmRequest, current_user: CurrentUser, session: DBSession
):
    try:
        codes = await MfaService(session).confirm_enrollment(current_user, payload.code)
    except MfaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/recovery-codes/regenerate", response_model=RecoveryCodesResponse)
async def regenerate_recovery_codes(current_user: CurrentUser, session: DBSession):
    try:
        codes = await MfaService(session).regenerate_recovery_codes(current_user)
    except MfaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(current_user: CurrentUser, session: DBSession):
    await MfaService(session).disable(current_user, actor_user_id=current_user.id)
    await session.commit()
