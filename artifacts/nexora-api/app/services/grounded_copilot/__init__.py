"""Grounded LLM copilot.

Replaces the deterministic keyword copilot with a grounded LLM pipeline:

* ``retrieval``      — RAG over the org's reliability records (embeddings + cosine)
* ``knowledge_graph``— service dependency / blast-radius grounding facts
* ``tools``          — read-only tool registry the model can call
* ``memory``         — conversation history replayed as context
* ``confidence``     — confidence scoring + hallucination-prevention validation
* ``llm``            — Anthropic client with streaming, retry/backoff, fallback
* ``engine``         — orchestrates the above and persists conversations

Offline-safe: when ``ANTHROPIC_API_KEY`` is unset (tests/CI) it synthesizes a
grounded, deterministic answer from the retrieved evidence with no network call.
The same path is the live fallback when the LLM is unavailable.
"""

from app.services.grounded_copilot.engine import GroundedCopilotEngine

__all__ = ["GroundedCopilotEngine"]
