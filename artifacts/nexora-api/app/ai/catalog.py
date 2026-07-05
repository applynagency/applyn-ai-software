"""Model catalog: pricing, latency and quality scores (Sprint 61D).

Drives both model routing (cheapest/fastest/highest-quality) and cost accounting.
Prices are USD per 1K tokens. Values are configurable at runtime via org provider
config; these are sane built-in defaults so the platform works out of the box.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str
    input_per_1k: float       # USD / 1K input tokens
    output_per_1k: float      # USD / 1K output tokens
    quality: int              # 0-100 relative answer quality
    typical_latency_ms: int   # rough p50 latency
    context_window: int = 200_000
    supports_streaming: bool = True
    supports_tools: bool = True


# Built-in catalog. Keyed by (provider, model).
CATALOG: dict[tuple[str, str], ModelSpec] = {
    # Anthropic
    ("anthropic", "claude-sonnet-4-6"): ModelSpec(
        "anthropic", "claude-sonnet-4-6", 0.003, 0.015, 93, 1400),
    ("anthropic", "claude-haiku-4"): ModelSpec(
        "anthropic", "claude-haiku-4", 0.0008, 0.004, 82, 600),
    ("anthropic", "claude-opus-4"): ModelSpec(
        "anthropic", "claude-opus-4", 0.015, 0.075, 97, 2600),
    # OpenAI
    ("openai", "gpt-4o"): ModelSpec("openai", "gpt-4o", 0.005, 0.015, 92, 1200),
    ("openai", "gpt-4o-mini"): ModelSpec("openai", "gpt-4o-mini", 0.00015, 0.0006, 80, 700),
    ("openai", "o3-mini"): ModelSpec("openai", "o3-mini", 0.0011, 0.0044, 90, 3000),
    # Azure OpenAI (same model ids, different deployment)
    ("azure_openai", "gpt-4o"): ModelSpec("azure_openai", "gpt-4o", 0.005, 0.015, 92, 1300),
    ("azure_openai", "gpt-4o-mini"): ModelSpec(
        "azure_openai", "gpt-4o-mini", 0.00015, 0.0006, 80, 800),
    # Google Gemini
    ("gemini", "gemini-2.5-pro"): ModelSpec("gemini", "gemini-2.5-pro", 0.00125, 0.005, 91, 1500),
    ("gemini", "gemini-2.5-flash"): ModelSpec(
        "gemini", "gemini-2.5-flash", 0.0003, 0.0012, 83, 500),
    # Ollama (local, free)
    ("ollama", "llama3.1"): ModelSpec(
        "ollama", "llama3.1", 0.0, 0.0, 70, 1800, supports_tools=False),
    ("ollama", "qwen2.5"): ModelSpec(
        "ollama", "qwen2.5", 0.0, 0.0, 72, 1700, supports_tools=False),
    # OpenRouter (aggregator — price varies; representative defaults)
    ("openrouter", "auto"): ModelSpec("openrouter", "auto", 0.002, 0.008, 88, 1500),
    # AWS Bedrock
    ("bedrock", "anthropic.claude-sonnet-4"): ModelSpec(
        "bedrock", "anthropic.claude-sonnet-4", 0.003, 0.015, 93, 1500),
    ("bedrock", "meta.llama3-70b"): ModelSpec(
        "bedrock", "meta.llama3-70b", 0.00099, 0.00099, 78, 1600, supports_tools=False),
}

# Default model per provider (used when only a provider is requested).
DEFAULT_MODEL: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "azure_openai": "gpt-4o",
    "gemini": "gemini-2.5-pro",
    "ollama": "llama3.1",
    "openrouter": "auto",
    "bedrock": "anthropic.claude-sonnet-4",
}

ALL_PROVIDERS = list(DEFAULT_MODEL.keys())


def get_spec(provider: str, model: str | None = None) -> ModelSpec | None:
    model = model or DEFAULT_MODEL.get(provider)
    if model is None:
        return None
    spec = CATALOG.get((provider, model))
    if spec is not None:
        return spec
    # Unknown model on a known provider — synthesize a mid-tier spec so cost/
    # routing still function for custom deployments.
    if provider in DEFAULT_MODEL:
        return ModelSpec(provider, model, 0.002, 0.008, 80, 1500)
    return None


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    spec = get_spec(provider, model)
    if spec is None:
        return 0.0
    return (input_tokens / 1000.0) * spec.input_per_1k + (
        output_tokens / 1000.0) * spec.output_per_1k


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for offline/usage accounting."""
    return max(1, len(text or "") // 4)
