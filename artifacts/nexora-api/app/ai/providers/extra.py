"""Additional pluggable providers: Gemini, Ollama, OpenRouter, Bedrock (Sprint 61D).

These implement the same :class:`LLMProvider` interface. Live calls use the
respective HTTP API / SDK (lazy-imported). With no credentials they degrade to
the deterministic offline response from the base class.
"""

from __future__ import annotations

from app.ai.catalog import estimate_tokens
from app.ai.providers.base import LLMProvider, ProviderError
from app.ai.types import LLMRequest, LLMResponse, TokenUsage
from app.core.config import settings


def _joined_prompt(req: LLMRequest) -> str:
    parts = []
    if req.system:
        parts.append(req.system)
    parts.extend(f"{m.role}: {m.content}" for m in req.messages)
    return "\n".join(parts)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY)

    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:  # pragma: no cover - network
        import httpx

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={settings.GEMINI_API_KEY}")
        payload = {
            "contents": [{"parts": [{"text": _joined_prompt(req)}]}],
            "generationConfig": {"temperature": req.temperature,
                                 "maxOutputTokens": req.max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        meta = data.get("usageMetadata", {})
        return LLMResponse(
            text=text.strip(), provider=self.name, model=model,
            usage=TokenUsage(meta.get("promptTokenCount", 0),
                             meta.get("candidatesTokenCount", 0)),
            mode="live",
        )


class OllamaProvider(LLMProvider):
    name = "ollama"

    def is_configured(self) -> bool:
        return bool(settings.OLLAMA_BASE_URL)

    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:  # pragma: no cover - network
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                    json={
                        "model": model,
                        "messages": ([{"role": "system", "content": req.system}] if req.system else [])
                        + [m.as_dict() for m in req.messages],
                        "stream": False,
                        "options": {"temperature": req.temperature},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
        text = data.get("message", {}).get("content", "")
        return LLMResponse(
            text=text.strip(), provider=self.name, model=model,
            usage=TokenUsage(data.get("prompt_eval_count", 0), data.get("eval_count", 0)),
            mode="live",
        )


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def is_configured(self) -> bool:
        return bool(settings.OPENROUTER_API_KEY)

    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:  # pragma: no cover - network
        import httpx

        msgs = ([{"role": "system", "content": req.system}] if req.system else []) + [
            m.as_dict() for m in req.messages]
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                    json={"model": model, "messages": msgs, "temperature": req.temperature,
                          "max_tokens": req.max_tokens},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text.strip(), provider=self.name, model=model,
            usage=TokenUsage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            mode="live",
        )


class BedrockProvider(LLMProvider):
    name = "bedrock"

    def is_configured(self) -> bool:
        return bool(settings.AWS_BEDROCK_REGION and settings.AWS_ACCESS_KEY_ID)

    async def _live_generate(self, req: LLMRequest, model: str) -> LLMResponse:  # pragma: no cover - network
        import json

        try:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=settings.AWS_BEDROCK_REGION)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": req.max_tokens,
                "temperature": req.temperature,
                "system": req.system or "",
                "messages": [m.as_dict() for m in req.messages if m.role != "system"],
            }
            resp = client.invoke_model(modelId=model, body=json.dumps(body))
            data = json.loads(resp["body"].read())
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
        text = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        return LLMResponse(
            text=text.strip(), provider=self.name, model=model,
            usage=TokenUsage(usage.get("input_tokens", estimate_tokens(_joined_prompt(req))),
                             usage.get("output_tokens", estimate_tokens(text))),
            mode="live",
        )
