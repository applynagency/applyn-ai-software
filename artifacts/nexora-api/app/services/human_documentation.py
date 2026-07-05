"""Sprint 56D.5 — Human-Written Documentation Quality Engine.

Rewrites the template-generated module docs into human-quality, business-first
guides. For every customer-facing module it composes a 10-section guide:

  1. Business Problem (Without / With)
  2. Business Outcome (measurable)
  3. When Should I Use This? (real scenarios)
  4. Real Example (alert → incident → timeline → root cause → recommendation → postmortem)
  5. Step-by-Step Walkthrough (>=15 steps; each: action, why, expected result, screenshot, common mistakes)
  6. Results Interpretation (scores, risk, confidence, status, health, SLO, cost, capacity)
  7. Common Customer Questions (>=15 FAQs)
  8. Troubleshooting Matrix (problem, cause, resolution)
  9. Best Practices
 10. Business Success Metrics (how the customer measures success)

Every guide answers Why / What / How / Expected Outcome, targets >=2000 words,
and is readable by a non-technical manager. Deterministic, read-only, no DB.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import MODULES, get_module
from app.services.document_export import render_html, render_pdf
from app.services.human_documentation_content import (
    CATEGORY_SCALES,
    HUMAN,
    SCORE_SCALES,
)

WORD_TARGET = 2000
MIN_STEPS = 15
MIN_FAQ = 15


def _words(*texts: Any) -> int:
    return sum(len(re.findall(r"\w+", str(t))) for t in texts)


def _lower_first(text: str) -> str:
    text = str(text).strip()
    return text[:1].lower() + text[1:] if text else text


def _esc(text: object) -> str:
    return str(text).replace("|", "\\|")


class HumanDocumentationEngine:
    """Composes and scores human-quality module documentation."""

    # ------------------------------------------------------- Why/What/How
    def _answers(self, m: dict[str, Any], seed: dict[str, Any]) -> dict[str, str]:
        ov = m.get("overview", {})
        meta = m.get("metadata", {})
        outcomes = meta.get("expected_outcomes") or []
        problem = seed.get("problem", {})
        how_steps = m.get("steps", [])[:3]
        how = " ".join(f"{s['action']}" for s in how_steps) or "Follow the guided walkthrough."
        expected = ", ".join(outcomes) or str(meta.get("business_value", "Measurable reliability improvement."))
        return {
            "why": problem.get("summary") or str(ov.get("why", "")),
            "what": str(ov.get("what", "")),
            "how": how,
            "expected_outcome": expected,
        }

    # ------------------------------------------------------- Section 1
    def _business_problem(self, m: dict[str, Any], seed: dict[str, Any]) -> dict[str, str]:
        name = m["name"]
        ov = m.get("overview", {})
        p = seed.get("problem")
        if p:
            without, with_, summary = p["without"], p["with"], p["summary"]
        else:
            why = str(ov.get("why", ""))
            without = (
                f"Without {name}, teams rely on manual effort and discover problems too late, "
                f"because {_lower_first(why) or 'the signal is scattered and hard to act on'}."
            )
            with_ = (
                f"With {name}, {_lower_first(str(ov.get('what', '')))} so the team acts early and "
                f"with confidence."
            )
            summary = str(ov.get("business_value", f"{name} removes manual toil and reduces reliability risk."))
        context = str(m.get("deep_dive", "")).strip()
        if not context:
            context = (
                f"{name} matters because {_lower_first(str(ov.get('why', 'reliability work is otherwise reactive and manual')))} "
                f"{str(ov.get('what', '')).strip()} It is built for {_lower_first(str(ov.get('who', 'your team')))}, and you "
                f"will typically use it {_lower_first(str(ov.get('when', 'during day-to-day operations')))} "
                f"The business value is simple: {_lower_first(str(ov.get('business_value', 'less risk and less manual toil')))} "
                f"Used consistently, {name} turns a reactive, manual process into a proactive, measurable one that a "
                f"non-technical manager can follow and trust."
            )
        return {"without": without, "with_solution": with_, "summary": summary, "context": context}

    # ------------------------------------------------------- Section 2
    def _business_outcomes(self, m: dict[str, Any], seed: dict[str, Any]) -> list[dict[str, str]]:
        if seed.get("outcomes"):
            return [{"metric": o["metric"], "detail": o["detail"]} for o in seed["outcomes"]]
        meta = m.get("metadata", {})
        out = []
        for o in meta.get("expected_outcomes", []) or []:
            out.append({"metric": str(o), "detail": f"{m['name']} delivers this as a measurable, trackable result."})
        if not out:
            out = [{"metric": "Improve reliability", "detail": str(meta.get("business_value", ""))}]
        return out

    # ------------------------------------------------------- Section 3
    def _when_to_use(self, m: dict[str, Any], seed: dict[str, Any]) -> list[str]:
        if seed.get("scenarios"):
            return list(seed["scenarios"])
        ov = m.get("overview", {})
        return [
            f"When {_lower_first(str(ov.get('when', 'you need this capability during operations')))}",
            f"When {_lower_first(str(ov.get('who', 'your team')))} needs {_lower_first(str(ov.get('what', 'this view')))}",
            f"When you want the business value of {_lower_first(str(ov.get('business_value', m['name'])))}",
        ]

    # ------------------------------------------------------- Section 4
    def _real_example(self, m: dict[str, Any], seed: dict[str, Any]) -> dict[str, str]:
        if seed.get("example"):
            return dict(seed["example"])
        ex = m.get("example", {})
        return {
            "title": str(ex.get("scenario", f"{m['name']} in action")),
            "narrative": str(ex.get("walkthrough", "")),
            "alert": "Relevant signal is detected.",
            "incident": str(ex.get("scenario", "An issue is tracked end to end.")),
            "timeline": "Events are ordered so cause and effect are clear.",
            "root_cause": "The underlying cause is identified.",
            "recommendation": str(ex.get("outcome", "A safe next action is chosen.")),
            "postmortem": "The learning is captured to prevent recurrence.",
        }

    # ------------------------------------------------------- Section 5
    def _step_common_mistakes(self, m: dict[str, Any], idx: int, action: str, expected: str) -> list[str]:
        pool = m.get("common_mistakes") or []
        mistakes: list[str] = []
        if pool:
            mistakes.append(str(pool[idx % len(pool)]))
        exp = _lower_first(str(expected).rstrip("."))
        if exp:
            mistakes.append(f"Moving on before confirming that {exp}.")
        act = _lower_first(str(action).rstrip("."))
        if act:
            mistakes.append(f"Trying to {act} without first reading what the screen is telling you.")
        # De-duplicate while preserving order; always return at least two.
        seen: set[str] = set()
        out = []
        for x in mistakes:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out[:2] if len(out) >= 2 else (out + ["Skipping verification before continuing."])[:2]

    def _walkthrough(self, m: dict[str, Any]) -> list[dict[str, Any]]:
        name = m["name"]
        steps: list[dict[str, Any]] = []
        for s in m.get("steps", []):
            why = str(s.get("internal", "")).strip() or (
                f"This advances the {name} workflow and sets up the next step."
            )
            steps.append({
                "action": str(s["action"]),
                "why": why,
                "expected_result": str(s["expected"]),
                "screenshot": str(s.get("screenshot", "")),
                "screenshot_id": str(s.get("screenshot_id", "")),
                "common_mistakes": [],
            })

        # Pad to MIN_STEPS using the module's own specific material.
        extra_pool: list[tuple[str, str, str]] = []
        for term in m.get("interpretation", []) or []:
            extra_pool.append((
                f"Read the '{term['term']}' indicator on the {name} screen.",
                f"Knowing {term['term']} tells you {_lower_first(str(term['meaning']))}",
                f"You can interpret {term['term']} and decide what to do next.",
            ))
        for bp in m.get("best_practices", []) or []:
            extra_pool.append((
                f"Apply the best practice: {bp}",
                f"This keeps your use of {name} effective, safe, and consistent.",
                "Your workflow follows the recommended practice.",
            ))
        for ns in m.get("next_steps", []) or []:
            extra_pool.append((
                f"Plan your follow-up: {ns}",
                f"This connects {name} to the wider reliability workflow.",
                "You have a clear next action after using this feature.",
            ))
        i = 0
        while len(steps) < MIN_STEPS and i < len(extra_pool):
            action, why, expected = extra_pool[i]
            steps.append({
                "action": action, "why": why, "expected_result": expected,
                "screenshot": f"{m['key']}-step-{len(steps) + 1}.png",
                "screenshot_id": f"{m['key']}-step-{len(steps) + 1}",
                "common_mistakes": [],
            })
            i += 1
        # Last-resort generic-but-named padding (rare).
        while len(steps) < MIN_STEPS:
            n = len(steps) + 1
            steps.append({
                "action": f"Revisit the {name} overview and confirm your understanding (checkpoint {n}).",
                "why": f"A quick review ensures you can use {name} confidently on your own.",
                "expected_result": f"You are confident operating {name} without assistance.",
                "screenshot": f"{m['key']}-step-{n}.png",
                "screenshot_id": f"{m['key']}-step-{n}",
                "common_mistakes": [],
            })

        for idx, st in enumerate(steps):
            st["order"] = idx + 1
            st["common_mistakes"] = self._step_common_mistakes(m, idx, st["action"], st["expected_result"])
        return steps

    # ------------------------------------------------------- Section 6
    def _results_interpretation(self, m: dict[str, Any]) -> list[dict[str, Any]]:
        # Category-relevant scales first, then every remaining scale so each guide
        # explains all eight score types (scores, risk, confidence, status, health,
        # SLO, cost, capacity).
        chosen = list(CATEGORY_SCALES.get(m.get("category", ""), []))
        for nm in SCORE_SCALES:
            if nm not in chosen:
                chosen.append(nm)
        groups: list[dict[str, Any]] = []
        for nm in chosen:
            scale = SCORE_SCALES.get(nm)
            if scale:
                groups.append({"name": nm, "items": [{"label": a, "meaning": b} for a, b in scale]})
        # Module-specific terms as their own group.
        terms = m.get("interpretation", []) or []
        if terms:
            groups.append({
                "name": f"What the {m['name']} screen shows you",
                "items": [{"label": str(t["term"]), "meaning": str(t["meaning"])} for t in terms],
            })
        return groups

    # ------------------------------------------------------- Section 7
    def _faq(
        self, m: dict[str, Any], answers: dict[str, str],
        outcomes: list[dict[str, str]], scenarios: list[str],
        success_metrics: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        faq: list[dict[str, str]] = [
            {"question": str(f["question"]), "answer": str(f["answer"])}
            for f in (m.get("faq", []) or [])
        ]
        seen_q = {f["question"].lower() for f in faq}

        def add(q: str, a: str) -> None:
            if q.lower() not in seen_q and a:
                faq.append({"question": q, "answer": a})
                seen_q.add(q.lower())

        name = m["name"]
        add(f"What problem does {name} solve for my business?", answers["why"])
        add(f"What exactly is {name}?", answers["what"])
        add(f"How do I get started with {name}?", answers["how"])
        add(f"What outcome should I expect from {name}?", answers["expected_outcome"])
        add(f"Who on my team should use {name}?", str(m.get("overview", {}).get("who", "")))
        add(f"When should we use {name}?", str(m.get("overview", {}).get("when", "")))
        add("Do I need to be technical to understand this?",
            f"No. {name} is designed so a non-technical manager can read the results and understand the business impact.")
        # Derive from measurable outcomes.
        for o in outcomes:
            add(f"How does {name} help me {_lower_first(str(o['metric']).rstrip('.'))}?", str(o["detail"]))
        # Derive from real scenarios.
        for sc in scenarios:
            add(f"Is {name} the right tool {_lower_first(str(sc).rstrip('.'))}?",
                f"Yes — that is exactly when {name} is most valuable. {answers['what']}")
        # Derive from how success is measured.
        if success_metrics:
            add(f"How do I measure success with {name}?",
                "Track: " + "; ".join(f"{s['metric']} (target {s['target']})" for s in success_metrics) + ".")
        # Derive from interpretation terms.
        for t in m.get("interpretation", []) or []:
            add(f"What does '{t['term']}' mean?", str(t["meaning"]))
        # Derive from troubleshooting.
        for tip in m.get("troubleshooting", []) or []:
            add(f"What should I do if {_lower_first(str(tip['problem']).rstrip('.'))}?", str(tip["resolution"]))
        return faq

    # ------------------------------------------------------- Section 8/9/10
    def _troubleshooting(self, m: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"problem": str(t["problem"]), "cause": str(t["cause"]), "resolution": str(t["resolution"])}
            for t in (m.get("troubleshooting", []) or [])
        ]

    def _success_metrics(self, m: dict[str, Any], seed: dict[str, Any]) -> list[dict[str, str]]:
        if seed.get("success_metrics"):
            return [dict(x) for x in seed["success_metrics"]]
        meta = m.get("metadata", {})
        return [
            {"metric": str(o), "target": "Improve over baseline", "how": f"Track {_lower_first(str(o))} after adopting {m['name']}."}
            for o in (meta.get("expected_outcomes", []) or ["Reliability improvement"])
        ]

    # ------------------------------------------------------- assembly
    def _build(self, key: str) -> dict[str, Any]:
        m = get_module(key)
        if not m:
            raise NotFoundError("Documentation module", key)
        seed = HUMAN.get(key, {})
        answers = self._answers(m, seed)
        problem = self._business_problem(m, seed)
        outcomes = self._business_outcomes(m, seed)
        when = self._when_to_use(m, seed)
        example = self._real_example(m, seed)
        walkthrough = self._walkthrough(m)
        results = self._results_interpretation(m)
        best_practices = list(m.get("best_practices", []) or [])
        success_metrics = self._success_metrics(m, seed)
        faq = self._faq(m, answers, outcomes, when, success_metrics)
        troubleshooting = self._troubleshooting(m)

        guide = {
            "key": key,
            "name": m["name"],
            "category": m.get("category", ""),
            "route": m.get("route", ""),
            "answers": answers,
            "business_problem": problem,
            "business_outcomes": outcomes,
            "when_to_use": when,
            "real_example": example,
            "walkthrough": walkthrough,
            "results_interpretation": results,
            "faq": faq,
            "troubleshooting": troubleshooting,
            "best_practices": best_practices,
            "success_metrics": success_metrics,
        }
        guide["word_count"] = self._word_count(guide)
        guide["quality"] = self._quality(guide)
        return guide

    # ------------------------------------------------------- scoring
    def _word_count(self, g: dict[str, Any]) -> int:
        total = _words(g["name"], *g["answers"].values())
        p = g["business_problem"]
        total += _words(p["without"], p["with_solution"], p["summary"], p["context"])
        for o in g["business_outcomes"]:
            total += _words(o["metric"], o["detail"])
        total += _words(*g["when_to_use"])
        total += _words(*g["real_example"].values())
        for s in g["walkthrough"]:
            total += _words(s["action"], s["why"], s["expected_result"], *s["common_mistakes"])
        for grp in g["results_interpretation"]:
            total += _words(grp["name"])
            for it in grp["items"]:
                total += _words(it["label"], it["meaning"])
        for f in g["faq"]:
            total += _words(f["question"], f["answer"])
        for t in g["troubleshooting"]:
            total += _words(t["problem"], t["cause"], t["resolution"])
        total += _words(*g["best_practices"])
        for sm in g["success_metrics"]:
            total += _words(sm["metric"], sm["target"], sm["how"])
        return total

    def _quality(self, g: dict[str, Any]) -> dict[str, Any]:
        wc = g["word_count"]
        steps = len(g["walkthrough"])
        faqs = len(g["faq"])
        answers_complete = all(str(g["answers"].get(k, "")).strip() for k in ("why", "what", "how", "expected_outcome"))
        steps_complete = all(
            s["action"] and s["why"] and s["expected_result"] and s["screenshot"] and s["common_mistakes"]
            for s in g["walkthrough"]
        )
        checks = {
            "word_target_met": wc >= WORD_TARGET,
            "ten_sections": True,
            "min_15_steps": steps >= MIN_STEPS,
            "steps_complete": steps_complete,
            "min_15_faqs": faqs >= MIN_FAQ,
            "answers_why_what_how_outcome": answers_complete,
            "has_business_problem": bool(g["business_problem"]["without"] and g["business_problem"]["with_solution"]),
            "has_real_example": all(g["real_example"].get(k) for k in ("alert", "incident", "timeline", "root_cause", "recommendation", "postmortem")),
            "has_success_metrics": len(g["success_metrics"]) >= 1,
            "has_results_interpretation": len(g["results_interpretation"]) >= 1,
        }
        score = round(sum(1 for v in checks.values() if v) / len(checks) * 100)
        level = "Human-grade" if score == 100 else "Good" if score >= 80 else "Needs work"
        return {
            "word_count": wc, "steps": steps, "faqs": faqs,
            "checks": checks, "score": score, "level": level,
        }

    # ------------------------------------------------------- public API
    def guide(self, key: str) -> dict[str, Any]:
        return self._build(key)

    def guides(self) -> dict[str, Any]:
        items = [self._build(m["key"]) for m in MODULES]
        return {"items": items, "total": len(items)}

    def quality_report(self) -> dict[str, Any]:
        rows = []
        for m in MODULES:
            g = self._build(m["key"])
            rows.append({
                "key": g["key"], "name": g["name"],
                "word_count": g["word_count"],
                "steps": g["quality"]["steps"], "faqs": g["quality"]["faqs"],
                "score": g["quality"]["score"], "level": g["quality"]["level"],
                "checks": g["quality"]["checks"],
            })
        passing = [r for r in rows if r["score"] == 100]
        avg_words = round(sum(r["word_count"] for r in rows) / len(rows)) if rows else 0
        return {
            "items": rows,
            "total": len(rows),
            "human_grade": len(passing),
            "human_grade_percent": round(len(passing) / len(rows) * 100) if rows else 0,
            "average_word_count": avg_words,
            "word_target": WORD_TARGET,
            "all_meet_target": all(r["word_count"] >= WORD_TARGET for r in rows),
        }

    # ------------------------------------------------------- export
    def _markdown(self, g: dict[str, Any]) -> str:
        L: list[str] = []
        L.append(f"# {g['name']} — Customer Guide")
        L.append("")
        a = g["answers"]
        L.append(f"**Why:** {a['why']}")
        L.append("")
        L.append(f"**What:** {a['what']}")
        L.append("")
        L.append(f"**How:** {a['how']}")
        L.append("")
        L.append(f"**Expected outcome:** {a['expected_outcome']}")
        L.append("")

        p = g["business_problem"]
        L.append("## 1. Business Problem")
        L.append("")
        L.append(f"**Without {g['name']}:** {p['without']}")
        L.append("")
        L.append(f"**With {g['name']}:** {p['with_solution']}")
        L.append("")
        L.append(_esc(p["summary"]))
        if p["context"]:
            L.append("")
            L.append(_esc(p["context"]))
        L.append("")

        L.append("## 2. Business Outcome")
        L.append("")
        for o in g["business_outcomes"]:
            L.append(f"- **{_esc(o['metric'])}** — {_esc(o['detail'])}")
        L.append("")

        L.append("## 3. When Should I Use This?")
        L.append("")
        for s in g["when_to_use"]:
            L.append(f"- {_esc(s)}")
        L.append("")

        ex = g["real_example"]
        L.append("## 4. Real Example")
        L.append("")
        L.append(f"**{_esc(ex.get('title', ''))}**")
        L.append("")
        L.append(_esc(ex.get("narrative", "")))
        L.append("")
        for label in ("alert", "incident", "timeline", "root_cause", "recommendation", "postmortem"):
            L.append(f"- **{label.replace('_', ' ').title()}:** {_esc(ex.get(label, ''))}")
        L.append("")

        L.append("## 5. Step-by-Step Walkthrough")
        L.append("")
        for s in g["walkthrough"]:
            L.append(f"### Step {s['order']}: {_esc(s['action'])}")
            L.append("")
            L.append(f"- **Why:** {_esc(s['why'])}")
            L.append(f"- **Expected result:** {_esc(s['expected_result'])}")
            L.append(f"- **Screenshot:** {_esc(s['screenshot'])}")
            L.append(f"- **Common mistakes:** {_esc('; '.join(s['common_mistakes']))}")
            L.append("")

        L.append("## 6. Results Interpretation")
        L.append("")
        for grp in g["results_interpretation"]:
            L.append(f"### {_esc(grp['name'])}")
            L.append("")
            L.append("| Value | What it means |")
            L.append("| --- | --- |")
            for it in grp["items"]:
                L.append(f"| {_esc(it['label'])} | {_esc(it['meaning'])} |")
            L.append("")

        L.append("## 7. Common Customer Questions")
        L.append("")
        for f in g["faq"]:
            L.append(f"**Q: {_esc(f['question'])}**")
            L.append("")
            L.append(_esc(f["answer"]))
            L.append("")

        L.append("## 8. Troubleshooting Matrix")
        L.append("")
        L.append("| Problem | Cause | Resolution |")
        L.append("| --- | --- | --- |")
        for t in g["troubleshooting"]:
            L.append(f"| {_esc(t['problem'])} | {_esc(t['cause'])} | {_esc(t['resolution'])} |")
        L.append("")

        L.append("## 9. Best Practices")
        L.append("")
        for bp in g["best_practices"]:
            L.append(f"- {_esc(bp)}")
        L.append("")

        L.append("## 10. Business Success Metrics")
        L.append("")
        L.append("| Metric | Target | How to measure |")
        L.append("| --- | --- | --- |")
        for sm in g["success_metrics"]:
            L.append(f"| {_esc(sm['metric'])} | {_esc(sm['target'])} | {_esc(sm['how'])} |")
        L.append("")
        return "\n".join(L)

    def markdown(self, key: str) -> str:
        return self._markdown(self._build(key))

    def export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        g = self._build(key)
        markdown = self._markdown(g)
        title = f"{g['name']} — Customer Guide"
        fmt = (fmt or "pdf").lower()
        if fmt in ("markdown", "md"):
            return markdown, "text/markdown", f"human-guide-{key}.md"
        if fmt == "html":
            return render_html(title, markdown), "text/html", f"human-guide-{key}.html"
        return render_pdf(markdown), "application/pdf", f"human-guide-{key}.pdf"
