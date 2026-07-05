"""Grounded LLM client (Anthropic) with retry, backoff, streaming, and fallback.

The engine performs retrieval/tool orchestration and hands this client a fully
grounded prompt (retrieve-then-read). The client's job is to turn that grounded
context into a fluent answer:

* offline (no ``ANTHROPIC_API_KEY``)  -> deterministic ``synthesizer()`` output
* live                                -> Anthropic completion (with retry/backoff)
* live failure after retries          -> deterministic ``synthesizer()`` (fallback)

Streaming yields text deltas; on any streaming error it falls back to streaming
the deterministic synthesis so the endpoint always returns a usable answer.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Errors that should NOT be retried (deterministic client/auth failures).
_NON_RETRIABLE = {
    "AuthenticationError",
    "PermissionDeniedError",
    "BadRequestError",
    "NotFoundError",
}


@dataclass
class LLMResult:
    text: str
    mode: str  # "offline" | "live" | "fallback"


def _record_llm(status: str, model: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_llm_request("anthropic", model, status)
    except Exception:  # pragma: no cover - metrics optional
        pass


def _chunk_text(text: str, size: int = 48) -> list[str]:
    text = text or ""
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


class GroundedLLMClient:
    """Copilot LLM access.

    Sprint 61D: live generation/streaming flows through the unified
    :class:`~app.ai.gateway.AIGateway` so the copilot uses the same runtime,
    routing, caching, cost tracking and telemetry as every other AI feature.
    The deterministic offline/fallback contract (``synthesizer()``) is preserved
    exactly so retrieval-grounded answers and confidence scoring are unchanged.
    """

    def __init__(self, session=None, organization_id: str | None = None):
        self._offline = not (
            settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY
        ) if settings.AI_PLATFORM_ENABLED else not settings.ANTHROPIC_API_KEY
        self._client = None
        self._session = session
        self._organization_id = organization_id

    @property
    def offline(self) -> bool:
        return self._offline

    @property
    def model(self) -> str:
        return settings.COPILOT_MODEL or settings.ANTHROPIC_MODEL

    def _ensure_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    # --------------------------------------------------------------- retry
    async def _with_retries(self, factory: Callable):
        attempts = settings.COPILOT_MAX_RETRIES + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return await factory()
            except Exception as exc:  # noqa: BLE001 - classify then re-raise/retry
                last_exc = exc
                if type(exc).__name__ in _NON_RETRIABLE or attempt == attempts - 1:
                    raise
                delay = settings.COPILOT_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "copilot_llm_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    delay=delay,
                )
                await asyncio.sleep(delay)
        raise last_exc  # pragma: no cover

    # ------------------------------------------------------------ generate
    async def generate(
        self,
        *,
        system: str,
        history: list[dict],
        user_prompt: str,
        synthesizer: Callable[[], str],
        organization_id: str | None = None,
    ) -> LLMResult:
        if self._offline:
            return LLMResult(text=synthesizer(), mode="offline")
        # Sprint 61D: route live generation through the unified AI gateway.
        if settings.AI_PLATFORM_ENABLED:
            try:
                text = await self._gateway_generate(
                    system, history, user_prompt, organization_id)
                return LLMResult(text=text, mode="live")
            except Exception as exc:  # noqa: BLE001 - degrade to deterministic answer
                logger.error("copilot_gateway_failed_fallback", error=str(exc))
                return LLMResult(text=synthesizer(), mode="fallback")
        try:
            text = await self._with_retries(
                lambda: self._live_generate(system, history, user_prompt)
            )
            _record_llm("success", self.model)
            return LLMResult(text=text, mode="live")
        except Exception as exc:  # noqa: BLE001 - degrade to deterministic answer
            _record_llm("error", self.model)
            logger.error("copilot_llm_failed_fallback", error=str(exc))
            return LLMResult(text=synthesizer(), mode="fallback")

    async def _gateway_generate(
        self, system: str, history: list[dict], user_prompt: str,
        organization_id: str | None,
    ) -> str:
        from app.ai.gateway import AIGateway
        from app.ai.types import LLMMessage, LLMRequest

        messages = [LLMMessage(role=m["role"], content=m["content"]) for m in history]
        messages.append(LLMMessage(role="user", content=user_prompt))
        req = LLMRequest(
            messages=messages, system=system, temperature=settings.COPILOT_TEMPERATURE,
            max_tokens=settings.COPILOT_MAX_TOKENS, feature="copilot",
            organization_id=organization_id or self._organization_id,
        )
        resp = await AIGateway(self._session).complete(req)
        # The copilot has its own grounded deterministic synthesizer, so a degraded
        # (offline/fallback) gateway result should trigger that grounded fallback
        # rather than returning a generic non-grounded answer.
        if resp.mode != "live":
            raise RuntimeError(f"gateway degraded: {resp.mode}")
        if not (resp.text or "").strip():
            raise RuntimeError("Empty gateway response")
        return resp.text.strip()

    async def _live_generate(
        self, system: str, history: list[dict], user_prompt: str
    ) -> str:
        from app.observability.tracing import start_as_current_span

        client = self._ensure_client()
        messages = [*history, {"role": "user", "content": user_prompt}]
        with start_as_current_span(
            "copilot.llm.request",
            {"llm.provider": "anthropic", "llm.model": self.model},
            kind="client",
        ):
            message = await client.messages.create(
                model=self.model,
                max_tokens=settings.COPILOT_MAX_TOKENS,
                temperature=settings.COPILOT_TEMPERATURE,
                system=system,
                messages=messages,
            )
        text = ""
        for block in message.content or []:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        if not text.strip():
            raise RuntimeError("Empty LLM response")
        return text.strip()

    # -------------------------------------------------------------- stream
    async def stream(
        self,
        *,
        system: str,
        history: list[dict],
        user_prompt: str,
        synthesizer: Callable[[], str],
        organization_id: str | None = None,
    ) -> AsyncIterator[str]:
        if self._offline:
            for chunk in _chunk_text(synthesizer()):
                yield chunk
            return
        if settings.AI_PLATFORM_ENABLED:
            try:
                from app.ai.gateway import AIGateway
                from app.ai.types import LLMMessage, LLMRequest

                messages = [
                    LLMMessage(role=m["role"], content=m["content"]) for m in history]
                messages.append(LLMMessage(role="user", content=user_prompt))
                req = LLMRequest(
                    messages=messages, system=system,
                    temperature=settings.COPILOT_TEMPERATURE,
                    max_tokens=settings.COPILOT_MAX_TOKENS, feature="copilot",
                    organization_id=organization_id or self._organization_id,
                )
                async for chunk in AIGateway(self._session).stream(req):
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001 - stream the deterministic answer
                logger.error("copilot_gateway_stream_failed_fallback", error=str(exc))
                for chunk in _chunk_text(synthesizer()):
                    yield chunk
                return
        try:
            async for chunk in self._live_stream(system, history, user_prompt):
                yield chunk
            _record_llm("success", self.model)
        except Exception as exc:  # noqa: BLE001 - stream the deterministic answer
            _record_llm("error", self.model)
            logger.error("copilot_llm_stream_failed_fallback", error=str(exc))
            for chunk in _chunk_text(synthesizer()):
                yield chunk

    async def _live_stream(
        self, system: str, history: list[dict], user_prompt: str
    ) -> AsyncIterator[str]:
        client = self._ensure_client()
        messages = [*history, {"role": "user", "content": user_prompt}]
        async with client.messages.stream(
            model=self.model,
            max_tokens=settings.COPILOT_MAX_TOKENS,
            temperature=settings.COPILOT_TEMPERATURE,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
