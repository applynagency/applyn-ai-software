"""AI Playground (Sprint 61D).

Developer-facing comparisons that all run through the gateway: prompt testing,
model comparison, temperature comparison, provider comparison and tool debugging.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.tools import ToolContext, ToolRuntime
from app.ai.types import LLMMessage, LLMRequest


class PlaygroundService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.gateway = AIGateway(session)

    async def _run(self, *, prompt: str, system: str | None, provider: str | None,
                   model: str | None, temperature: float, organization_id: str | None,
                   feature: str = "playground") -> dict:
        req = LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)], system=system,
            provider=provider, model=model, temperature=temperature,
            feature=feature, organization_id=organization_id,
        )
        resp = await self.gateway.complete(req)
        return {
            "provider": resp.provider, "model": resp.model, "temperature": temperature,
            "text": resp.text, "mode": resp.mode, "usage": resp.usage.as_dict(),
            "cost_usd": round(resp.cost_usd, 6), "latency_ms": round(resp.latency_ms, 2),
            "cached": resp.cached,
        }

    async def test_prompt(
        self, *, prompt: str, system: str | None = None, provider: str | None = None,
        model: str | None = None, temperature: float = 0.2,
        organization_id: str | None = None,
    ) -> dict:
        return await self._run(prompt=prompt, system=system, provider=provider,
                               model=model, temperature=temperature,
                               organization_id=organization_id)

    async def compare_models(
        self, *, prompt: str, models: list[dict], system: str | None = None,
        temperature: float = 0.2, organization_id: str | None = None,
    ) -> list[dict]:
        """``models`` = [{"provider": ..., "model": ...}, ...]."""
        results = []
        for m in models:
            results.append(await self._run(
                prompt=prompt, system=system, provider=m.get("provider"),
                model=m.get("model"), temperature=temperature,
                organization_id=organization_id))
        return results

    async def compare_temperatures(
        self, *, prompt: str, temperatures: list[float], provider: str | None = None,
        model: str | None = None, system: str | None = None,
        organization_id: str | None = None,
    ) -> list[dict]:
        results = []
        for temp in temperatures:
            results.append(await self._run(
                prompt=prompt, system=system, provider=provider, model=model,
                temperature=temp, organization_id=organization_id))
        return results

    async def compare_providers(
        self, *, prompt: str, providers: list[str], system: str | None = None,
        temperature: float = 0.2, organization_id: str | None = None,
    ) -> list[dict]:
        results = []
        for provider in providers:
            results.append(await self._run(
                prompt=prompt, system=system, provider=provider, model=None,
                temperature=temperature, organization_id=organization_id))
        return results

    async def debug_tool(
        self, *, name: str, args: dict, organization_id: str | None = None,
        user_id: str | None = None, approved: bool = False,
    ) -> dict:
        ctx = ToolContext(session=self.session, organization_id=organization_id,
                          user_id=user_id)
        result = await ToolRuntime(ctx).execute(name, args, approved=approved)
        return result.as_dict()
