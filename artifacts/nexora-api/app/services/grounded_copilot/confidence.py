"""Confidence scoring and hallucination-prevention validation.

``validate_citations`` enforces that every citation the assistant surfaces refers
to a record that was actually retrieved (the allow-set). Anything else is dropped
— so the UI can never show a fabricated source. ``score_confidence`` produces a
0-100 score from grounding signals.
"""

from __future__ import annotations


def _citation_key(citation: dict) -> tuple:
    return (citation.get("source"), citation.get("id"), citation.get("label"))


def build_allowed_set(citations: list[dict]) -> set[tuple]:
    return {_citation_key(c) for c in citations}


def validate_citations(
    citations: list[dict], allowed: set[tuple]
) -> tuple[list[dict], list[dict]]:
    """Split citations into (grounded, hallucinated) against the allow-set."""
    grounded: list[dict] = []
    hallucinated: list[dict] = []
    seen: set[tuple] = set()
    for c in citations:
        key = _citation_key(c)
        if key in allowed and key not in seen:
            grounded.append(c)
            seen.add(key)
        elif key not in allowed:
            hallucinated.append(c)
    return grounded, hallucinated


def score_confidence(
    *,
    has_evidence: bool,
    num_citations: int,
    top_similarity: float,
    num_tool_results: int,
    mode: str,
    hallucinated: int,
) -> int:
    """Heuristic 0-100 confidence from grounding strength.

    More grounded citations, stronger top RAG similarity, and successful tool
    results raise confidence; the deterministic fallback path and any
    hallucinated (dropped) citations lower it.
    """
    if not has_evidence and num_citations == 0:
        return 10

    score = 35.0
    score += min(num_citations, 5) * 9.0  # up to +45
    score += max(0.0, min(top_similarity, 1.0)) * 15.0  # up to +15
    score += min(num_tool_results, 3) * 3.0  # up to +9

    if mode == "fallback":
        score -= 12.0
    if hallucinated:
        score -= 10.0 * min(hallucinated, 3)

    return max(5, min(99, int(round(score))))
