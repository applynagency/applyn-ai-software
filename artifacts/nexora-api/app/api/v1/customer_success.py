"""Sprint 56A — Customer Success Documentation Platform API.

Read-only customer-success content: maturity-complete module guides, end-to-end
journey guides, integration playbooks, a beginner success center, a screenshot
manifest, and the documentation quality score. Org-scoped, strictly additive.
"""

from pathlib import Path

from fastapi import APIRouter, Query, Response
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.customer_success import (
    AcademyDashboard,
    AcademyProgressRequest,
    AcademyTrack,
    AcademyTracksResponse,
    AdoptionAnalyzeRequest,
    AdoptionDashboard,
    AnnotationResponse,
    AnnotationSummary,
    ArchitectureDiagram,
    ArchitectureListResponse,
    AuditReport,
    AuditTrailResponse,
    CaptureListResponse,
    CertificationDashboard,
    CertificationReport,
    ConsistencyReport,
    CustomerPlaybook,
    CustomerPlaybooksResponse,
    DashboardResponse,
    DemoDashboard,
    DemoRunState,
    DemoSalesMode,
    DemoScenario,
    DemoStateRequest,
    DriftReport,
    GalleryResponse,
    GuideAudit,
    HumanGuide,
    HumanGuideListResponse,
    HumanQualityReport,
    IntegrationVisual,
    IntegrationVisualListResponse,
    JourneyDiagramListResponse,
    JourneyGuide,
    JourneyListResponse,
    JourneyManual,
    JourneyManualListResponse,
    JourneyVerificationReport,
    JourneyWalkthroughListResponse,
    LearningPath,
    LearningPathListResponse,
    LifecycleListResponse,
    ModuleGuide,
    ModuleListResponse,
    NavigationHealthReport,
    NavigationMapListResponse,
    Playbook,
    PlaybookListResponse,
    PlaybookManual,
    PlaybookManualListResponse,
    PortalResponse,
    QualityReport,
    ReadinessReport,
    ReleaseReport,
    RewriteGuide,
    RewriteGuidesResponse,
    RewriteQualityReport,
    ScreenshotAssetGenerateResponse,
    ScreenshotAssetResponse,
    ScreenshotCoverageResponse,
    ScreenshotEnsureResponse,
    ScreenshotGuideDetail,
    ScreenshotManifestResponse,
    ScreenshotRealityReport,
    ScreenshotReleaseGate,
    ScreenshotValidationReport,
    SuccessGuide,
    SuccessListResponse,
    TourGuide,
    TourGuideListResponse,
    TourListResponse,
    TourState,
    TourStateRequest,
    TTVDashboard,
    TTVExperience,
    TTVExperiencesResponse,
    TTVProgressRequest,
    VerificationDashboard,
    VerificationListResponse,
    VerificationRunResponse,
    VerificationSummary,
    VideoDetail,
    VideoLibraryResponse,
    VideoListResponse,
    VideoModuleResponse,
    VisualCoverageDashboard,
    VisualReadinessReport,
)
from app.services.customer_success import CustomerSuccessService
from app.services.documentation_export import DocumentationExportService
from app.services.documentation_verification_audit import (
    DocumentationVerificationAuditService,
)

router = APIRouter(prefix="/customer-success", tags=["Customer Success"])


def _service() -> CustomerSuccessService:
    return CustomerSuccessService()


@router.get("/portal", response_model=PortalResponse)
async def get_portal(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().portal()


@router.get("/modules", response_model=ModuleListResponse)
async def list_modules(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().list_modules()


@router.get("/modules/{key}", response_model=ModuleGuide)
async def get_module(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_module(key)


@router.get("/journeys", response_model=JourneyListResponse)
async def list_journeys(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().list_journeys()


# Sprint 56D.3 — journey diagrams & manuals (static paths before /journeys/{key}).
@router.get("/journey-diagrams", response_model=JourneyDiagramListResponse)
async def journey_diagrams(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().journey_diagrams()


@router.get("/journey-manuals", response_model=JourneyManualListResponse)
async def journey_manuals(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().journey_manuals()


@router.get("/journeys/{key}", response_model=JourneyGuide)
async def get_journey(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_journey(key)


@router.get("/journeys/{key}/manual", response_model=JourneyManual)
async def journey_manual(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().journey_manual(key)


@router.get("/journeys/{key}/export")
async def journey_export(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = _service().journey_export(key, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/playbooks", response_model=PlaybookListResponse)
async def list_playbooks(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().list_playbooks()


# Sprint 56D.4 — playbook manuals (static path before /playbooks/{key}).
@router.get("/playbook-manuals", response_model=PlaybookManualListResponse)
async def playbook_manuals(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().playbook_manuals()


@router.get("/playbooks/{key}", response_model=Playbook)
async def get_playbook(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_playbook(key)


@router.get("/playbooks/{key}/manual", response_model=PlaybookManual)
async def playbook_manual(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().playbook_manual(key)


@router.get("/playbooks/{key}/export")
async def playbook_export(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = _service().playbook_export(key, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Sprint 56D.6 — Screenshot Reality Validation
@router.get("/screenshot-reality", response_model=ScreenshotRealityReport)
async def screenshot_reality(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_reality_report()


@router.get("/screenshot-reality/release-gate", response_model=ScreenshotReleaseGate)
async def screenshot_release_gate(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_release_gate()


@router.post("/screenshot-reality/ensure", response_model=ScreenshotEnsureResponse)
async def screenshot_reality_ensure(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_reality_ensure()


# Sprint 56D.5 — Human-Written Documentation Quality Engine
@router.get("/human-guides", response_model=HumanGuideListResponse)
async def list_human_guides(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().human_guides()


@router.get("/human-guides-quality", response_model=HumanQualityReport)
async def human_guides_quality(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().human_quality()


@router.get("/human-guides/{key}", response_model=HumanGuide)
async def get_human_guide(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().human_guide(key)


@router.get("/human-guides/{key}/export")
async def export_human_guide(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = _service().human_export(key, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Sprint 56F.1 — Documentation Content Audit Engine
@router.get("/documentation-audit", response_model=AuditReport)
async def documentation_audit(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().documentation_audit_report()


@router.get("/documentation-audit/guides/{key}", response_model=GuideAudit)
async def documentation_audit_guide(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().documentation_audit_guide(key)


# Sprint 56F.2 — Customer Documentation Rewrite Engine
@router.get("/rewritten-guides", response_model=RewriteGuidesResponse)
async def rewritten_guides(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return {"guides": _service().rewritten_guides()}


@router.get("/rewritten-guides/quality", response_model=RewriteQualityReport)
async def rewritten_guides_quality(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().rewrite_quality_report()


@router.get("/rewritten-guides/{key}", response_model=RewriteGuide)
async def rewritten_guide(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().rewritten_guide(key)


# Sprint 56F.3 — Screenshot Quality Validation Platform
@router.get("/screenshot-validation", response_model=ScreenshotValidationReport)
async def screenshot_validation(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_validation_report()


@router.get("/screenshot-validation/guides/{guide_id}", response_model=ScreenshotGuideDetail)
async def screenshot_validation_guide(
    guide_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_validation_guide(guide_id)


# Sprint 56F.4 — Customer Success Playbooks
@router.get("/success-playbooks", response_model=CustomerPlaybooksResponse)
async def success_playbooks(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().success_playbooks()


@router.get("/success-playbooks/{key}", response_model=CustomerPlaybook)
async def success_playbook(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().success_playbook(key)


@router.get("/success-playbooks/{key}/export")
async def export_success_playbook(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = _service().success_playbook_export(key, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Sprint 56F.5 — Documentation Excellence Certification
@router.get("/certification", response_model=CertificationReport)
async def documentation_certification(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().documentation_certification()


@router.get("/certification/dashboard", response_model=CertificationDashboard)
async def documentation_certification_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().documentation_certification_dashboard()


# Sprint 57A — Adoption Analytics
@router.get("/adoption-analytics", response_model=AdoptionDashboard)
async def adoption_analytics(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().adoption_dashboard()


@router.post("/adoption-analytics/analyze", response_model=AdoptionDashboard)
async def adoption_analytics_analyze(
    body: AdoptionAnalyzeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    events = [e.model_dump() for e in body.events]
    return _service().adoption_analyze(events)


# Sprint 56E.5 — Demo Experience Platform
@router.get("/demos", response_model=DemoDashboard)
async def demo_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().demo_dashboard()


@router.get("/demos/scenarios/{key}", response_model=DemoScenario)
async def demo_scenario(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().demo_scenario(key)


@router.get("/demos/scenarios/{key}/sales-mode", response_model=DemoSalesMode)
async def demo_sales_mode(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().demo_sales_mode(key)


@router.post("/demos/scenarios/{key}/launch", response_model=DemoRunState)
async def demo_launch(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().demo_launch(key)


@router.post("/demos/scenarios/{key}/state", response_model=DemoRunState)
async def demo_state(
    key: str,
    body: DemoStateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().demo_state(key, body.action, body.completed, body.started_at)


# Sprint 56E.4 — Time To Value Optimization
@router.get("/time-to-value", response_model=TTVDashboard)
async def ttv_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    keys = [k for k in (completed or "").split(",") if k]
    return _service().ttv_dashboard(keys)


@router.post("/time-to-value/progress", response_model=TTVDashboard)
async def ttv_progress(
    body: TTVProgressRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().ttv_dashboard(body.completed)


@router.get("/time-to-value/experiences", response_model=TTVExperiencesResponse)
async def ttv_experiences(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    keys = [k for k in (completed or "").split(",") if k]
    return _service().ttv_experiences(keys)


@router.get("/time-to-value/experiences/{key}", response_model=TTVExperience)
async def ttv_experience(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    keys = [k for k in (completed or "").split(",") if k]
    return _service().ttv_experience(key, keys)


@router.post("/time-to-value/experiences/{key}/progress", response_model=TTVExperience)
async def ttv_experience_progress(
    key: str,
    body: TTVProgressRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().ttv_experience(key, body.completed)


# Sprint 56E.3 — Customer Success Academy
@router.get("/academy", response_model=AcademyDashboard)
async def academy_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    keys = [k for k in (completed or "").split(",") if k]
    return _service().academy_dashboard(keys)


@router.post("/academy/progress", response_model=AcademyDashboard)
async def academy_progress(
    body: AcademyProgressRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().academy_dashboard(body.completed)


@router.get("/academy/tracks", response_model=AcademyTracksResponse)
async def academy_tracks(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    keys = [k for k in (completed or "").split(",") if k]
    return _service().academy_tracks(keys)


@router.get("/academy/tracks/{key}", response_model=AcademyTrack)
async def academy_track(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    keys = [k for k in (completed or "").split(",") if k]
    return _service().academy_track(key, keys)


@router.post("/academy/tracks/{key}/progress", response_model=AcademyTrack)
async def academy_track_progress(
    key: str,
    body: AcademyProgressRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().academy_track(key, body.completed)


# Sprint 56E.2 — Video Training Platform
@router.get("/videos", response_model=VideoLibraryResponse)
async def video_library(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    module: str | None = Query(default=None),
    category: str | None = Query(default=None),
    kind: str | None = Query(default=None),
):
    return _service().video_library(module=module, category=category, kind=kind)


@router.get("/videos/featured", response_model=VideoListResponse)
async def featured_videos(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().featured_videos()


@router.get("/videos/recently-added", response_model=VideoListResponse)
async def recently_added_videos(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    limit: int = Query(default=12),
):
    return _service().recently_added_videos(limit)


@router.get("/videos/by-module/{module}", response_model=VideoModuleResponse)
async def videos_for_module(
    module: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().videos_for_module(module)


@router.get("/videos/{video_id}", response_model=VideoDetail)
async def get_video(
    video_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().video(video_id)


@router.get("/videos/{video_id}/export")
async def export_video(
    video_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = _service().video_export(video_id, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Sprint 56E.1 — Interactive Product Tours
@router.get("/tours", response_model=TourListResponse)
async def list_tours(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    kind: str | None = Query(default=None),
    audience: str | None = Query(default=None),
):
    return _service().list_tours(kind=kind, audience=audience)


@router.get("/tour-guides", response_model=TourGuideListResponse)
async def list_tour_guides(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().list_tour_guides()


@router.get("/tours/by-module/{module}", response_model=TourGuideListResponse)
async def tours_for_module(
    module: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().tours_for_module(module)


@router.get("/tours/{key}", response_model=TourGuide)
async def get_tour(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_tour(key)


@router.post("/tours/{key}/state", response_model=TourState)
async def tour_state(
    key: str,
    payload: TourStateRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().tour_state(
        key, action=payload.action, completed=payload.completed, started_at=payload.started_at
    )


@router.get("/success-center", response_model=SuccessListResponse)
async def list_success(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().list_success()


@router.get("/success-center/{key}", response_model=SuccessGuide)
async def get_success(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_success(key)


@router.get("/screenshots", response_model=ScreenshotManifestResponse)
async def get_screenshots(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    category: str | None = Query(default=None),
):
    return _service().screenshots(category=category)


@router.get("/quality", response_model=QualityReport)
async def get_quality(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().quality()


# --------------------------------------------------------------------------- #
# Sprint 56A.1 endpoints                                                       #
# --------------------------------------------------------------------------- #
@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().dashboard()


@router.get("/readiness", response_model=ReadinessReport)
async def get_readiness(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().readiness()


@router.get("/screenshot-coverage", response_model=ScreenshotCoverageResponse)
async def get_screenshot_coverage(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_coverage()


@router.get("/architecture", response_model=ArchitectureListResponse)
async def list_architecture(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().architecture()


@router.get("/architecture/{key}", response_model=ArchitectureDiagram)
async def get_architecture(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_architecture(key)


@router.get("/learning-paths", response_model=LearningPathListResponse)
async def list_learning_paths(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    return _service().learning_paths(completed=completed)


@router.get("/learning-paths/{key}", response_model=LearningPath)
async def get_learning_path(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    completed: str | None = Query(default=None),
):
    return _service().get_learning_path(key, completed=completed)


# --------------------------------------------------------------------------- #
# Sprint 56B endpoints — visual documentation                                 #
# --------------------------------------------------------------------------- #
@router.get("/captures", response_model=CaptureListResponse)
async def list_captures(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    device: str | None = Query(default=None),
    module: str | None = Query(default=None),
    capture_type: str | None = Query(default=None),
):
    return _service().captures(device=device, module=module, capture_type=capture_type)


@router.get("/annotations", response_model=AnnotationResponse)
async def list_annotations(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    screenshot_id: str | None = Query(default=None),
):
    return _service().annotations(screenshot_id=screenshot_id)


@router.get("/annotations/summary", response_model=AnnotationSummary)
async def annotation_summary(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().annotation_summary()


@router.get("/navigation-maps", response_model=NavigationMapListResponse)
async def navigation_maps(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().navigation_maps()


@router.get("/journey-walkthroughs", response_model=JourneyWalkthroughListResponse)
async def journey_walkthroughs(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().journey_walkthroughs()


@router.get("/integration-visuals", response_model=IntegrationVisualListResponse)
async def integration_visuals(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().integration_visuals()


@router.get("/integration-visuals/{key}", response_model=IntegrationVisual)
async def get_integration_visual(
    key: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().get_integration_visual(key)


@router.get("/gallery", response_model=GalleryResponse)
async def gallery(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    module: str | None = Query(default=None),
    workflow: str | None = Query(default=None),
    journey: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    role: str | None = Query(default=None),
    device: str | None = Query(default=None),
):
    return _service().gallery(
        module=module, workflow=workflow, journey=journey,
        integration=integration, role=role, device=device,
    )


@router.get("/visual-coverage", response_model=VisualCoverageDashboard)
async def visual_coverage(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().visual_coverage()


@router.get("/visual-readiness", response_model=VisualReadinessReport)
async def visual_readiness(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().visual_readiness()


@router.get("/export")
async def export_visual_docs(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = DocumentationExportService().export(format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# Sprint 56C endpoints — documentation verification & drift detection         #
# --------------------------------------------------------------------------- #
@router.get("/verifications", response_model=VerificationListResponse)
async def list_verifications(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status: str | None = Query(default=None),
    module: str | None = Query(default=None),
):
    return _service().verifications(status=status, module=module)


@router.get("/verification-summary", response_model=VerificationSummary)
async def verification_summary(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().verification_summary()


@router.get("/lifecycle", response_model=LifecycleListResponse)
async def lifecycle(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().lifecycle()


@router.get("/lifecycle-report")
async def lifecycle_report(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().lifecycle_report()


@router.get("/drift", response_model=DriftReport)
async def drift(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().drift()


@router.get("/navigation-health", response_model=NavigationHealthReport)
async def navigation_health(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().navigation_health()


@router.get("/journey-verification", response_model=JourneyVerificationReport)
async def journey_verification(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().journey_verification()


@router.get("/consistency", response_model=ConsistencyReport)
async def consistency(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().consistency()


@router.get("/release-report", response_model=ReleaseReport)
async def release_report(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().release_report()


@router.get("/verification-dashboard", response_model=VerificationDashboard)
async def verification_dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().verification_dashboard()


@router.post("/verify", response_model=VerificationRunResponse)
async def run_verification(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DocumentationVerificationAuditService(session).run(
        org_id=org_context.organization_id, user_id=current_user.id,
    )


@router.get("/verification-audit", response_model=AuditTrailResponse)
async def verification_audit(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await DocumentationVerificationAuditService(session).trail(
        org_id=org_context.organization_id,
    )


# --------------------------------------------------------------------------- #
# Sprint 56D.1 endpoints — real screenshot assets                             #
# --------------------------------------------------------------------------- #
@router.get("/screenshot-assets", response_model=ScreenshotAssetResponse)
async def screenshot_assets(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().screenshot_assets()


@router.post("/screenshot-assets/generate", response_model=ScreenshotAssetGenerateResponse)
async def generate_screenshot_assets(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return _service().generate_screenshot_assets()


# Short cache so re-captured screenshots show up quickly (ETag still revalidates).
_SVG_HEADERS = {"Cache-Control": "public, max-age=300"}
_PNG_HEADERS = {"Cache-Control": "public, max-age=300"}

# Real screenshots captured from the live application (Sprint 56F.9).
_SHOTS_DIR = Path(__file__).resolve().parents[3] / "static" / "docs" / "shots"

# Documentation module keys whose name differs from the captured screenshot file.
_SHOT_ALIASES = {
    "infrastructure-discovery": "discovery",
    "slo": "slos",
    "reports": "reliability-dashboard",
    "executive-reports": "reliability-dashboard",
    "postmortems": "incidents",
    "timeline": "incidents",
    "remediation": "incidents",
    "recommendations": "copilot",
    "members": "organization",
}


def _real_screenshot(screenshot_id: str) -> Path | None:
    """Resolve a screenshot id to a real captured PNG via progressive prefixes.

    e.g. ``cost-step-3`` -> ``cost-step`` -> ``cost`` so module/step ids reuse
    the captured module screenshot when a step-specific one is not present.
    Known module-key aliases (``slo`` -> ``slos``) are also tried.
    """
    parts = screenshot_id.split("-")
    for i in range(len(parts), 0, -1):
        prefix = "-".join(parts[:i])
        for name in (prefix, _SHOT_ALIASES.get(prefix)):
            if not name:
                continue
            candidate = _SHOTS_DIR / (name + ".png")
            if candidate.is_file():
                return candidate
    return None


# Public image endpoints so documentation <img> tags can load assets directly.
@router.get("/screenshot-render")
async def render_screenshot(
    route: str = Query(default="/"),
    shot: str = Query(default="overview"),
    device: str = Query(default="desktop"),
):
    svg = _service().screenshot_svg_for_route(route, shot, device)
    return Response(content=svg, media_type="image/svg+xml", headers=_SVG_HEADERS)


@router.get("/screenshots/{screenshot_id}")
async def get_screenshot(screenshot_id: str):
    real = _real_screenshot(screenshot_id)
    if real is not None:
        return FileResponse(real, media_type="image/png", headers=_PNG_HEADERS)
    svg = _service().screenshot_svg(screenshot_id)
    return Response(content=svg, media_type="image/svg+xml", headers=_SVG_HEADERS)
