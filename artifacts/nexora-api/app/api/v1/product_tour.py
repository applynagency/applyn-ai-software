"""Sprint 51D - Interactive Product Tour API.

* POST /v1/product-tours/start          - start (or resume) a tour for the user
* GET  /v1/product-tours                 - list tours (with the user's progress)
* GET  /v1/product-tours/{id}           - tour detail (steps + progress)
* POST /v1/product-tours/{id}/step      - record step progress
* POST /v1/product-tours/{id}/complete  - mark a tour complete
* GET  /v1/product-tours/contextual      - contextual help by module/route (additive)

Org-scoped; progress is private per user. Audited. Strictly additive.
"""

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.product_tour import ProductTour, ProductTourProgress, ProductTourStep
from app.schemas.product_tour import (
    ContextualHelpResponse,
    ProgressView,
    StartRequest,
    StartResponse,
    StepRequest,
    StepView,
    TourDetail,
    TourSummary,
)
from app.services.product_tour import ProductTourService

router = APIRouter(prefix="/product-tours", tags=["Product Tours"])


def _progress(p: ProductTourProgress | None) -> ProgressView | None:
    if p is None:
        return None
    return ProgressView(
        id=p.id,
        tour_id=p.tour_id,
        user_id=p.user_id,
        status=p.status,
        current_step_index=p.current_step_index,
        completed_step_ids=list(p.completed_step_ids or []),
        progress_percent=p.progress_percent,
        started_at=p.started_at,
        completed_at=p.completed_at,
        last_activity_at=p.last_activity_at,
    )


def _detail(tour: ProductTour, steps: list[ProductTourStep], progress) -> TourDetail:
    return TourDetail(
        id=tour.id,
        organization_id=tour.organization_id,
        key=tour.key,
        name=tour.name,
        description=tour.description,
        audience=tour.audience,
        is_first_login=bool(tour.is_first_login),
        estimated_minutes=tour.estimated_minutes,
        steps=[StepView.model_validate(s) for s in steps],
        progress=_progress(progress),
    )


@router.post("/start", response_model=StartResponse, status_code=status.HTTP_201_CREATED)
async def start_tour(
    payload: StartRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    tour, steps, progress = await ProductTourService(session).start(current_user, org_context, payload)
    return StartResponse(tour=_detail(tour, steps, progress), progress=_progress(progress))


@router.get("", response_model=list[TourSummary])
async def list_tours(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    audience: str | None = Query(default=None),
    first_login: bool | None = Query(default=None),
):
    rows = await ProductTourService(session).list_tours(
        current_user, org_context, audience=audience, first_login=first_login
    )
    return [
        TourSummary(
            id=tr.id,
            key=tr.key,
            name=tr.name,
            description=tr.description,
            audience=tr.audience,
            is_first_login=bool(tr.is_first_login),
            estimated_minutes=tr.estimated_minutes,
            step_count=count,
            progress=_progress(progress),
        )
        for (tr, count, progress) in rows
    ]


@router.get("/contextual", response_model=ContextualHelpResponse)
async def contextual_help(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    module: str | None = Query(default=None),
    route: str | None = Query(default=None),
):
    module, route, steps = await ProductTourService(session).contextual_help(
        current_user, org_context, module=module, route=route
    )
    return ContextualHelpResponse(
        module=module, route=route, steps=[StepView.model_validate(s) for s in steps]
    )


@router.get("/{tour_id}", response_model=TourDetail)
async def get_tour(
    tour_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    tour, steps, progress = await ProductTourService(session).get_tour(
        current_user, org_context, tour_id
    )
    return _detail(tour, steps, progress)


@router.post("/{tour_id}/step", response_model=TourDetail)
async def record_step(
    tour_id: str,
    payload: StepRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    tour, steps, progress = await ProductTourService(session).record_step(
        current_user, org_context, tour_id, payload
    )
    return _detail(tour, steps, progress)


@router.post("/{tour_id}/complete", response_model=TourDetail)
async def complete_tour(
    tour_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    tour, steps, progress = await ProductTourService(session).complete(
        current_user, org_context, tour_id
    )
    return _detail(tour, steps, progress)
