"""Provider registry (Sprint 61D).

Providers are pluggable: register a class under a name and the router/gateway can
use it. ``get_provider`` returns a cached singleton instance per provider name.
"""

from __future__ import annotations

from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.base import LLMProvider
from app.ai.providers.extra import (
    BedrockProvider,
    GeminiProvider,
    OllamaProvider,
    OpenRouterProvider,
)
from app.ai.providers.openai import AzureOpenAIProvider, OpenAIProvider

_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "azure_openai": AzureOpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
    "bedrock": BedrockProvider,
}

_INSTANCES: dict[str, LLMProvider] = {}


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    _PROVIDER_CLASSES[name] = cls
    _INSTANCES.pop(name, None)


def get_provider(name: str) -> LLMProvider:
    if name not in _PROVIDER_CLASSES:
        raise KeyError(f"Unknown AI provider: {name}")
    if name not in _INSTANCES:
        _INSTANCES[name] = _PROVIDER_CLASSES[name]()
    return _INSTANCES[name]


def new_provider(name: str) -> LLMProvider:
    """Return a FRESH provider instance (no cached SDK client).

    Used by the pinned/internal-agent path so each call builds its own client
    (important for deterministic per-call behaviour and test isolation).
    """
    if name not in _PROVIDER_CLASSES:
        raise KeyError(f"Unknown AI provider: {name}")
    return _PROVIDER_CLASSES[name]()


def available_providers() -> list[str]:
    return list(_PROVIDER_CLASSES.keys())


def configured_providers() -> list[str]:
    return [n for n in _PROVIDER_CLASSES if get_provider(n).is_configured()]


def reset_instances() -> None:
    """Drop cached provider instances (used by tests after config changes)."""
    _INSTANCES.clear()
