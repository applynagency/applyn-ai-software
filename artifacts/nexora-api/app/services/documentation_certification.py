"""Sprint 56F.5 — Documentation Excellence Certification.

Measures *true* documentation quality by aggregating concrete signals from the
documentation engines built across the 56-series:

    * documentation_audit        * customer_playbooks
    * customer_rewrite           * video_training
    * screenshot_validation      * customer_success_academy

It scores ten quality dimensions, rolls them up into six headline scores
(Technical, Content, Screenshot, Training, Customer Success, Overall), assigns a
certification level (Bronze / Silver / Gold / Platinum), and produces a
Documentation Excellence Report plus a Certification Dashboard.

Deterministic and read-only. The target is an Overall Score >= 95, at which
point the documentation is certified customer-self-service ready.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_playbooks import CustomerPlaybooksEngine
from app.services.customer_rewrite import CustomerRewriteEngine
from app.services.customer_success_academy import CustomerSuccessAcademy
from app.services.customer_success_content import MODULES
from app.services.documentation_audit import DocumentationAuditEngine
from app.services.screenshot_validation import ScreenshotValidationEngine
from app.services.video_training import VideoTrainingEngine

CERTIFICATION_TARGET = 95

# Overall >= threshold earns the level (highest matching wins).
CERTIFICATION_THRESHOLDS = {
    "Platinum": 95,
    "Gold": 85,
    "Silver": 75,
    "Bronze": 0,
}

# Required minimums used as scoring baselines.
_REWRITE_TROUBLESHOOTING_MIN = 3
_VIDEOS_PER_MODULE = 3


def _pct(part: float, whole: float) -> float:
    return (part / whole * 100) if whole else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class DocumentationCertificationEngine:
    def __init__(self) -> None:
        self._audit = DocumentationAuditEngine()
        self._rewrite = CustomerRewriteEngine()
        self._screenshots = ScreenshotValidationEngine()
        self._playbooks = CustomerPlaybooksEngine()
        self._videos = VideoTrainingEngine()
        self._academy = CustomerSuccessAcademy()
        self._cache: dict[str, Any] | None = None

    # ------------------------------------------------------- raw signals
    def _signals(self) -> dict[str, Any]:
        rewrite_guides = self._rewrite.guides()
        rewrite_total = len(rewrite_guides) or 1

        audit = self._audit.report()["summary"]
        screenshots = self._screenshots.report()
        shot_summary = screenshots["summary"]
        playbooks = self._playbooks.summary()
        video_lib = self._videos.library()
        academy = self._academy.dashboard()

        modules = len(MODULES) or 1

        # Per-guide rewrite roll-ups.
        meet_steps = sum(1 for g in rewrite_guides if g["meets_step_minimum"])
        meet_words = sum(1 for g in rewrite_guides if g["meets_word_target"])
        meet_faqs = sum(1 for g in rewrite_guides if g["meets_faq_minimum"])
        full_sections = sum(1 for g in rewrite_guides if len(g["sections"]) == 15)
        with_business = sum(
            1 for g in rewrite_guides
            if any(s["number"] == 3 and s["body"].strip() for s in g["sections"])
            and any(s["number"] == 2 and s["body"].strip() for s in g["sections"])
        )
        trouble_ok = sum(
            1 for g in rewrite_guides
            if len(g["troubleshooting"]) >= _REWRITE_TROUBLESHOOTING_MIN
        )

        journey_cov = screenshots["by_type"].get("journey", {}).get("coverage_percent", 0)

        return {
            "modules": modules,
            "rewrite_total": rewrite_total,
            "meet_steps": meet_steps,
            "meet_words": meet_words,
            "meet_faqs": meet_faqs,
            "full_sections": full_sections,
            "with_business": with_business,
            "trouble_ok": trouble_ok,
            "audit_average": audit["average_score"],
            "shot_coverage": shot_summary["coverage_percent"],
            "shot_broken": shot_summary["broken"],
            "shot_below_min": shot_summary["guides_below_minimum"],
            "journey_coverage": journey_cov,
            "playbooks": playbooks["playbooks"],
            "playbooks_self_service": playbooks["all_self_service"],
            "playbook_min_shots": playbooks["min_screenshots"],
            "videos": video_lib["library_total"],
            "academy_tracks": academy["totals"]["tracks"],
            "academy_modules": academy["totals"]["modules"],
        }

    # ------------------------------------------------------- dimensions
    def _dimensions(self, s: dict[str, Any]) -> list[dict[str, Any]]:
        total = s["rewrite_total"]
        modules = s["modules"]

        technical_completeness = _pct(s["meet_steps"], total)
        content_depth = _pct(s["meet_words"], total)
        screenshot_quality = s["shot_coverage"] if s["shot_broken"] == 0 else max(0, s["shot_coverage"] - 25)
        customer_readability = _pct(s["full_sections"], total)
        video_cov = min(100.0, _pct(s["videos"], modules * _VIDEOS_PER_MODULE))
        academy_cov = _pct(s["academy_modules"], modules)
        training_value = round(0.6 * video_cov + 0.4 * academy_cov, 1)
        business_value = _pct(s["with_business"], total)
        troubleshooting_quality = _pct(s["trouble_ok"], total)
        faq_quality = _pct(s["meet_faqs"], total)
        playbook_coverage = 100.0 if s["playbooks_self_service"] and s["playbooks"] >= 5 else _pct(s["playbooks"], 5)
        journey_coverage = float(s["journey_coverage"])

        def dim(key: str, label: str, score: float, signal: str, source: str) -> dict[str, Any]:
            return {
                "key": key, "label": label, "score": round(score),
                "signal": signal, "source": source,
            }

        return [
            dim("technical_completeness", "Technical Completeness", technical_completeness,
                f"{s['meet_steps']}/{total} guides have a complete 15+ step walkthrough", "customer_rewrite"),
            dim("content_depth", "Content Depth", content_depth,
                f"{s['meet_words']}/{total} guides reach the 2000-word depth target", "customer_rewrite"),
            dim("screenshot_quality", "Screenshot Quality", screenshot_quality,
                f"{s['shot_coverage']}% screenshot coverage with {s['shot_broken']} broken", "screenshot_validation"),
            dim("customer_readability", "Customer Readability", customer_readability,
                f"{s['full_sections']}/{total} guides follow the full 15-section customer format", "customer_rewrite"),
            dim("training_value", "Training Value", training_value,
                f"{s['videos']} training videos and {s['academy_tracks']} academy tracks", "video_training + academy"),
            dim("business_value", "Business Value", business_value,
                f"{s['with_business']}/{total} guides articulate business problem and value", "customer_rewrite"),
            dim("troubleshooting_quality", "Troubleshooting Quality", troubleshooting_quality,
                f"{s['trouble_ok']}/{total} guides ship {_REWRITE_TROUBLESHOOTING_MIN}+ troubleshooting entries", "customer_rewrite"),
            dim("faq_quality", "FAQ Quality", faq_quality,
                f"{s['meet_faqs']}/{total} guides answer 15+ FAQs", "customer_rewrite"),
            dim("playbook_coverage", "Playbook Coverage", playbook_coverage,
                f"{s['playbooks']} self-service playbooks ({s['playbook_min_shots']}+ screenshots each)", "customer_playbooks"),
            dim("journey_coverage", "Journey Coverage", journey_coverage,
                f"{s['journey_coverage']}% journey screenshot coverage", "screenshot_validation"),
        ]

    # ------------------------------------------------------- scores
    def _scores(self, dims: dict[str, float]) -> dict[str, int]:
        technical = _mean([dims["technical_completeness"], dims["troubleshooting_quality"]])
        content = _mean([dims["content_depth"], dims["business_value"], dims["faq_quality"]])
        screenshot = dims["screenshot_quality"]
        training = dims["training_value"]
        customer_success = _mean([
            dims["customer_readability"], dims["playbook_coverage"], dims["journey_coverage"],
        ])
        overall = _mean([technical, content, screenshot, training, customer_success])
        return {
            "technical_score": round(technical),
            "content_score": round(content),
            "screenshot_score": round(screenshot),
            "training_score": round(training),
            "customer_success_score": round(customer_success),
            "overall_score": round(overall),
        }

    def _certify(self, overall: int) -> str:
        for level, threshold in CERTIFICATION_THRESHOLDS.items():
            if overall >= threshold:
                return level
        return "Bronze"

    # ------------------------------------------------------- build
    def _build(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache

        signals = self._signals()
        dimensions = self._dimensions(signals)
        dim_scores = {d["key"]: float(d["score"]) for d in dimensions}
        scores = self._scores(dim_scores)
        overall = scores["overall_score"]
        level = self._certify(overall)
        self_service_ready = (
            overall >= CERTIFICATION_TARGET
            and signals["shot_broken"] == 0
            and signals["shot_below_min"] == 0
            and signals["playbooks_self_service"]
        )

        ranked = sorted(dimensions, key=lambda d: d["score"], reverse=True)
        strengths = [d for d in ranked if d["score"] >= 95][:5]
        opportunities = [d for d in ranked if d["score"] < CERTIFICATION_TARGET][-5:]

        certification = {
            "level": level,
            "overall_score": overall,
            "target": CERTIFICATION_TARGET,
            "meets_target": overall >= CERTIFICATION_TARGET,
            "self_service_ready": self_service_ready,
            "thresholds": dict(CERTIFICATION_THRESHOLDS),
        }
        dashboard = {
            "certification": certification,
            "scores": scores,
            "headline_stats": {
                "guides_certified": signals["rewrite_total"],
                "modules": signals["modules"],
                "training_videos": signals["videos"],
                "academy_tracks": signals["academy_tracks"],
                "playbooks": signals["playbooks"],
                "screenshot_coverage": signals["shot_coverage"],
                "broken_screenshots": signals["shot_broken"],
                "audit_average": signals["audit_average"],
            },
            "strengths": strengths,
            "opportunities": opportunities,
        }
        self._cache = {
            "certification": certification,
            "scores": scores,
            "dimensions": dimensions,
            "dashboard": dashboard,
        }
        return self._cache

    # ------------------------------------------------------- public API
    def report(self) -> dict[str, Any]:
        return self._build()

    def dashboard(self) -> dict[str, Any]:
        return self._build()["dashboard"]
