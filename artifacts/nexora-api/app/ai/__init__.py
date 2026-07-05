"""Nexora unified AI Platform (Sprint 61D).

A single runtime that powers every intelligent capability in Nexora. All AI
execution flows through the :class:`~app.ai.gateway.AIGateway`, which resolves a
pluggable provider via the model router, applies caching / retries / fallback,
captures token usage + cost, and emits telemetry.

Public surface:

* ``types``        — provider-agnostic request/response dataclasses
* ``providers``    — pluggable LLM providers (OpenAI, Anthropic, Azure, Gemini,
                     Ollama, OpenRouter, Bedrock) behind one interface
* ``routing``      — model routing policies + automatic fallback
* ``gateway``      — the single AI gateway every feature calls
* ``prompts``      — versioned prompt registry with org overrides
* ``tools``        — unified tool runtime (read/write/approval, sandbox, audit)
* ``agent_runtime``— planning/execution loop with checkpoints + resume
* ``memory``       — semantic/episodic/org/user long-term memory
* ``mcp``          — Model Context Protocol client/server
* ``evaluation``   — automatic AI evaluation + history
* ``cost``         — token + cost accounting per org / feature
* ``playground``   — prompt/model/temperature/provider comparison
"""

from app.ai.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

__all__ = ["LLMMessage", "LLMRequest", "LLMResponse", "TokenUsage"]
