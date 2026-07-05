"""Organization configuration variables API."""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.org_config import OrgVariableCreate, OrgVariableUpdate, OrgVariableView
from app.services.org_config import OrgConfigService

router = APIRouter(prefix="/org-config", tags=["Organization Config"])


def _svc(session: DBSession) -> OrgConfigService:
    return OrgConfigService(session)


@router.get("/variables", response_model=list[OrgVariableView])
async def list_variables(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    environment: str | None = None,
):
    rows = await _svc(session).list_variables(current_user, org_context, environment=environment)
    return [OrgVariableView(**r) for r in rows]


@router.post("/variables", response_model=OrgVariableView, status_code=status.HTTP_201_CREATED)
async def create_variable(
    payload: OrgVariableCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_variable(current_user, org_context, payload)
    await session.commit()
    return OrgVariableView(**row)


@router.put("/variables/{variable_id}", response_model=OrgVariableView)
async def update_variable(
    variable_id: str,
    payload: OrgVariableUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).update_variable(current_user, org_context, variable_id, payload)
    await session.commit()
    return OrgVariableView(**row)


@router.delete("/variables/{variable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    variable_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    await _svc(session).delete_variable(current_user, org_context, variable_id)
    await session.commit()
