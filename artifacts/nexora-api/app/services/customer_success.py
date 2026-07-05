"""Sprint 56A — Customer Success Documentation Platform service.

Read-only aggregation over the deterministic content catalog, the screenshot
manifest, and the documentation-quality engine. Strictly additive.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.adoption_analytics import AdoptionAnalyticsEngine
from app.services.architecture_diagrams import ArchitectureDiagramService
from app.services.customer_playbooks import CustomerPlaybooksEngine
from app.services.customer_rewrite import CustomerRewriteEngine
from app.services.customer_success_academy import CustomerSuccessAcademy
from app.services.customer_success_content import (
    JOURNEYS,
    LEARNING_PATHS,
    MODULES,
    PLAYBOOKS,
    SUCCESS_CENTER,
    get_journey,
    get_learning_path,
    get_module,
    get_playbook,
    get_success_guide,
    learning_path_progress,
)
from app.services.customer_success_ttv import TimeToValueEngine
from app.services.demo_experience import DemoExperienceEngine
from app.services.documentation_audit import DocumentationAuditEngine
from app.services.documentation_certification import DocumentationCertificationEngine
from app.services.documentation_consistency import DocumentationConsistencyService
from app.services.documentation_coverage import DocumentationCoverageDashboard
from app.services.documentation_quality import DocumentationQualityService
from app.services.documentation_release_gate import DocumentationReleaseGateService
from app.services.documentation_verification import DocumentationVerificationService
from app.services.human_documentation import HumanDocumentationEngine
from app.services.journey_documentation import JourneyDocumentationService
from app.services.journey_verification import JourneyVerificationService
from app.services.navigation_validation import NavigationValidationService
from app.services.playbook_documentation import PlaybookDocumentationService
from app.services.product_tour_engine import ProductTourEngine
from app.services.screenshot_annotation import ScreenshotAnnotationService
from app.services.screenshot_asset_audit import ScreenshotAssetAuditEngine
from app.services.screenshot_assets import ScreenshotAssetGenerator
from app.services.screenshot_capture import ScreenshotCaptureService
from app.services.screenshot_coverage import ScreenshotCoverageService
from app.services.screenshot_drift import ScreenshotDriftService
from app.services.screenshot_manifest import ScreenshotManifestService
from app.services.screenshot_reality import ScreenshotRealityValidator
from app.services.screenshot_validation import ScreenshotValidationEngine
from app.services.video_training import VideoTrainingEngine
from app.services.visual_documentation import VisualDocumentationService


def _parse_completed(completed: str | None) -> set[str]:
    if not completed:
        return set()
    return {c.strip() for c in completed.split(",") if c.strip()}


def _module_summary(module: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": module["key"],
        "name": module["name"],
        "category": module["category"],
        "route": module["route"],
        "metadata": module["metadata"],
        "screenshot_count": len(module.get("screenshots") or []),
    }


class CustomerSuccessService:
    def __init__(self) -> None:
        self.quality_engine = DocumentationQualityService()
        self.screenshot_engine = ScreenshotManifestService()
        self.coverage_engine = ScreenshotCoverageService()
        self.architecture_engine = ArchitectureDiagramService()
        self.dashboard_engine = DocumentationCoverageDashboard()
        self.capture_engine = ScreenshotCaptureService()
        self.annotation_engine = ScreenshotAnnotationService()
        self.visual_engine = VisualDocumentationService()
        self.verification_engine = DocumentationVerificationService()
        self.drift_engine = ScreenshotDriftService()
        self.navigation_engine = NavigationValidationService()
        self.journey_engine = JourneyVerificationService()
        self.journey_docs = JourneyDocumentationService()
        self.playbook_docs = PlaybookDocumentationService()
        self.consistency_engine = DocumentationConsistencyService()
        self.release_gate_engine = DocumentationReleaseGateService()
        self.asset_generator = ScreenshotAssetGenerator()
        self.tour_engine = ProductTourEngine()
        self.human_docs = HumanDocumentationEngine()
        self.screenshot_reality = ScreenshotRealityValidator()
        self.video_engine = VideoTrainingEngine()
        self.academy = CustomerSuccessAcademy()
        self.ttv = TimeToValueEngine()
        self.demo = DemoExperienceEngine()
        self.adoption = AdoptionAnalyticsEngine()
        self.doc_audit = DocumentationAuditEngine()
        self.rewrite = CustomerRewriteEngine()
        self.screenshot_validation = ScreenshotValidationEngine()
        self.playbooks_engine = CustomerPlaybooksEngine()
        self.certification = DocumentationCertificationEngine()
        self.screenshot_audit = ScreenshotAssetAuditEngine()

    # -- modules ------------------------------------------------------------ #
    def list_modules(self) -> dict[str, Any]:
        items = [_module_summary(m) for m in MODULES]
        return {"items": items, "total": len(items)}

    def get_module(self, key: str) -> dict[str, Any]:
        module = get_module(key)
        if not module:
            raise NotFoundError("Documentation module", key)
        return module

    # -- journeys ----------------------------------------------------------- #
    def list_journeys(self) -> dict[str, Any]:
        return {"items": JOURNEYS, "total": len(JOURNEYS)}

    def get_journey(self, key: str) -> dict[str, Any]:
        journey = get_journey(key)
        if not journey:
            raise NotFoundError("Journey guide", key)
        return journey

    # -- Sprint 56D.3 — journey diagrams / manuals / exports --------------- #
    def journey_diagrams(self) -> dict[str, Any]:
        return self.journey_docs.diagrams()

    def journey_manual(self, key: str) -> dict[str, Any]:
        return self.journey_docs.manual(key)

    def journey_manuals(self) -> dict[str, Any]:
        return self.journey_docs.manuals()

    def journey_export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        return self.journey_docs.export(key, fmt)

    # -- playbooks ---------------------------------------------------------- #
    def list_playbooks(self) -> dict[str, Any]:
        return {"items": PLAYBOOKS, "total": len(PLAYBOOKS)}

    def get_playbook(self, key: str) -> dict[str, Any]:
        playbook = get_playbook(key)
        if not playbook:
            raise NotFoundError("Integration playbook", key)
        return playbook

    # -- Sprint 56D.4 — playbook manuals / exports ------------------------- #
    def playbook_manual(self, key: str) -> dict[str, Any]:
        return self.playbook_docs.manual(key)

    def playbook_manuals(self) -> dict[str, Any]:
        return self.playbook_docs.manuals()

    def playbook_export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        return self.playbook_docs.export(key, fmt)

    # -- Sprint 56E.1 — interactive product tours -------------------------- #
    def list_tours(self, *, kind: str | None = None, audience: str | None = None) -> dict[str, Any]:
        return self.tour_engine.list_tours(kind=kind, audience=audience)

    def list_tour_guides(self) -> dict[str, Any]:
        items = self.tour_engine.all_tours()
        return {"items": items, "total": len(items)}

    def get_tour(self, key: str) -> dict[str, Any]:
        tour = self.tour_engine.get_tour(key)
        if not tour:
            raise NotFoundError("Product tour", key)
        return tour

    def tours_for_module(self, module: str) -> dict[str, Any]:
        return self.tour_engine.tours_for_module(module)

    def tour_state(
        self, key: str, *, action: str = "progress",
        completed: list[str] | None = None, started_at: str | None = None,
    ) -> dict[str, Any]:
        state = self.tour_engine.state(
            key, action=action, completed=completed, started_at=started_at
        )
        if state is None:
            raise NotFoundError("Product tour", key)
        return state

    # -- Sprint 56D.5 — human-written documentation ------------------------ #
    def human_guides(self) -> dict[str, Any]:
        return self.human_docs.guides()

    def human_guide(self, key: str) -> dict[str, Any]:
        return self.human_docs.guide(key)

    def human_quality(self) -> dict[str, Any]:
        return self.human_docs.quality_report()

    def human_export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        return self.human_docs.export(key, fmt)

    # -- Sprint 56D.6 — screenshot reality validation ---------------------- #
    def screenshot_reality_report(self) -> dict[str, Any]:
        return self.screenshot_reality.validate(ensure=True)

    def screenshot_release_gate(self) -> dict[str, Any]:
        return self.screenshot_reality.release_gate()

    def screenshot_reality_ensure(self) -> dict[str, Any]:
        return self.screenshot_reality.ensure_assets()

    # -- Sprint 56E.2 — video training platform ---------------------------- #
    def video_library(self, *, module: str | None = None, category: str | None = None,
                      kind: str | None = None) -> dict[str, Any]:
        return self.video_engine.library(module=module, category=category, kind=kind)

    def featured_videos(self) -> dict[str, Any]:
        return self.video_engine.featured()

    def recently_added_videos(self, limit: int = 12) -> dict[str, Any]:
        return self.video_engine.recently_added(limit)

    def video(self, video_id: str) -> dict[str, Any]:
        return self.video_engine.get(video_id)

    def videos_for_module(self, module: str) -> dict[str, Any]:
        return self.video_engine.for_module(module)

    def video_export(self, video_id: str, fmt: str) -> tuple[bytes | str, str, str]:
        return self.video_engine.export(video_id, fmt)

    # -- Sprint 56E.3 — customer success academy --------------------------- #
    def academy_dashboard(self, completed: list[str] | None = None) -> dict[str, Any]:
        return self.academy.dashboard(set(completed or []))

    def academy_tracks(self, completed: list[str] | None = None) -> dict[str, Any]:
        items = self.academy.tracks(set(completed or []))
        return {"items": items, "total": len(items)}

    def academy_track(self, key: str, completed: list[str] | None = None) -> dict[str, Any]:
        return self.academy.get_track(key, set(completed or []))

    # -- Sprint 56E.4 — time to value optimization ------------------------- #
    def ttv_dashboard(self, completed: list[str] | None = None) -> dict[str, Any]:
        return self.ttv.dashboard(set(completed or []))

    def ttv_experiences(self, completed: list[str] | None = None) -> dict[str, Any]:
        items = self.ttv.experiences(set(completed or []))
        return {"items": items, "total": len(items)}

    def ttv_experience(self, key: str, completed: list[str] | None = None) -> dict[str, Any]:
        return self.ttv.get_experience(key, set(completed or []))

    # -- Sprint 56E.5 — demo experience platform --------------------------- #
    def demo_dashboard(self) -> dict[str, Any]:
        return self.demo.dashboard()

    def demo_scenarios(self) -> dict[str, Any]:
        items = self.demo.scenarios()
        return {"items": items, "total": len(items)}

    def demo_scenario(self, key: str) -> dict[str, Any]:
        return self.demo.get_scenario(key)

    def demo_sales_mode(self, key: str) -> dict[str, Any]:
        return self.demo.sales_mode(key)

    def demo_launch(self, key: str) -> dict[str, Any]:
        return self.demo.launch(key)

    def demo_state(self, key: str, action: str, completed: list[str] | None,
                   started_at: str | None) -> dict[str, Any]:
        return self.demo.state(key, action=action, completed=completed, started_at=started_at)

    # -- Sprint 57A — adoption analytics ----------------------------------- #
    def adoption_dashboard(self) -> dict[str, Any]:
        return self.adoption.analyze()

    def adoption_analyze(self, events: list[dict[str, Any]] | None) -> dict[str, Any]:
        return self.adoption.analyze(events)

    # -- Sprint 56F.1 — documentation content audit ------------------------ #
    def documentation_audit_report(self) -> dict[str, Any]:
        return self.doc_audit.report()

    def documentation_audit_guide(self, key: str) -> dict[str, Any]:
        return self.doc_audit.audit_guide(key)

    # --- Sprint 56F.2: Customer Documentation Rewrite ---

    def rewritten_guides(self) -> list[dict[str, Any]]:
        return self.rewrite.guides()

    def rewritten_guide(self, key: str) -> dict[str, Any]:
        return self.rewrite.guide(key)

    def rewrite_quality_report(self) -> dict[str, Any]:
        return self.rewrite.quality_report()

    # --- Sprint 56F.3: Screenshot Quality Validation ---

    def screenshot_validation_report(self) -> dict[str, Any]:
        return self.screenshot_validation.report()

    def screenshot_validation_guide(self, guide_id: str) -> dict[str, Any]:
        return self.screenshot_validation.guide(guide_id)

    # --- Sprint 56F.4: Customer Success Playbooks ---

    def success_playbooks(self) -> dict[str, Any]:
        return {
            "summary": self.playbooks_engine.summary(),
            "playbooks": self.playbooks_engine.playbooks(),
        }

    def success_playbook(self, key: str) -> dict[str, Any]:
        return self.playbooks_engine.playbook(key)

    def success_playbook_export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        return self.playbooks_engine.export(key, fmt)

    # --- Sprint 56F.5: Documentation Excellence Certification ---

    def documentation_certification(self) -> dict[str, Any]:
        return self.certification.report()

    def documentation_certification_dashboard(self) -> dict[str, Any]:
        return self.certification.dashboard()

    # --- Sprint 56F.7: Screenshot Asset Path Audit ---

    def screenshot_asset_audit(self) -> dict[str, Any]:
        return self.screenshot_audit.report()

    # -- success center ----------------------------------------------------- #
    def list_success(self) -> dict[str, Any]:
        return {"items": SUCCESS_CENTER, "total": len(SUCCESS_CENTER)}

    def get_success(self, key: str) -> dict[str, Any]:
        guide = get_success_guide(key)
        if not guide:
            raise NotFoundError("Success guide", key)
        return guide

    # -- screenshots -------------------------------------------------------- #
    def screenshots(self, *, category: str | None = None) -> dict[str, Any]:
        items = self.screenshot_engine.build(category=category)
        return {"items": items, "total": len(items), "summary": self.screenshot_engine.summary()}

    # -- quality ------------------------------------------------------------ #
    def quality(self) -> dict[str, Any]:
        return self.quality_engine.report()

    # -- Sprint 56A.1 ------------------------------------------------------- #
    def dashboard(self) -> dict[str, Any]:
        return self.dashboard_engine.dashboard()

    def readiness(self) -> dict[str, Any]:
        return self.dashboard_engine.readiness()

    def screenshot_coverage(self) -> dict[str, Any]:
        return self.coverage_engine.report()

    def architecture(self) -> dict[str, Any]:
        return self.architecture_engine.list()

    def get_architecture(self, key: str) -> dict[str, Any]:
        diagram = self.architecture_engine.get(key)
        if not diagram:
            raise NotFoundError("Architecture diagram", key)
        return diagram

    def learning_paths(self, *, completed: str | None = None) -> dict[str, Any]:
        done = _parse_completed(completed)
        items = [learning_path_progress(p, done) for p in LEARNING_PATHS]
        return {"items": items, "total": len(items)}

    def get_learning_path(self, key: str, *, completed: str | None = None) -> dict[str, Any]:
        path = get_learning_path(key)
        if not path:
            raise NotFoundError("Learning path", key)
        return learning_path_progress(path, _parse_completed(completed))

    # -- Sprint 56B (visual documentation) ---------------------------------- #
    def captures(self, *, device: str | None = None, module: str | None = None,
                 capture_type: str | None = None) -> dict[str, Any]:
        items = self.capture_engine.build(device=device, module=module, capture_type=capture_type)
        return {"items": items, "total": len(items)}

    def capture_summary(self) -> dict[str, Any]:
        return self.capture_engine.summary()

    def annotations(self, *, screenshot_id: str | None = None) -> dict[str, Any]:
        if screenshot_id:
            return self.annotation_engine.get(screenshot_id)
        items = self.annotation_engine.list()
        return {"screenshot_id": "", "annotations": items, "total": len(items)}

    def annotation_summary(self) -> dict[str, Any]:
        return self.annotation_engine.summary()

    def navigation_maps(self) -> dict[str, Any]:
        return self.visual_engine.navigation_maps()

    def journey_walkthroughs(self) -> dict[str, Any]:
        return self.visual_engine.journey_walkthroughs()

    def integration_visuals(self) -> dict[str, Any]:
        return self.visual_engine.integration_visuals()

    def get_integration_visual(self, key: str) -> dict[str, Any]:
        item = self.visual_engine.get_integration_visual(key)
        if not item:
            raise NotFoundError("Integration visual", key)
        return item

    def gallery(self, **filters: str | None) -> dict[str, Any]:
        return self.visual_engine.gallery(**filters)

    def visual_coverage(self) -> dict[str, Any]:
        return self.visual_engine.coverage_dashboard()

    def visual_readiness(self) -> dict[str, Any]:
        return self.visual_engine.visual_readiness()

    # -- Sprint 56C (documentation verification) ---------------------------- #
    def verifications(self, *, status: str | None = None, module: str | None = None) -> dict[str, Any]:
        return self.verification_engine.verifications(status=status, module=module)

    def verification_summary(self) -> dict[str, Any]:
        return self.verification_engine.summary()

    def lifecycle(self) -> dict[str, Any]:
        return self.verification_engine.lifecycle()

    def lifecycle_report(self) -> dict[str, Any]:
        return self.verification_engine.lifecycle_report()

    def drift(self) -> dict[str, Any]:
        return self.drift_engine.report()

    def navigation_health(self) -> dict[str, Any]:
        return self.navigation_engine.report()

    def journey_verification(self) -> dict[str, Any]:
        return self.journey_engine.report()

    def consistency(self) -> dict[str, Any]:
        return self.consistency_engine.report()

    def release_report(self) -> dict[str, Any]:
        return self.release_gate_engine.report()

    def verification_dashboard(self) -> dict[str, Any]:
        summary = self.verification_engine.summary()
        nav = self.navigation_engine.report()
        journey = self.journey_engine.report()
        consistency = self.consistency_engine.report()
        drift = self.drift_engine.report()
        return {
            "verified_screenshots": summary["verified_screenshots"],
            "outdated_screenshots": summary["outdated_screenshots"],
            "broken_screenshots": summary["broken_screenshots"],
            "pending_screenshots": summary["pending_screenshots"],
            "navigation_health": nav["health_score"],
            "journey_health": journey["journey_health"],
            "consistency_score": consistency["consistency_score"],
            "drift_alerts": drift["items"],
            "facets": {
                "modules": sorted({m["name"] for m in MODULES}),
                "integrations": [p["key"] for p in PLAYBOOKS],
                "journeys": [j["name"] for j in JOURNEYS],
                "guide_types": ["module", "journey", "integration", "success"],
            },
        }

    # -- Sprint 56D.1 (real screenshot assets) ----------------------------- #
    def screenshot_assets(self) -> dict[str, Any]:
        return {
            "items": self.asset_generator.manifest(),
            "coverage": self.asset_generator.coverage(),
        }

    def generate_screenshot_assets(self) -> dict[str, Any]:
        return self.asset_generator.generate()

    def screenshot_svg(self, screenshot_id: str) -> str:
        return self.asset_generator.svg_for_id(screenshot_id)

    def screenshot_svg_for_route(self, route: str, shot: str, device: str) -> str:
        return self.asset_generator.svg_for_route(route, shot, device)

    def verification_readiness(self) -> dict[str, Any]:
        summary = self.verification_engine.summary()
        nav = self.navigation_engine.report()
        journey = self.journey_engine.report()
        consistency = self.consistency_engine.report()
        release = self.release_gate_engine.report()
        verified = summary["verified_percent"]
        components = [verified, nav["health_score"], journey["journey_health"],
                     consistency["consistency_score"]]
        score = round(sum(components) / len(components))
        return {
            "verified_screenshots": verified,
            "outdated_screenshots": summary["outdated_screenshots"],
            "broken_screenshots": summary["broken_screenshots"],
            "navigation_health": nav["health_score"],
            "journey_health": journey["journey_health"],
            "consistency_score": consistency["consistency_score"],
            "documentation_verification_score": score,
            "release_ready": release["release_ready"],
        }

    # -- portal ------------------------------------------------------------- #
    def portal(self) -> dict[str, Any]:
        return {
            "modules": [_module_summary(m) for m in MODULES],
            "journeys": JOURNEYS,
            "playbooks": PLAYBOOKS,
            "success_center": SUCCESS_CENTER,
            "quality": self.quality_engine.report(),
            "screenshots": self.screenshot_engine.summary(),
            "counts": {
                "modules": len(MODULES),
                "journeys": len(JOURNEYS),
                "playbooks": len(PLAYBOOKS),
                "success_center": len(SUCCESS_CENTER),
            },
        }
