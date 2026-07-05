"""Provider-agnostic request/response types for the AI runtime (Sprint 61D)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str

    def as_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMRequest:
    """A provider-agnostic completion request."""

    messages: list[LLMMessage]
    system: str | None = None
    model: str | None = None           # provider-specific model id (router may set)
    provider: str | None = None        # explicit provider override (router may set)
    temperature: float = 0.2
    max_tokens: int = 1024
    # Optional tool specs (OpenAI/Anthropic JSON-schema style) for tool calling.
    tools: list[dict] | None = None
    # Caller metadata for telemetry / cost attribution.
    feature: str = "generic"
    organization_id: str | None = None
    user_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def cache_key_payload(self) -> dict:
        return {
            "system": self.system,
            "messages": [m.as_dict() for m in self.messages],
            "model": self.model,
            "provider": self.provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


@dataclass
class LLMResponse:
    """A provider-agnostic completion response."""

    text: str
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    mode: str = "live"                 # "live" | "offline" | "fallback"
    cost_usd: float = 0.0
    cached: bool = False
    latency_ms: float = 0.0
    finish_reason: str | None = None
    tool_calls: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "usage": self.usage.as_dict(),
            "mode": self.mode,
            "cost_usd": round(self.cost_usd, 6),
            "cached": self.cached,
            "latency_ms": round(self.latency_ms, 2),
            "finish_reason": self.finish_reason,
            "tool_calls": self.tool_calls,
        }


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    provider: str
    model: str
    dim: int
