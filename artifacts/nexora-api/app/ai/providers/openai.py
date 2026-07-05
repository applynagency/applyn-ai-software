"""OpenAI + Azure OpenAI providers (Sprint 61D)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.providers.base import LLMProvider, ProviderError
from app.ai.types import LLMRequest, LLMResponse, TokenUsage
from app.core.config import settings


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client = None

    def is_configured(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    def _ensure_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
        return self._client

    def _messages(self, req: LLMRequest) -> list[dict]:
        msgs = []
        if req.system:
            msgs.append({"role": "system", "content": req.system})
        msgs.extend(m.as_dict() for m in req.messages)
        return msgs

    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:
        client = self._ensure_client()
        try:
            resp = await client.chat.completions.create(
                model=model, messages=self._messages(req),
                temperature=req.temperature, max_tokens=req.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            text=(choice.message.content or "").strip(), provider=self.name, model=model,
            usage=TokenUsage(
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            ),
            mode="live", finish_reason=getattr(choice, "finish_reason", None),
        )

    async def _live_stream(self, req: LLMRequest, model: str) -> AsyncIterator[str]:
        client = self._ensure_client()
        stream = await client.chat.completions.create(
            model=model, messages=self._messages(req), temperature=req.temperature,
            max_tokens=req.max_tokens, stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


class AzureOpenAIProvider(OpenAIProvider):
    name = "azure_openai"

    def is_configured(self) -> bool:
        return bool(settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT)

    def _ensure_client(self):
        if self._client is None:
            from openai import AsyncAzureOpenAI

            self._client = AsyncAzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                max_retries=0,
            )
        return self._client
