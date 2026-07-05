"""Sprint 56F.1 — Documentation Content Audit Engine.

Audits every customer-facing module guide, measures content depth, flags weak
content, and produces a per-guide quality score with concrete recommendations.

Measured per guide:
    word_count, screenshot_count, step_count, faq_count,
    troubleshooting_count, example_count

Flagged:
    thin content (<1500 words), generic content, missing screenshots,
    missing expected results, missing business value, missing examples,
    missing troubleshooting, missing FAQs

Quality levels:
    0-59 Poor · 60-79 Good · 80-94 Excellent · 95-100 Production Ready

Deterministic and read-only (no DB).
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import MODULES, get_module

THIN_CONTENT_WORDS = 1500

# Minimum healthy counts — below these we deduct and recommend.
_MIN_STEPS = 5
_MIN_FAQS = 5
_MIN_TROUBLESHOOTING = 3
_MIN_SCREENSHOTS = 5

# Generic / placeholder phrases that indicate templated, low-value content.
_GENERIC_MARKERS = (
    "lorem ipsum", "todo", "tbd", "placeholder", "describe the feature",
    "feature description", "coming soon", "add content here", "xxx",
)


def _level(score: int) -> str:
    if score >= 95:
        return "Production Ready"
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    return "Poor"


def _words(text: Any) -> int:
    return len(str(text).split()) if text else 0


class DocumentationAuditEngine:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------- text collection
    def _all_text(self, guide: dict[str, Any]) -> str:
        parts: list[str] = [guide.get("name", "")]
        ov = guide.get("overview", {})
        if isinstance(ov, dict):
            parts += [str(v) for v in ov.values()]
        parts += [str(p) for p in guide.get("prerequisites", [])]
        for s in guide.get("steps", []):
            parts += [str(s.get("action", "")), str(s.get("expected", "")), str(s.get("internal", ""))]
        for it in guide.get("interpretation", []):
            parts += [str(it.get("term", "")), str(it.get("meaning", ""))]
        ex = guide.get("example", {})
        if isinstance(ex, dict):
            parts += [str(v) for v in ex.values()]
        for t in guide.get("troubleshooting", []):
            parts += [str(t.get("problem", "")), str(t.get("cause", "")), str(t.get("resolution", ""))]
        parts += [str(b) for b in guide.get("best_practices", [])]
        for f in guide.get("faq", []):
            parts += [str(f.get("question", "")), str(f.get("answer", ""))]
        parts += [str(m) for m in guide.get("common_mistakes", [])]
        parts += [str(n) for n in guide.get("next_steps", [])]
        dd = guide.get("deep_dive")
        if dd:
            parts.append(str(dd))
        return " ".join(p for p in parts if p)

    # ------------------------------------------------------- metrics
    def _metrics(self, guide: dict[str, Any], text: str) -> dict[str, int]:
        steps = guide.get("steps", [])
        screenshots = guide.get("screenshots", []) or []
        step_shots = sum(1 for s in steps if s.get("screenshot"))
        ex = guide.get("example", {})
        example_count = 1 if (isinstance(ex, dict) and ex.get("scenario")) else (1 if isinstance(ex, str) and ex.strip() else 0)
        return {
            "word_count": _words(text),
            "screenshot_count": len(screenshots) + step_shots,
            "step_count": len(steps),
            "faq_count": len(guide.get("faq", [])),
            "troubleshooting_count": len(guide.get("troubleshooting", [])),
            "example_count": example_count,
        }

    # ------------------------------------------------------- flags
    def _flags(self, guide: dict[str, Any], metrics: dict[str, int], text: str) -> dict[str, bool]:
        steps = guide.get("steps", [])
        missing_expected = bool(steps) and any(not s.get("expected") for s in steps)
        if not steps:
            missing_expected = True
        ov = guide.get("overview", {}) if isinstance(guide.get("overview"), dict) else {}
        business_value = ov.get("business_value") or guide.get("metadata", {}).get("business_value")

        lowered = text.lower()
        words = lowered.split()
        unique_ratio = (len(set(words)) / len(words)) if words else 0
        has_marker = any(mk in lowered for mk in _GENERIC_MARKERS)
        # Generic = placeholder markers, or very repetitive text, or a too-thin overview.
        generic = has_marker or (len(words) > 50 and unique_ratio < 0.30) or _words(ov.get("what")) < 6

        return {
            "thin_content": metrics["word_count"] < THIN_CONTENT_WORDS,
            "generic_content": generic,
            "missing_screenshots": metrics["screenshot_count"] == 0,
            "missing_expected_results": missing_expected,
            "missing_business_value": not bool(business_value),
            "missing_examples": metrics["example_count"] == 0,
            "missing_troubleshooting": metrics["troubleshooting_count"] == 0,
            "missing_faqs": metrics["faq_count"] == 0,
        }

    # ------------------------------------------------------- score
    def _score(self, metrics: dict[str, int], flags: dict[str, bool]) -> int:
        score = 100
        # Thin content is penalised in proportion to how far short it falls.
        if flags["thin_content"]:
            shortfall = (THIN_CONTENT_WORDS - metrics["word_count"]) / THIN_CONTENT_WORDS
            score -= min(35, round(shortfall * 40))
        penalties = {
            "generic_content": 15,
            "missing_screenshots": 15,
            "missing_expected_results": 12,
            "missing_business_value": 10,
            "missing_examples": 8,
            "missing_troubleshooting": 8,
            "missing_faqs": 8,
        }
        for flag, pen in penalties.items():
            if flags[flag]:
                score -= pen
        # Soft deductions for shallow-but-present sections.
        if not flags["missing_faqs"] and metrics["faq_count"] < _MIN_FAQS:
            score -= 5
        if not flags["missing_troubleshooting"] and metrics["troubleshooting_count"] < _MIN_TROUBLESHOOTING:
            score -= 3
        if metrics["step_count"] < _MIN_STEPS:
            score -= 5
        if not flags["missing_screenshots"] and metrics["screenshot_count"] < _MIN_SCREENSHOTS:
            score -= 3
        return max(0, min(100, score))

    # ------------------------------------------------------- issues + recs
    def _issues(self, metrics: dict[str, int], flags: dict[str, bool]) -> tuple[list[str], list[str]]:
        issues: list[str] = []
        recs: list[str] = []
        if flags["thin_content"]:
            issues.append(f"Thin content: {metrics['word_count']} words (minimum {THIN_CONTENT_WORDS}).")
            recs.append(f"Expand the guide to at least {THIN_CONTENT_WORDS} words with deeper explanation and context.")
        if flags["generic_content"]:
            issues.append("Generic or templated content detected.")
            recs.append("Replace generic phrasing with specific, product-accurate detail and concrete outcomes.")
        if flags["missing_screenshots"]:
            issues.append("No screenshots.")
            recs.append("Add screenshots for each major step and the overview screen.")
        elif metrics["screenshot_count"] < _MIN_SCREENSHOTS:
            issues.append(f"Few screenshots ({metrics['screenshot_count']}).")
            recs.append(f"Add screenshots until at least {_MIN_SCREENSHOTS} are present.")
        if flags["missing_expected_results"]:
            issues.append("Steps are missing expected results.")
            recs.append("Give every step a clear expected result so customers can self-verify.")
        if flags["missing_business_value"]:
            issues.append("No business value stated.")
            recs.append("State the measurable business value this feature delivers.")
        if flags["missing_examples"]:
            issues.append("No worked example.")
            recs.append("Add a realistic end-to-end example scenario.")
        if flags["missing_troubleshooting"]:
            issues.append("No troubleshooting guidance.")
            recs.append("Add a troubleshooting matrix of common problems, causes, and resolutions.")
        elif metrics["troubleshooting_count"] < _MIN_TROUBLESHOOTING:
            issues.append(f"Sparse troubleshooting ({metrics['troubleshooting_count']} entries).")
            recs.append(f"Expand troubleshooting to at least {_MIN_TROUBLESHOOTING} entries.")
        if flags["missing_faqs"]:
            issues.append("No FAQs.")
            recs.append("Add frequently asked questions with clear answers.")
        elif metrics["faq_count"] < _MIN_FAQS:
            issues.append(f"Few FAQs ({metrics['faq_count']}).")
            recs.append(f"Add FAQs until at least {_MIN_FAQS} are present.")
        if metrics["step_count"] < _MIN_STEPS:
            issues.append(f"Few steps ({metrics['step_count']}).")
            recs.append(f"Expand the walkthrough to at least {_MIN_STEPS} steps.")
        return issues, recs

    # ------------------------------------------------------- assembly
    def _audit_one(self, guide: dict[str, Any]) -> dict[str, Any]:
        text = self._all_text(guide)
        metrics = self._metrics(guide, text)
        flags = self._flags(guide, metrics, text)
        score = self._score(metrics, flags)
        issues, recs = self._issues(metrics, flags)
        return {
            "key": guide["key"],
            "name": guide["name"],
            "route": guide.get("route", ""),
            "quality_score": score,
            "level": _level(score),
            "metrics": metrics,
            "flags": flags,
            "issue_count": len(issues),
            "issues": issues,
            "recommendations": recs,
        }

    def _build(self) -> dict[str, dict[str, Any]]:
        if self._cache is None:
            self._cache = {m["key"]: self._audit_one(m) for m in MODULES}
        return self._cache

    # ------------------------------------------------------- public API
    def audit_all(self) -> list[dict[str, Any]]:
        return sorted(self._build().values(), key=lambda g: (g["quality_score"], g["name"]))

    def audit_guide(self, key: str) -> dict[str, Any]:
        if not get_module(key):
            raise NotFoundError("Documentation guide", key)
        return self._build()[key]

    def report(self) -> dict[str, Any]:
        guides = self.audit_all()
        total = len(guides)
        distribution = {"Poor": 0, "Good": 0, "Excellent": 0, "Production Ready": 0}
        for g in guides:
            distribution[g["level"]] += 1
        flag_totals: dict[str, int] = {}
        for g in guides:
            for flag, on in g["flags"].items():
                flag_totals[flag] = flag_totals.get(flag, 0) + (1 if on else 0)
        avg = round(sum(g["quality_score"] for g in guides) / total) if total else 0
        weak = [
            {k: g[k] for k in ("key", "name", "route", "quality_score", "level", "issue_count", "issues")}
            for g in guides if g["quality_score"] < 80
        ]
        return {
            "summary": {
                "guides_audited": total,
                "average_score": avg,
                "production_ready": distribution["Production Ready"],
                "weak_guides": len(weak),
                "total_issues": sum(g["issue_count"] for g in guides),
            },
            "level_distribution": distribution,
            "issue_totals": flag_totals,
            "weak_guides": weak,
            "guides": guides,
        }
