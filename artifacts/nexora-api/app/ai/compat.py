"""Anthropic-compatible client backed by the unified AIGateway (Sprint 62A).

The internal pipeline agents (`app/agents/*`) were each constructing their own
`anthropic.AsyncAnthropic` client. This module provides a drop-in replacement
whose ``.messages.create(...)`` routes through the :class:`~app.ai.gateway.AIGateway`
(pinned to Anthropic, with native exceptions preserved) so there is exactly ONE
LLM runtime and no provider SDK is constructed outside `app/ai/`. The returned
object mimics the Anthropic message shape (``.content[].text`` + ``.usage``) the
agents already parse, so agent bodies and their tests are unchanged.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.gateway import AIGateway
from app.ai.types import LLMMessage, LLMRequest


def _to_messages(messages: list[dict]) -> list[LLMMessage]:
    out: list[LLMMessage] = []
    for m in messages or []:
        content = m.get("content", "")
        if isinstance(content, list):  # anthropic block content
            content = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
        out.append(LLMMessage(role=m.get("role", "user"), content=content))
    return out


class _Messages:
    def __init__(self, client: GatewayAnthropicClient) -> None:
        self._client = client

    async def create(self, *, model=None, max_tokens=1024, system=None,
                     messages=None, temperature=0.2, **_ignored):
        req = LLMRequest(
            messages=_to_messages(messages or []), system=system, model=model,
            temperature=temperature, max_tokens=max_tokens,
            feature=self._client.feature, organization_id=self._client.organization_id,
            user_id=self._client.user_id,
        )
        resp = await AIGateway(self._client.session).complete_pinned(
            req, provider="anthropic")
        block = SimpleNamespace(type="text", text=resp.text)
        usage = SimpleNamespace(
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens)
        return SimpleNamespace(content=[block], usage=usage,
                               stop_reason=resp.finish_reason)


class GatewayAnthropicClient:
    """Drop-in for ``anthropic.AsyncAnthropic`` that routes via the gateway."""

    def __init__(self, *, session=None, organization_id: str | None = None,
                 user_id: str | None = None, feature: str = "internal_agent") -> None:
        self.session = session
        self.organization_id = organization_id
        self.user_id = user_id
        self.feature = feature
        self.messages = _Messages(self)


def gateway_anthropic_client(*, feature: str = "internal_agent") -> GatewayAnthropicClient:
    return GatewayAnthropicClient(feature=feature)
