"""Anthropic provider (Sprint 61D)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.providers.base import LLMProvider, ProviderError
from app.ai.types import LLMRequest, LLMResponse, TokenUsage
from app.core.config import settings

_NON_RETRIABLE = {
    "AuthenticationError", "PermissionDeniedError", "BadRequestError", "NotFoundError",
}


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self._client = None

    def is_configured(self) -> bool:
        return bool(settings.ANTHROPIC_API_KEY)

    def _ensure_client(self):
        if self._client is None:
            import anthropic

            # Gateway owns retries/fallback, so disable the SDK's own retry storm.
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY, max_retries=0)
        return self._client

    def _messages(self, req: LLMRequest) -> list[dict]:
        return [m.as_dict() for m in req.messages if m.role != "system"]

    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:
        client = self._ensure_client()
        try:
            message = await client.messages.create(
                model=model,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                system=req.system or "",
                messages=self._messages(req),
            )
        except Exception as exc:  # noqa: BLE001
            retriable = type(exc).__name__ not in _NON_RETRIABLE
            raise ProviderError(str(exc), retriable=retriable) from exc
        text = ""
        for block in message.content or []:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        usage = message.usage
        return LLMResponse(
            text=text.strip(), provider=self.name, model=model,
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            ),
            mode="live", finish_reason=getattr(message, "stop_reason", None),
        )

    async def _live_stream(self, req: LLMRequest, model: str) -> AsyncIterator[str]:
        client = self._ensure_client()
        async with client.messages.stream(
            model=model, max_tokens=req.max_tokens, temperature=req.temperature,
            system=req.system or "", messages=self._messages(req),
        ) as stream:
            async for text in stream.text_stream:
                yield text
