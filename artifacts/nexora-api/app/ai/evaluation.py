"""Automatic AI evaluation (Sprint 61D).

Scores a generation on hallucination risk, grounding, answer quality, tool
success, latency, token usage and cost using deterministic heuristics (no
external grader needed), and stores the result for historical reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.types import LLMResponse
from app.models.ai_platform import AIEvaluation

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


@dataclass
class EvalScores:
    hallucination_risk: float
    grounding_score: float
    answer_quality: float
    tool_success: float
    latency_ms: float
    tokens_used: int
    cost_usd: float
    passed: bool

    def as_dict(self) -> dict:
        return {
            "hallucination_risk": round(self.hallucination_risk, 4),
            "grounding_score": round(self.grounding_score, 4),
            "answer_quality": round(self.answer_quality, 4),
            "tool_success": round(self.tool_success, 4),
            "latency_ms": round(self.latency_ms, 2),
            "tokens_used": self.tokens_used,
            "cost_usd": round(self.cost_usd, 6),
            "passed": self.passed,
        }


class AIEvaluator:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def score(
        self, response: LLMResponse, *, context: str = "",
        tool_results: list[dict] | None = None,
    ) -> EvalScores:
        answer = response.text or ""
        answer_tokens = _tokens(answer)
        context_tokens = _tokens(context)

        if answer_tokens and context_tokens:
            overlap = len(answer_tokens & context_tokens) / len(answer_tokens)
        else:
            overlap = 0.0
        grounding = overlap if context else (0.5 if answer.strip() else 0.0)

        # Hallucination risk: high when ungrounded claims with no context.
        if not answer.strip():
            hallucination = 1.0
        elif context:
            hallucination = max(0.0, 1.0 - grounding)
        else:
            hallucination = 0.4  # no context to verify against

        # Answer quality: rewards adequate, structured, non-trivial answers.
        length_score = min(len(answer) / 400.0, 1.0)
        has_structure = 1.0 if any(c in answer for c in (".", ":", "-", "\n")) else 0.5
        quality = round(min(1.0, 0.5 * length_score + 0.5 * has_structure), 4)

        results = tool_results or []
        if results:
            ok = sum(1 for r in results if r.get("ok"))
            tool_success = ok / len(results)
        else:
            tool_success = 1.0  # no tools used → not penalized

        passed = (
            bool(answer.strip())
            and hallucination <= 0.6
            and quality >= 0.3
            and tool_success >= 0.5
        )
        return EvalScores(
            hallucination_risk=hallucination, grounding_score=grounding,
            answer_quality=quality, tool_success=tool_success,
            latency_ms=response.latency_ms, tokens_used=response.usage.total_tokens,
            cost_usd=response.cost_usd, passed=passed,
        )

    async def evaluate_and_store(
        self, response: LLMResponse, *, organization_id: str | None, feature: str,
        context: str = "", tool_results: list[dict] | None = None,
    ) -> AIEvaluation:
        scores = self.score(response, context=context, tool_results=tool_results)
        record = AIEvaluation(
            organization_id=organization_id, feature=feature,
            provider=response.provider, model=response.model,
            hallucination_risk=scores.hallucination_risk,
            grounding_score=scores.grounding_score,
            answer_quality=scores.answer_quality, tool_success=scores.tool_success,
            latency_ms=scores.latency_ms, tokens_used=scores.tokens_used,
            cost_usd=scores.cost_usd, passed=scores.passed, details=scores.as_dict(),
        )
        if self.session is not None:
            self.session.add(record)
            await self.session.flush()
            self._metric(scores)
        return record

    def _metric(self, scores: EvalScores) -> None:
        try:
            from app.observability import metrics

            metrics.observe_ai_evaluation(scores.grounding_score, scores.hallucination_risk)
        except Exception:  # pragma: no cover
            pass

    async def history(
        self, organization_id: str | None, *, feature: str | None = None, limit: int = 100,
    ) -> list[AIEvaluation]:
        if self.session is None:
            return []
        stmt = select(AIEvaluation)
        if organization_id is not None:
            stmt = stmt.where(AIEvaluation.organization_id == organization_id)
        if feature:
            stmt = stmt.where(AIEvaluation.feature == feature)
        stmt = stmt.order_by(AIEvaluation.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def aggregate(self, organization_id: str | None, *, days: int = 30) -> dict:
        if self.session is None:
            return {}
        stmt = select(
            func.count(AIEvaluation.id),
            func.coalesce(func.avg(AIEvaluation.grounding_score), 0.0),
            func.coalesce(func.avg(AIEvaluation.hallucination_risk), 0.0),
            func.coalesce(func.avg(AIEvaluation.answer_quality), 0.0),
            func.coalesce(func.avg(AIEvaluation.latency_ms), 0.0),
        )
        if organization_id is not None:
            stmt = stmt.where(AIEvaluation.organization_id == organization_id)
        count, grounding, halluc, quality, latency = (await self.session.execute(stmt)).one()
        return {
            "evaluations": int(count),
            "avg_grounding": round(float(grounding), 4),
            "avg_hallucination_risk": round(float(halluc), 4),
            "avg_answer_quality": round(float(quality), 4),
            "avg_latency_ms": round(float(latency), 2),
        }
