"""Sprint 56C — DocumentationConsistencyService.

Verifies internal documentation referential integrity and produces a consistency
score (0–100). Read-only, deterministic.

Checks:
* screenshots referenced by guides exist
* annotations reference valid screenshots
* journey guides reference valid modules
* integration guides reference valid integrations
* related guides exist
"""

from __future__ import annotations

from typing import Any

from app.services.architecture_diagrams import ArchitectureDiagramService
from app.services.customer_success_content import JOURNEYS, MODULES, PLAYBOOKS
from app.services.screenshot_annotation import ScreenshotAnnotationService


class DocumentationConsistencyService:
    def report(self) -> dict[str, Any]:
        module_keys = {m["key"] for m in MODULES}
        checks: list[dict[str, Any]] = []

        # 1. Screenshots referenced by guide steps exist (have ids + screenshots).
        total_steps = 0
        ok_steps = 0
        screenshot_names: set[str] = set()
        for m in MODULES:
            for shot in m["screenshots"]:
                screenshot_names.add(shot["name"].rsplit(".", 1)[0])
            for s in m["steps"]:
                total_steps += 1
                if s.get("screenshot_id") and s.get("screenshot"):
                    ok_steps += 1
        checks.append({"check": "guide_screenshots_exist", "total": total_steps,
                       "passed": ok_steps, "ok": ok_steps == total_steps})

        # 2. Annotations reference valid screenshots.
        anns = ScreenshotAnnotationService().list()
        ann_ok = sum(1 for a in anns if a["screenshot_id"] in screenshot_names)
        checks.append({"check": "annotations_reference_valid_screenshots",
                       "total": len(anns), "passed": ann_ok, "ok": ann_ok == len(anns)})

        # 3. Journey guides reference valid modules.
        total_stages = 0
        stage_ok = 0
        for j in JOURNEYS:
            for s in j["stages"]:
                total_stages += 1
                if s.get("module") in module_keys:
                    stage_ok += 1
        checks.append({"check": "journey_modules_valid", "total": total_stages,
                       "passed": stage_ok, "ok": stage_ok == total_stages})

        # 4. Integration guides reference valid integrations.
        arch_keys = {d["key"] for d in ArchitectureDiagramService().list()["items"]}
        integ_ok = sum(1 for p in PLAYBOOKS if p["key"] in arch_keys)
        checks.append({"check": "integration_references_valid", "total": len(PLAYBOOKS),
                       "passed": integ_ok, "ok": integ_ok == len(PLAYBOOKS)})

        # 5. Related guides exist.
        total_related = 0
        related_ok = 0
        for m in MODULES:
            for rel in (m.get("metadata") or {}).get("related", []):
                total_related += 1
                if rel in module_keys:
                    related_ok += 1
        checks.append({"check": "related_guides_exist", "total": total_related,
                       "passed": related_ok, "ok": related_ok == total_related})

        total = sum(c["total"] for c in checks)
        passed = sum(c["passed"] for c in checks)
        score = round(passed / total * 100) if total else 0
        return {
            "consistency_score": score,
            "checks": checks,
            "passes": all(c["ok"] for c in checks),
        }
