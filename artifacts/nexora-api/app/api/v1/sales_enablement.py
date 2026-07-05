"""Sprint 53D - Sales & Demo Enablement API.

Catalogs (read-only):
* GET  /v1/sales/demo-recordings           - demo recording library (+ org videos)
* GET  /v1/sales/product-videos            - product explainer videos
* GET  /v1/sales/scenario-launcher         - launch manifest for built-in scenarios
* GET  /v1/sales/competitive-comparison    - Nexora vs competitors (?competitor=)
* GET  /v1/sales/personas                  - value-proposition personas
* GET  /v1/sales/pricing                   - pricing tiers

Generators:
* POST /v1/sales/value-proposition         - persona pitch
* POST /v1/sales/proposal                  - proposal + scope + pricing bundle

Exports (pdf | html | markdown):
* GET  /v1/sales/competitive-comparison/export
* POST /v1/sales/value-proposition/export
* POST /v1/sales/proposal/export           - ?document=proposal|scope|pricing
"""

from fastapi import APIRouter, Query, Response

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.sales_enablement import ProposalRequest, ValuePropositionRequest
from app.services.sales_enablement import SalesEnablementService

router = APIRouter(prefix="/sales", tags=["Sales Enablement"])


# ------------------------------------------------------------------ catalogs
@router.get("/demo-recordings")
async def demo_recordings(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    scenario: str | None = Query(default=None),
    persona: str | None = Query(default=None),
):
    return await SalesEnablementService(session).list_demo_recordings(
        org_context.organization_id, scenario=scenario, persona=persona
    )


@router.get("/product-videos")
async def product_videos(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    category: str | None = Query(default=None),
):
    return SalesEnablementService(session).list_product_videos(category=category)


@router.get("/scenario-launcher")
async def scenario_launcher(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return SalesEnablementService(session).get_scenario_launcher()


@router.get("/competitive-comparison")
async def competitive_comparison(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    competitor: str | None = Query(default=None),
):
    return SalesEnablementService(session).get_comparison(competitor=competitor)


@router.get("/personas")
async def personas(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return SalesEnablementService(session).list_personas()


@router.get("/pricing")
async def pricing(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return SalesEnablementService(session).pricing_catalog()


# ---------------------------------------------------------------- generators
@router.post("/value-proposition")
async def value_proposition(
    payload: ValuePropositionRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SalesEnablementService(session)
    vp = service.generate_value_proposition(
        persona=payload.persona, company_name=payload.company_name
    )
    await service._audit("value_proposition_generated", current_user,
                         {"persona": vp["persona"], "organization_id": org_context.organization_id})
    return vp


@router.post("/proposal")
async def proposal(
    payload: ProposalRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SalesEnablementService(session)
    bundle = service.generate_proposal(
        company_name=payload.company_name, engineer_count=payload.engineer_count,
        tier=payload.tier, term_months=payload.term_months,
        contact_name=payload.contact_name, prepared_by=payload.prepared_by, notes=payload.notes,
    )
    await service._audit("proposal_generated", current_user,
                         {"company_name": payload.company_name,
                          "tier": bundle["pricing"]["tier"],
                          "organization_id": org_context.organization_id})
    return bundle


# ------------------------------------------------------------------- exports
def _file_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/competitive-comparison/export")
async def export_comparison(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    competitor: str | None = Query(default=None),
    format: str = Query(default="pdf"),
):
    service = SalesEnablementService(session)
    data = service.get_comparison(competitor=competitor)
    markdown = service.render_comparison_markdown(data)
    content, media_type, filename = service.export(
        markdown, title="Nexora Competitive Comparison", fmt=format,
        filename_base="nexora-comparison",
    )
    return _file_response(content, media_type, filename)


@router.post("/value-proposition/export")
async def export_value_proposition(
    payload: ValuePropositionRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    service = SalesEnablementService(session)
    vp = service.generate_value_proposition(
        persona=payload.persona, company_name=payload.company_name
    )
    markdown = service.render_value_proposition_markdown(vp)
    content, media_type, filename = service.export(
        markdown, title=f"{vp['persona_label']} Pitch", fmt=format,
        filename_base=f"nexora-pitch-{vp['persona'].lower()}",
    )
    return _file_response(content, media_type, filename)


@router.post("/proposal/export")
async def export_proposal(
    payload: ProposalRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    document: str = Query(default="proposal", description="proposal | scope | pricing"),
    format: str = Query(default="pdf"),
):
    from app.core.exceptions import NexoraException

    service = SalesEnablementService(session)
    bundle = service.generate_proposal(
        company_name=payload.company_name, engineer_count=payload.engineer_count,
        tier=payload.tier, term_months=payload.term_months,
        contact_name=payload.contact_name, prepared_by=payload.prepared_by, notes=payload.notes,
    )
    doc = (document or "proposal").lower()
    if doc == "proposal":
        markdown, title, base = service.render_proposal_markdown(bundle), "Nexora Proposal", "nexora-proposal"
    elif doc == "scope":
        markdown, title, base = service.render_scope_markdown(bundle), "Nexora Scope Document", "nexora-scope"
    elif doc == "pricing":
        markdown, title, base = service.render_pricing_markdown(bundle), "Nexora Pricing Sheet", "nexora-pricing"
    else:
        raise NexoraException("document must be proposal, scope, or pricing.", status_code=400)
    content, media_type, filename = service.export(
        markdown, title=title, fmt=format, filename_base=base
    )
    return _file_response(content, media_type, filename)
