"""Base LLM provider interface (Sprint 61D)."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.ai.catalog import DEFAULT_MODEL, estimate_tokens
from app.ai.types import LLMRequest, LLMResponse, TokenUsage


class ProviderError(Exception):
    """Raised when a provider call fails (drives gateway retries/fallback)."""

    def __init__(self, message: str, *, retriable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.retriable = retriable


def _deterministic_answer(req: LLMRequest) -> str:
    """A stable, grounded-looking answer for offline mode.

    Echoes the salient parts of the prompt so behaviour is predictable and
    testable without any external model.
    """
    last_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )
    digest = hashlib.sha256((req.system or "" + last_user).encode()).hexdigest()[:8]
    snippet = (last_user or "").strip().replace("\n", " ")
    if len(snippet) > 240:
        snippet = snippet[:240] + "…"
    return (
        f"[offline:{digest}] Based on the provided context, here is a grounded "
        f"response to: {snippet}"
    )


class LLMProvider(ABC):
    """One pluggable model backend."""

    name: str

    @property
    def default_model(self) -> str:
        return DEFAULT_MODEL.get(self.name, "default")

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether real credentials/SDK are available for live calls."""

    async def generate(self, req: LLMRequest) -> LLMResponse:
        model = req.model or self.default_model
        if not self.is_configured():
            return self._offline_response(req, model)
        try:
            return await self._live_generate(req, model)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize to ProviderError
            raise ProviderError(str(exc)) from exc

    async def stream(self, req: LLMRequest) -> AsyncIterator[str]:
        model = req.model or self.default_model
        if not self.is_configured():
            text = _deterministic_answer(req)
            for i in range(0, len(text), 48):
                yield text[i : i + 48]
            return
        async for chunk in self._live_stream(req, model):
            yield chunk

    def _offline_response(self, req: LLMRequest, model: str) -> LLMResponse:
        text = _deterministic_answer(req)
        usage = TokenUsage(
            input_tokens=estimate_tokens((req.system or "") + " ".join(
                m.content for m in req.messages)),
            output_tokens=estimate_tokens(text),
        )
        return LLMResponse(
            text=text, provider=self.name, model=model, usage=usage,
            mode="offline", finish_reason="stop",
        )

    # Subclasses override these for real calls.
    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:  # pragma: no cover
        return self._offline_response(req, model)

    async def _live_stream(self, req: LLMRequest, model: str) -> AsyncIterator[str]:  # pragma: no cover
        text = _deterministic_answer(req)
        for i in range(0, len(text), 48):
            yield text[i : i + 48]
