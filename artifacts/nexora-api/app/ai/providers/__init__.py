"""Pluggable LLM providers behind one interface (Sprint 61D).

Every provider implements :class:`LLMProvider`. Providers are pluggable via the
registry — adding a backend means registering a class, nothing else changes.
When a provider is not configured (no API key / SDK), it runs in deterministic
*offline* mode so the platform (and tests) work with zero external dependencies.
"""

from app.ai.providers.base import LLMProvider, ProviderError
from app.ai.providers.registry import (
    available_providers,
    get_provider,
    register_provider,
)

__all__ = [
    "LLMProvider",
    "ProviderError",
    "get_provider",
    "available_providers",
    "register_provider",
]
