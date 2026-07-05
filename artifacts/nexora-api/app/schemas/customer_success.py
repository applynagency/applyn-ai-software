"""Sprint 56A — Customer Success Documentation Platform schemas."""

from __future__ import annotations

from pydantic import BaseModel


class NavPath(BaseModel):
    path: list[str]
    route: str


class OverviewView(BaseModel):
    what: str
    why: str
    business_value: str
    who: str
    when: str


class StepView(BaseModel):
    order: int
    action: str
    expected: str
    screenshot: str
    expected_screens: list[str] = []
    # Sprint 56B — embedded screenshot metadata.
    screenshot_id: str = ""
    caption: str = ""
    alt_text: str = ""
    # Sprint 56D.2 — per-step "what happens internally".
    internal: str = ""


class TermView(BaseModel):
    term: str
    meaning: str


class TipView(BaseModel):
    problem: str
    cause: str
    resolution: str


class FaqView(BaseModel):
    question: str
    answer: str


class ExampleView(BaseModel):
    scenario: str
    walkthrough: str
    outcome: str


class ScreenshotMeta(BaseModel):
    name: str
    caption: str
    category: str


class ModuleMetadata(BaseModel):
    reading_time_minutes: int
    difficulty: str
    role: str
    business_value: str
    expected_outcomes: list[str]
    related: list[str]


class InternalView(BaseModel):
    customer_action: str
    engines: list[str]
    outputs: list[str]


class ModuleGuide(BaseModel):
    key: str
    name: str
    category: str
    route: str
    navigation: NavPath
    overview: OverviewView
    prerequisites: list[str]
    steps: list[StepView]
    interpretation: list[TermView]
    example: ExampleView
    troubleshooting: list[TipView]
    best_practices: list[str]
    faq: list[FaqView]
    screenshots: list[ScreenshotMeta]
    metadata: ModuleMetadata
    # Sprint 56A.1 additions.
    architecture_diagram: str = ""
    internal: InternalView | None = None
    expected_screens: list[str] = []
    updated_at: str = ""
    # Sprint 56D.2 — training-grade additions.
    deep_dive: str = ""
    common_mistakes: list[str] = []
    next_steps: list[str] = []


class ModuleSummary(BaseModel):
    key: str
    name: str
    category: str
    route: str
    metadata: ModuleMetadata
    screenshot_count: int


class ModuleListResponse(BaseModel):
    items: list[ModuleSummary]
    total: int


class JourneyStage(BaseModel):
    order: int
    title: str
    description: str
    module: str
    screenshot: str
    expected_outcome: str
    # Sprint 56D.3 — end-to-end journey step detail.
    navigation: list[str] = []
    route: str = ""
    expected_screen: list[str] = []
    internal: str = ""
    common_issues: list[str] = []
    recovery_steps: list[str] = []


class JourneyGuide(BaseModel):
    key: str
    name: str
    category: str
    summary: str
    stages: list[JourneyStage]
    expected_outcomes: list[str]
    screenshots: list[ScreenshotMeta]
    # Sprint 56D.3 — Mermaid diagram for the whole journey.
    diagram: str = ""


class JourneyListResponse(BaseModel):
    items: list[JourneyGuide]
    total: int


# Sprint 56D.3 — journey diagrams & manuals.
class JourneyDiagram(BaseModel):
    key: str
    name: str
    diagram: str


class JourneyDiagramListResponse(BaseModel):
    items: list[JourneyDiagram]
    total: int


class JourneyManual(BaseModel):
    key: str
    name: str
    diagram: str
    markdown: str


class JourneyManualListResponse(BaseModel):
    items: list[JourneyManual]
    total: int


class CommonError(BaseModel):
    error: str
    fix: str


# Sprint 56D.4 — integration playbook detail.
class PlaybookConfigStep(BaseModel):
    order: int
    title: str
    action: str
    expected: str
    screenshot: str
    screenshot_id: str = ""
    caption: str = ""
    alt_text: str = ""
    route: str = ""
    shot: str = ""


class PlaybookAnnotation(BaseModel):
    target: str
    note: str


class PlaybookVisual(BaseModel):
    kind: str
    title: str
    route: str = ""
    shot: str = ""
    screenshot_id: str = ""
    caption: str = ""
    annotations: list[str] = []
    diagram: str = ""


class Playbook(BaseModel):
    key: str
    name: str
    category: str
    overview: str
    architecture_diagram: str
    prerequisites: list[str]
    required_permissions: list[str]
    credential_setup: list[str]
    validation_steps: list[str]
    expected_results: list[str]
    common_errors: list[CommonError]
    troubleshooting: list[str]
    security_notes: list[str]
    best_practices: list[str]
    screenshots: list[ScreenshotMeta]
    # Sprint 56A.1 additions.
    validation_checklist: list[str] = []
    recovery_steps: list[str] = []
    expected_outputs: list[str] = []
    # Sprint 56D.4 additions.
    business_value: str = ""
    use_cases: list[str] = []
    route: str = ""
    expected_screens: list[str] = []
    architecture_mermaid: str = ""
    configuration_steps: list[PlaybookConfigStep] = []
    annotations: list[PlaybookAnnotation] = []
    visuals: list[PlaybookVisual] = []
    faq: list[FaqView] = []


class PlaybookListResponse(BaseModel):
    items: list[Playbook]
    total: int


# Sprint 56D.4 — playbook manuals.
class PlaybookManual(BaseModel):
    key: str
    name: str
    diagram: str
    markdown: str


class PlaybookManualListResponse(BaseModel):
    items: list[PlaybookManual]
    total: int


class SuccessGuide(BaseModel):
    key: str
    name: str
    category: str
    summary: str
    difficulty: str
    estimated_minutes: int
    steps: list[StepView]
    expected_outcome: str
    related: list[str]
    screenshots: list[ScreenshotMeta]


class SuccessListResponse(BaseModel):
    items: list[SuccessGuide]
    total: int


class ScreenshotManifestEntry(BaseModel):
    page_name: str
    route: str
    screenshot_name: str
    screenshot_category: str
    description: str
    capture_priority: str


class ScreenshotManifestResponse(BaseModel):
    items: list[ScreenshotManifestEntry]
    total: int
    summary: dict


class QualityModule(BaseModel):
    key: str
    name: str
    category: str
    coverage_score: int
    level: str
    dimensions: dict[str, bool]
    missing_dimensions: list[str]
    production_ready: bool


class QualityReport(BaseModel):
    dimensions: list[str]
    target: int
    modules_total: int
    average_score: int
    production_ready_count: int
    passes_target: bool
    level: str
    modules: list[QualityModule]


class PortalResponse(BaseModel):
    modules: list[ModuleSummary]
    journeys: list[JourneyGuide]
    playbooks: list[Playbook]
    success_center: list[SuccessGuide]
    quality: QualityReport
    screenshots: dict
    counts: dict[str, int]


# --------------------------------------------------------------------------- #
# Sprint 56A.1 — dashboard, readiness, architecture, learning paths, coverage #
# --------------------------------------------------------------------------- #
class DashboardRow(BaseModel):
    module: str
    name: str
    category: str
    coverage_score: int
    quality_level: str
    screenshot_coverage: int
    guide_count: int
    last_updated: str


class DashboardResponse(BaseModel):
    modules: list[DashboardRow]
    average_score: int
    passes_target: bool
    target: int


class ReadinessReport(BaseModel):
    documentation_score: int
    screenshot_coverage: int
    modules_ready: int
    modules_total: int
    journeys_ready: int
    journeys_total: int
    integrations_ready: int
    integrations_total: int
    release_ready: bool


class ArchitectureDiagram(BaseModel):
    key: str
    name: str
    source_systems: list[str]
    data_flow: list[str]
    processing_layer: list[str]
    platform_components: list[str]
    outputs: list[str]
    mermaid: str


class ArchitectureListResponse(BaseModel):
    items: list[ArchitectureDiagram]
    total: int


class LearningPathStep(BaseModel):
    label: str
    module: str
    completed: bool = False


class LearningPath(BaseModel):
    key: str
    name: str
    summary: str
    steps: list[LearningPathStep]
    total_guides: int
    completed_guides: int
    remaining_guides: int
    completion_percent: int


class LearningPathListResponse(BaseModel):
    items: list[LearningPath]
    total: int


class CoveragePage(BaseModel):
    page_name: str
    route: str
    module: str
    screenshot_name: str
    screenshot_required: bool
    screenshot_available: bool
    screenshot_priority: str
    release_blocking: bool


class CoverageMetric(BaseModel):
    scope: str
    name: str
    total: int
    completed: int
    missing: int
    coverage_percent: int
    level: str


class ScreenshotCoverageResponse(BaseModel):
    pages: list[CoveragePage]
    metrics: dict
    platform: CoverageMetric
    total: int
    release_blocking: list[CoveragePage]


# --------------------------------------------------------------------------- #
# Sprint 56B — visual documentation & screenshot automation                   #
# --------------------------------------------------------------------------- #
class CaptureEntry(BaseModel):
    id: str
    page_name: str
    route: str
    module: str
    category: str
    device: str
    capture_type: str
    screenshot_path: str
    captured: bool
    captured_at: str
    version: str


class CaptureListResponse(BaseModel):
    items: list[CaptureEntry]
    total: int


class Annotation(BaseModel):
    screenshot_id: str
    kind: str
    target: str
    description: str
    region: dict


class AnnotationResponse(BaseModel):
    screenshot_id: str
    annotations: list[Annotation]
    total: int


class AnnotationSummary(BaseModel):
    annotated_screenshots: int
    total_annotations: int
    by_kind: dict[str, int]
    kinds: list[str]


class NavigationNode(BaseModel):
    page_name: str
    route: str
    page_screenshot: str
    navigation_screenshot: str
    expected_screens: list[str]


class NavigationMap(BaseModel):
    key: str
    name: str
    flow: str
    nodes: list[NavigationNode]


class NavigationMapListResponse(BaseModel):
    items: list[NavigationMap]
    total: int


class WalkthroughStep(BaseModel):
    order: int
    title: str
    screenshot: str
    expected_result: str
    navigation_path: list[str]


class JourneyWalkthrough(BaseModel):
    key: str
    name: str
    summary: str
    steps: list[WalkthroughStep]
    total_steps: int


class JourneyWalkthroughListResponse(BaseModel):
    items: list[JourneyWalkthrough]
    total: int


class IntegrationScreenSet(BaseModel):
    key: str
    label: str
    screenshot: str
    caption: str


class IntegrationVisual(BaseModel):
    key: str
    name: str
    architecture_diagram: str
    screen_sets: list[IntegrationScreenSet]


class IntegrationVisualListResponse(BaseModel):
    items: list[IntegrationVisual]
    total: int


class GalleryItem(BaseModel):
    screenshot_id: str
    screenshot_path: str
    title: str
    description: str
    module: str
    category: str
    device: str
    capture_type: str
    role: str
    workflows: list[str]
    journeys: list[str]
    integration: str | None = None
    related_guide: str


class GalleryResponse(BaseModel):
    items: list[GalleryItem]
    total: int
    facets: dict


class VisualCoverageDashboard(BaseModel):
    platform: dict
    by_module: list[dict]
    by_device: list[dict]
    by_journey: list[dict]
    by_integration: list[dict]
    by_capture_type: list[dict]
    target: int
    release_ready: bool


class VisualReadinessReport(BaseModel):
    screenshot_coverage: int
    annotated_screenshots: int
    total_annotations: int
    journeys_visualized: int
    integrations_visualized: int
    embedding_coverage: int
    documentation_visual_score: int
    release_ready: bool


# --------------------------------------------------------------------------- #
# Sprint 56C — documentation reality verification & drift detection           #
# --------------------------------------------------------------------------- #
class VerificationRecord(BaseModel):
    screenshot_id: str
    route: str
    page_name: str
    module: str
    ui_version: str
    screenshot_version: str
    verification_status: str
    verified_at: str | None = None


class VerificationListResponse(BaseModel):
    items: list[VerificationRecord]
    total: int


class VerificationSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    verified_screenshots: int
    outdated_screenshots: int
    broken_screenshots: int
    pending_screenshots: int
    verified_percent: int


class LifecycleRecord(BaseModel):
    screenshot_id: str
    module: str
    created_at: str
    updated_at: str
    verified_at: str | None = None
    last_used_at: str
    verification_count: int
    verification_status: str


class LifecycleListResponse(BaseModel):
    items: list[LifecycleRecord]
    total: int


class DriftItem(BaseModel):
    affected_module: str
    screenshot_count: int
    impacted_guides: int
    severity: str
    recommended_action: str


class DriftReport(BaseModel):
    items: list[DriftItem]
    total_drift: int
    by_severity: dict[str, int]
    drift_detected: bool


class NavigationHealthReport(BaseModel):
    paths: list[dict]
    total_paths: int
    valid_paths: int
    broken_paths: int
    health_score: int


class JourneyVerificationItem(BaseModel):
    key: str
    name: str
    status: str
    checks: list[dict]
    stage_count: int


class JourneyVerificationReport(BaseModel):
    journeys: list[JourneyVerificationItem]
    total: int
    passing: int
    warning: int
    failing: int
    journey_health: int


class ConsistencyReport(BaseModel):
    consistency_score: int
    checks: list[dict]
    passes: bool


class ReleaseReport(BaseModel):
    gates: list[dict]
    release_ready: bool
    metrics: dict


class VerificationDashboard(BaseModel):
    verified_screenshots: int
    outdated_screenshots: int
    broken_screenshots: int
    pending_screenshots: int
    navigation_health: int
    journey_health: int
    consistency_score: int
    drift_alerts: list[DriftItem]
    facets: dict


class VerificationReadinessReport(BaseModel):
    verified_screenshots: int
    outdated_screenshots: int
    broken_screenshots: int
    navigation_health: int
    journey_health: int
    consistency_score: int
    documentation_verification_score: int
    release_ready: bool


class VerificationRunResponse(BaseModel):
    verification: VerificationSummary
    drift: DriftReport
    navigation: NavigationHealthReport
    journey: JourneyVerificationReport
    release: ReleaseReport
    events_recorded: int


class AuditTrailItem(BaseModel):
    action: str
    resource_id: str | None = None
    details: dict | None = None
    status: str
    created_at: str | None = None


class AuditTrailResponse(BaseModel):
    items: list[AuditTrailItem]
    total: int


# --------------------------------------------------------------------------- #
# Sprint 56D.1 — real screenshot asset generation                             #
# --------------------------------------------------------------------------- #
class ScreenshotAsset(BaseModel):
    screenshot_id: str
    page_name: str
    route: str
    title: str
    description: str
    device: str
    shot_type: str
    capture_date: str
    version: str
    path: str
    asset_url: str
    route_valid: bool


class ScreenshotAssetCoverage(BaseModel):
    total: int
    valid: int
    invalid: int
    coverage_percent: int
    areas: int
    devices: int
    shots: int


class ScreenshotAssetResponse(BaseModel):
    items: list[ScreenshotAsset]
    coverage: ScreenshotAssetCoverage


class ScreenshotAssetGenerateResponse(BaseModel):
    generated: int
    directory: str
    total: int
    valid: int
    invalid: int
    coverage_percent: int
    areas: int
    devices: int
    shots: int


# --------------------------------------------------------------------------- #
# Sprint 56E.1 — Interactive Product Tours                                     #
# --------------------------------------------------------------------------- #
class TourStep(BaseModel):
    order: int
    title: str
    description: str
    detail: str = ""
    module: str
    target_element: str
    target_route: str
    target_selector: str
    expected_result: str
    next_action: str
    screenshot: str = ""
    screenshot_id: str = ""


class TourSummary(BaseModel):
    key: str
    name: str
    kind: str
    module: str
    audience: str
    difficulty: str
    summary: str
    estimated_minutes: int
    step_count: int


class TourListResponse(BaseModel):
    items: list[TourSummary]
    total: int


class TourGuide(BaseModel):
    key: str
    name: str
    kind: str
    module: str
    audience: str
    difficulty: str
    summary: str
    estimated_minutes: int
    steps: list[TourStep]


class TourGuideListResponse(BaseModel):
    items: list[TourGuide]
    total: int


class TourStateRequest(BaseModel):
    action: str = "progress"
    completed: list[str] = []
    started_at: str | None = None


class TourState(BaseModel):
    key: str
    name: str
    action: str
    status: str
    total_steps: int
    completed_steps: int
    completed_step_ids: list[str]
    completion_percentage: int
    current_step_index: int
    current_step: TourStep | None = None
    started_at: str | None = None
    completed_at: str | None = None


# --------------------------------------------------------------------------- #
# Sprint 56D.5 — Human-Written Documentation Quality Engine                    #
# --------------------------------------------------------------------------- #
class HumanAnswers(BaseModel):
    why: str
    what: str
    how: str
    expected_outcome: str


class HumanProblem(BaseModel):
    without: str
    with_solution: str
    summary: str
    context: str = ""


class HumanOutcome(BaseModel):
    metric: str
    detail: str


class HumanExample(BaseModel):
    title: str
    narrative: str
    alert: str
    incident: str
    timeline: str
    root_cause: str
    recommendation: str
    postmortem: str


class HumanWalkStep(BaseModel):
    order: int
    action: str
    why: str
    expected_result: str
    screenshot: str
    screenshot_id: str = ""
    common_mistakes: list[str]


class HumanScaleItem(BaseModel):
    label: str
    meaning: str


class HumanScaleGroup(BaseModel):
    name: str
    items: list[HumanScaleItem]


class HumanFaqItem(BaseModel):
    question: str
    answer: str


class HumanTroubleRow(BaseModel):
    problem: str
    cause: str
    resolution: str


class HumanSuccessMetric(BaseModel):
    metric: str
    target: str
    how: str


class HumanQuality(BaseModel):
    word_count: int
    steps: int
    faqs: int
    checks: dict[str, bool]
    score: int
    level: str


class HumanGuide(BaseModel):
    key: str
    name: str
    category: str
    route: str
    answers: HumanAnswers
    business_problem: HumanProblem
    business_outcomes: list[HumanOutcome]
    when_to_use: list[str]
    real_example: HumanExample
    walkthrough: list[HumanWalkStep]
    results_interpretation: list[HumanScaleGroup]
    faq: list[HumanFaqItem]
    troubleshooting: list[HumanTroubleRow]
    best_practices: list[str]
    success_metrics: list[HumanSuccessMetric]
    word_count: int
    quality: HumanQuality


class HumanGuideListResponse(BaseModel):
    items: list[HumanGuide]
    total: int


class HumanQualityRow(BaseModel):
    key: str
    name: str
    word_count: int
    steps: int
    faqs: int
    score: int
    level: str
    checks: dict[str, bool]


class HumanQualityReport(BaseModel):
    items: list[HumanQualityRow]
    total: int
    human_grade: int
    human_grade_percent: int
    average_word_count: int
    word_target: int
    all_meet_target: bool


# --------------------------------------------------------------------------- #
# Sprint 56D.6 — Screenshot Reality Validation                                 #
# --------------------------------------------------------------------------- #
class ScreenshotCheck(BaseModel):
    entity_type: str
    entity_key: str
    entity_name: str
    route: str
    shot: str
    device: str
    source: str
    declared_id: str = ""
    screenshot_id: str
    status: str
    file_exists: bool
    image_loads: bool
    rendered_in_ui: bool
    is_curated_asset: bool
    invalid_reference: bool


class ScreenshotRealityCounts(BaseModel):
    valid: int
    missing: int
    broken: int
    placeholder: int
    invalid_references: int


class ScreenshotEntityCoverage(BaseModel):
    entity_type: str
    entity_key: str
    entity_name: str
    screenshot_count: int
    min_required: int
    meets_minimum: bool
    valid: int
    placeholder: int
    broken: int
    missing: int


class ScreenshotReleaseGate(BaseModel):
    passed: bool
    status: str
    reasons: list[str]
    entities_below_minimum: list[ScreenshotEntityCoverage]


class ScreenshotRealityReport(BaseModel):
    total: int
    valid: int
    counts: ScreenshotRealityCounts
    missing: list[ScreenshotCheck]
    broken: list[ScreenshotCheck]
    placeholder: list[ScreenshotCheck]
    invalid_references: list[ScreenshotCheck]
    entity_coverage: list[ScreenshotEntityCoverage]
    minimums: dict[str, int]
    release_gate: ScreenshotReleaseGate


class ScreenshotEnsureResponse(BaseModel):
    canonical_generated: int
    reference_assets_written: int
    directory: str


# --------------------------------------------------------------------------- #
# Sprint 56E.2 — Video Training Platform                                       #
# --------------------------------------------------------------------------- #
class VideoScreen(BaseModel):
    route: str
    shot: str
    device: str
    screenshot_id: str
    thumbnail_url: str


class VideoScene(BaseModel):
    order: int
    title: str
    duration_seconds: int
    timecode: str
    narration: str
    voice_over: str
    on_screen_text: str
    expected_action: str
    screen: VideoScreen


class VideoMetadata(BaseModel):
    format: str
    codec: str
    resolution: str
    aspect_ratio: str
    fps: int
    duration_seconds: int
    has_captions: bool
    audio: str
    file: str
    poster_url: str
    status: str


class GifMetadata(BaseModel):
    format: str
    resolution: str
    fps: int
    loop: bool
    duration_seconds: int
    file: str
    preview_url: str


class ThumbnailMetadata(BaseModel):
    format: str
    resolution: str
    screenshot_id: str
    route: str
    file: str
    url: str
    alt: str


class VideoSummary(BaseModel):
    id: str
    module: str
    module_name: str
    route: str
    kind: str
    label: str
    title: str
    category: str
    duration_seconds: int
    duration_label: str
    summary: str
    featured: bool
    scene_count: int
    added_at: str
    thumbnail_metadata: ThumbnailMetadata


class VideoDetail(VideoSummary):
    scenes: list[VideoScene]
    video_metadata: VideoMetadata
    gif_metadata: GifMetadata


class VideoFacets(BaseModel):
    categories: dict[str, int]
    kinds: dict[str, int]
    modules: int


class VideoLibraryResponse(BaseModel):
    items: list[VideoSummary]
    total: int
    library_total: int
    facets: VideoFacets


class VideoListResponse(BaseModel):
    items: list[VideoSummary]
    total: int


class VideoModuleResponse(BaseModel):
    items: list[VideoDetail]
    total: int


# --------------------------------------------------------------------------- #
# Sprint 56E.3 — Customer Success Academy                                      #
# --------------------------------------------------------------------------- #
class AcademyModule(BaseModel):
    order: int
    key: str
    name: str
    route: str
    difficulty: str
    estimated_minutes: int
    completed: bool = False


class AcademyBadge(BaseModel):
    key: str
    name: str
    description: str
    tier: str
    icon: str
    track: str | None = None
    criteria: str
    earned: bool = False


class AcademyTrack(BaseModel):
    key: str
    role: str
    title: str
    icon: str
    summary: str
    objectives: list[str]
    difficulty: str
    estimated_minutes: int
    estimated_label: str
    module_count: int
    modules: list[AcademyModule]
    completed_modules: int
    remaining_modules: int
    remaining_minutes: int
    remaining_label: str
    completion_percent: int
    status: str
    next_module: str | None = None
    badge: AcademyBadge


class AcademyTracksResponse(BaseModel):
    items: list[AcademyTrack]
    total: int


class AcademyTotals(BaseModel):
    tracks: int
    modules: int
    badges: int
    estimated_minutes: int
    estimated_label: str


class AcademyOverall(BaseModel):
    completion_percent: int
    tracks_completed: int
    badges_earned: int
    is_graduate: bool


class AcademyDashboard(BaseModel):
    tracks: list[AcademyTrack]
    badges: list[AcademyBadge]
    totals: AcademyTotals
    overall: AcademyOverall


class AcademyProgressRequest(BaseModel):
    completed: list[str] = []


# --------------------------------------------------------------------------- #
# Sprint 56E.4 — Time To Value Optimization                                    #
# --------------------------------------------------------------------------- #
class TTVStep(BaseModel):
    order: int
    action: str
    detail: str
    expected_result: str
    estimated_minutes: int


class TTVChecklistItem(BaseModel):
    id: str
    label: str
    completed: bool = False


class TTVExperience(BaseModel):
    key: str
    title: str
    milestone: str
    module: str
    route: str
    icon: str
    goal: str
    prerequisites: list[str]
    steps: list[TTVStep]
    step_count: int
    expected_outcome: str
    criteria_count: int
    estimated_minutes: int
    within_time_to_value: bool
    time_to_value_budget: int
    success_checklist: list[TTVChecklistItem]
    completed_criteria: int
    remaining_criteria: int
    completion_percent: int
    status: str
    next_criterion: str | None = None
    value_reached: bool


class TTVExperiencesResponse(BaseModel):
    items: list[TTVExperience]
    total: int


class TTVTotals(BaseModel):
    experiences: int
    time_to_value_budget: int
    fastest_minutes: int
    slowest_minutes: int
    all_within_budget: bool


class TTVOverall(BaseModel):
    completion_percent: int
    milestones_reached: int
    milestones_total: int
    first_value_reached: bool
    fully_activated: bool


class TTVDashboard(BaseModel):
    experiences: list[TTVExperience]
    totals: TTVTotals
    overall: TTVOverall


class TTVProgressRequest(BaseModel):
    completed: list[str] = []


# --------------------------------------------------------------------------- #
# Sprint 56E.5 — Demo Experience Platform                                      #
# --------------------------------------------------------------------------- #
class DemoScene(BaseModel):
    order: int
    title: str
    module: str
    route: str
    duration_minutes: int
    focus: str
    narration: str
    action: str
    talking_points: list[str]
    presenter_notes: str
    expected_outcome: str
    screenshot_id: str
    screenshot_url: str


class DemoScenario(BaseModel):
    key: str
    audience: str
    title: str
    persona: str
    icon: str
    summary: str
    duration_minutes: int
    objectives: list[str]
    scenes: list[DemoScene]
    scene_count: int
    talking_points: list[str]
    presenter_notes: str
    expected_outcomes: list[str]
    modules: list[str]


class DemoScenarioSummary(BaseModel):
    key: str
    audience: str
    title: str
    persona: str
    icon: str
    summary: str
    duration_minutes: int
    scene_count: int
    objectives: list[str]


class DemoTotals(BaseModel):
    scenarios: int
    audiences: list[str]
    total_scenes: int
    shortest_minutes: int
    longest_minutes: int


class DemoDashboard(BaseModel):
    scenarios: list[DemoScenarioSummary]
    totals: DemoTotals


class DemoScriptLine(BaseModel):
    order: int
    title: str
    route: str
    duration_minutes: int
    say: str
    do: str
    talking_points: list[str]
    presenter_notes: str
    expected_outcome: str
    screenshot_url: str


class DemoSalesMode(BaseModel):
    key: str
    audience: str
    title: str
    persona: str
    duration_minutes: int
    presenter_notes: str
    objectives: list[str]
    expected_outcomes: list[str]
    script: list[DemoScriptLine]


class DemoStateRequest(BaseModel):
    action: str = "advance"
    completed: list[str] = []
    started_at: str | None = None


class DemoRunState(BaseModel):
    key: str
    title: str
    audience: str
    action: str
    status: str
    total_scenes: int
    completed_scenes: int
    completed_scene_ids: list[str]
    completion_percentage: int
    current_scene_index: int
    current_scene: DemoScene | None = None
    started_at: str | None = None
    completed_at: str | None = None


# --------------------------------------------------------------------------- #
# Sprint 57A — Adoption Analytics                                              #
# --------------------------------------------------------------------------- #
class AdoptionScores(BaseModel):
    adoption_score: int
    documentation_score: int
    training_score: int
    success_score: int


class AdoptionCounts(BaseModel):
    guide_views: int
    tour_starts: int
    tour_completions: int
    academy_tracks_tracked: int
    academy_average_progress: int
    video_views: int
    documentation_searches: int
    feature_adoptions: int
    events_analyzed: int


class FeatureUsage(BaseModel):
    key: str
    name: str
    route: str
    guide_views: int
    feature_uses: int
    video_views: int
    usage_score: int


class DropOffPoint(BaseModel):
    entity: str
    label: str
    type: str
    reached: int
    converted: int
    drop_off_rate: int
    detail: str


class CustomerHealth(BaseModel):
    status: str
    success_score: int
    risk_signals: list[str]
    top_struggle: str | None = None


class AdoptionDashboard(BaseModel):
    scores: AdoptionScores
    counts: AdoptionCounts
    most_used_features: list[FeatureUsage]
    least_used_features: list[FeatureUsage]
    drop_off_points: list[DropOffPoint]
    customer_health: CustomerHealth
    event_types: list[str]


class AdoptionEvent(BaseModel):
    type: str
    target: str
    value: int = 1


class AdoptionAnalyzeRequest(BaseModel):
    events: list[AdoptionEvent] = []


# --------------------------------------------------------------------------- #
# Sprint 56F.1 — Documentation Content Audit Engine                            #
# --------------------------------------------------------------------------- #
class AuditMetrics(BaseModel):
    word_count: int
    screenshot_count: int
    step_count: int
    faq_count: int
    troubleshooting_count: int
    example_count: int


class AuditFlags(BaseModel):
    thin_content: bool
    generic_content: bool
    missing_screenshots: bool
    missing_expected_results: bool
    missing_business_value: bool
    missing_examples: bool
    missing_troubleshooting: bool
    missing_faqs: bool


class GuideAudit(BaseModel):
    key: str
    name: str
    route: str
    quality_score: int
    level: str
    metrics: AuditMetrics
    flags: AuditFlags
    issue_count: int
    issues: list[str]
    recommendations: list[str]


class WeakGuide(BaseModel):
    key: str
    name: str
    route: str
    quality_score: int
    level: str
    issue_count: int
    issues: list[str]


class AuditSummary(BaseModel):
    guides_audited: int
    average_score: int
    production_ready: int
    weak_guides: int
    total_issues: int


class AuditReport(BaseModel):
    summary: AuditSummary
    level_distribution: dict[str, int]
    issue_totals: dict[str, int]
    weak_guides: list[WeakGuide]
    guides: list[GuideAudit]


# --- Sprint 56F.2: Customer Documentation Rewrite Engine ---


class RewriteSection(BaseModel):
    number: int
    title: str
    body: str
    bullets: list[str] = []


class RewriteStep(BaseModel):
    order: int
    action: str
    why: str
    screenshot: str
    expected_result: str
    common_mistake: str


class RewriteScoreLevel(BaseModel):
    level: str
    meaning: str


class RewriteScoreGroup(BaseModel):
    name: str
    description: str
    levels: list[RewriteScoreLevel]


class RewriteTroubleshooting(BaseModel):
    problem: str
    cause: str
    resolution: str


class RewriteFaq(BaseModel):
    question: str
    answer: str


class RewriteRelated(BaseModel):
    key: str
    name: str
    route: str


class RewriteGuide(BaseModel):
    key: str
    name: str
    route: str
    navigation_path: str
    sections: list[RewriteSection]
    walkthrough: list[RewriteStep]
    results_interpretation: list[RewriteScoreGroup]
    troubleshooting: list[RewriteTroubleshooting]
    faqs: list[RewriteFaq]
    related_features: list[RewriteRelated]
    next_steps: list[str]
    word_count: int
    step_count: int
    faq_count: int
    meets_word_target: bool
    meets_step_minimum: bool
    meets_faq_minimum: bool


class RewriteGuideSummary(BaseModel):
    key: str
    name: str
    route: str
    navigation_path: str
    word_count: int
    step_count: int
    faq_count: int
    meets_word_target: bool
    meets_step_minimum: bool
    meets_faq_minimum: bool


class RewriteGuidesResponse(BaseModel):
    guides: list[RewriteGuideSummary]


class RewriteQualityRow(BaseModel):
    key: str
    name: str
    word_count: int
    step_count: int
    faq_count: int
    meets_word_target: bool
    meets_step_minimum: bool
    meets_faq_minimum: bool


class RewriteQualitySummary(BaseModel):
    guides: int
    all_meet_word_target: bool
    all_meet_step_minimum: bool
    all_meet_faq_minimum: bool
    average_words: int


class RewriteQualityReport(BaseModel):
    items: list[RewriteQualityRow]
    summary: RewriteQualitySummary


# --- Sprint 56F.3: Screenshot Quality Validation Platform ---


class ScreenshotChecks(BaseModel):
    file_exists: bool
    image_loads: bool
    route_valid: bool
    displayed_in_ui: bool
    belongs_to_guide: bool


class ScreenshotValidation(BaseModel):
    name: str
    caption: str
    route: str
    guide_id: str
    asset_url: str
    checks: ScreenshotChecks
    status: str
    supplemental: bool


class ScreenshotGuideRow(BaseModel):
    id: str
    key: str
    name: str
    type: str
    route: str
    minimum: int
    required: int
    available: int
    missing: int
    broken: int
    invalid: int
    valid: int
    coverage_percent: int
    meets_minimum: bool
    declared_count: int
    generated_count: int


class ScreenshotGuideDetail(ScreenshotGuideRow):
    screenshots: list[ScreenshotValidation]


class ScreenshotTypeMetric(BaseModel):
    required: int
    available: int
    missing: int
    broken: int
    invalid: int
    valid: int
    guides: int
    minimum_per_guide: int
    guides_below_minimum: list[str]
    coverage_percent: int


class ScreenshotValidationSummary(BaseModel):
    required: int
    available: int
    missing: int
    broken: int
    invalid: int
    valid: int
    guides: int
    coverage_percent: int
    coverage_target: int
    coverage_meets_target: bool
    broken_zero: bool
    guides_below_minimum: int
    release_decision: str
    release_blocked: bool


class ScreenshotFailure(BaseModel):
    guide_id: str
    name: str
    status: str
    checks: ScreenshotChecks


class ScreenshotValidationReport(BaseModel):
    summary: ScreenshotValidationSummary
    rules: dict[str, int]
    by_type: dict[str, ScreenshotTypeMetric]
    guides: list[ScreenshotGuideRow]
    failures: list[ScreenshotFailure]


# --- Sprint 56F.4: Customer Success Playbooks ---


class PlaybookStep(BaseModel):
    order: int
    title: str
    description: str
    navigation: str
    route: str
    screenshot: str
    expected_screen: list[str]
    expected_result: str
    common_issues: list[str]
    recovery: list[str]


class PlaybookScreenshot(BaseModel):
    name: str
    caption: str
    route: str
    expected_screen: list[str]
    asset_url: str
    route_valid: bool
    supplemental: bool


class PlaybookTroubleshooting(BaseModel):
    problem: str
    resolution: str


class CustomerPlaybook(BaseModel):
    key: str
    name: str
    overview: str
    business_goal: str
    prerequisites: list[str]
    navigation: list[str]
    steps: list[PlaybookStep]
    screenshots: list[PlaybookScreenshot]
    screenshot_count: int
    expected_screens: list[str]
    expected_results: list[str]
    common_issues: list[str]
    troubleshooting: list[PlaybookTroubleshooting]
    success_criteria: list[str]
    estimated_minutes: int
    estimated_completion_time: str
    export_formats: list[str]
    self_service: bool


class CustomerPlaybookSummary(BaseModel):
    key: str
    name: str
    overview: str
    business_goal: str
    screenshot_count: int
    estimated_completion_time: str
    estimated_minutes: int
    export_formats: list[str]
    self_service: bool


class PlaybooksOverview(BaseModel):
    playbooks: int
    all_self_service: bool
    min_screenshots: int
    export_formats: list[str]


class CustomerPlaybooksResponse(BaseModel):
    summary: PlaybooksOverview
    playbooks: list[CustomerPlaybookSummary]


# --- Sprint 56F.5: Documentation Excellence Certification ---


class CertificationDimension(BaseModel):
    key: str
    label: str
    score: int
    signal: str
    source: str


class CertificationScores(BaseModel):
    technical_score: int
    content_score: int
    screenshot_score: int
    training_score: int
    customer_success_score: int
    overall_score: int


class Certification(BaseModel):
    level: str
    overall_score: int
    target: int
    meets_target: bool
    self_service_ready: bool
    thresholds: dict[str, int]


class CertificationHeadlineStats(BaseModel):
    guides_certified: int
    modules: int
    training_videos: int
    academy_tracks: int
    playbooks: int
    screenshot_coverage: int
    broken_screenshots: int
    audit_average: int


class CertificationDashboard(BaseModel):
    certification: Certification
    scores: CertificationScores
    headline_stats: CertificationHeadlineStats
    strengths: list[CertificationDimension]
    opportunities: list[CertificationDimension]


class CertificationReport(BaseModel):
    certification: Certification
    scores: CertificationScores
    dimensions: list[CertificationDimension]
    dashboard: CertificationDashboard


# --- Sprint 56F.7: Screenshot Asset Path Audit ---


class ScreenshotAuditItem(BaseModel):
    screenshot_id: str
    filename: str
    image_path: str
    article_id: str
    module: str
    url: str
    file_exists: bool
    static_route_valid: bool
    url_resolves: bool
    served_dynamically: bool
    status: str
    root_cause: str


class ScreenshotAuditCounts(BaseModel):
    total_references: int
    valid_files: int
    missing_files: int
    broken_urls: int
    invalid_static_routes: int


class ScreenshotAuditSummary(BaseModel):
    total_references: int
    resolving: int
    served_dynamically: int
    backed_by_static_file: int
    all_resolve: bool
    failure_count: int
    serving_prefix: str
    asset_directory: str


class ScreenshotAuditReport(BaseModel):
    report: ScreenshotAuditCounts
    summary: ScreenshotAuditSummary
    failures: list[ScreenshotAuditItem]
    screenshots: list[ScreenshotAuditItem]


# --- Sprint 56F.8: Documentation Image Rendering Verification ---


class BrokenImage(BaseModel):
    article_id: str
    article_title: str
    stored_url: str
    expected_url: str
    root_cause: str


class ImageRenderingCounts(BaseModel):
    article_count: int
    images_rendered: int
    images_broken: int
    stale_references: int
    wrong_base_path: int
    frontend_rendering_errors: int


class ImageRenderingSummary(BaseModel):
    total_images: int
    all_render: bool
    canonical_prefix: str


class ImageRenderingReport(BaseModel):
    report: ImageRenderingCounts
    summary: ImageRenderingSummary
    broken: list[BrokenImage]


class ImageRenderingRepairResult(BaseModel):
    articles_updated: int
    images_fixed: int
