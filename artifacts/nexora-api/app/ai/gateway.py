"""The AI Gateway — the single entrypoint for all AI generation (Sprint 61D).

Every AI request flows through here. Responsibilities:

* routing       — resolve provider/model via the org's routing policy
* fallback      — try candidates in order until one succeeds
* retries       — per-provider retry with exponential backoff
* caching       — versioned response cache (per org namespace)
* cost tracking — compute cost, persist a usage record, emit metrics
* telemetry     — Prometheus metrics + OpenTelemetry span
* streaming     — token streaming with the same routing/fallback front door

No feature should call a provider SDK directly; they call ``AIGateway``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import estimate_cost
from app.ai.cost import CostTracker
from app.ai.health import get_provider_health
from app.ai.providers import get_provider
from app.ai.providers.base import ProviderError
from app.ai.providers.registry import new_provider
from app.ai.routing import ModelRouter, OrgRoutingConfig, resolve_policy
from app.ai.types import LLMRequest, LLMResponse
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AIGatewayError(Exception):
    pass


def _cache_namespace(organization_id: str | None) -> str:
    return f"ai_gateway:{organization_id or 'global'}"


class AIGateway:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def _org_routing(self, organization_id: str | None) -> OrgRoutingConfig:
        policy = resolve_policy(settings.AI_PLATFORM_DEFAULT_ROUTING)
        cfg = OrgRoutingConfig(policy=policy)
        if self.session is None or organization_id is None:
            return cfg
        from sqlalchemy import select

        from app.models.ai_platform import AIProviderConfig

        row = await self.session.scalar(
            select(AIProviderConfig).where(
                AIProviderConfig.organization_id == organization_id)
        )
        if row is None:
            return cfg
        preferred = None
        if row.preferred_models:
            preferred = [tuple(pm) for pm in row.preferred_models if len(pm) == 2]
        return OrgRoutingConfig(
            policy=resolve_policy(row.routing_policy),
            enabled_providers=row.enabled_providers or None,
            preferred=preferred,
        )

    async def complete(self, req: LLMRequest) -> LLMResponse:
        """Run a completion through routing + fallback + cache + cost tracking."""
        cache_enabled = (
            settings.AI_PLATFORM_CACHE_ENABLED and req.temperature == 0.0
        )
        cache_ns = _cache_namespace(req.organization_id)
        cache_payload = req.cache_key_payload()

        if cache_enabled:
            cached = await self._cache_get(cache_ns, cache_payload)
            if cached is not None:
                cached.cached = True
                await self._track(req, cached, status="cache")
                _metric_request(cached.provider, cached.model, "cache")
                return cached

        # Token budgeting: enforce the org's daily budget before a live call.
        # Opt-in; a cache hit above is always allowed (costs nothing).
        if self.session is not None and settings.AI_TOKEN_BUDGET_ENABLED:
            from app.ai.budget import BudgetExceededError, TokenBudget

            try:
                await TokenBudget(self.session).check(req.organization_id)
            except BudgetExceededError as exc:
                _metric_request(req.provider or "budget", req.model or "budget", "budget_exceeded")
                raise AIGatewayError(str(exc)) from exc

        # Build candidate route. An explicit request provider/model takes priority.
        if req.provider:
            candidates = [(req.provider, req.model or _default_model(req.provider))]
        else:
            router = ModelRouter(await self._org_routing(req.organization_id))
            candidates = [c.as_tuple() for c in router.route()]
            # Prefer providers that have real credentials so a live model is used
            # when available (stable: preserves the policy order within groups).
            candidates.sort(key=lambda c: not _provider_configured(c[0]))
        if not settings.AI_PLATFORM_FALLBACK_ENABLED:
            candidates = candidates[:1]

        # Provider health: skip providers whose circuit breaker is open so we do
        # not waste retries on a known-bad provider. If every candidate is open
        # (total outage) we keep the original list so a half-open probe still runs.
        health = get_provider_health()
        healthy = [c for c in candidates if health.is_available(c[0])]
        if healthy:
            candidates = healthy

        last_error: Exception | None = None
        for provider_name, model in candidates:
            try:
                provider = get_provider(provider_name)
            except KeyError:
                continue
            try:
                response = await self._call_with_retries(provider, req, model)
            except ProviderError as exc:
                last_error = exc
                health.record_failure(provider_name, str(exc))
                _metric_request(provider_name, model, "error")
                logger.warning("ai_gateway_provider_failed",
                               provider=provider_name, model=model, error=str(exc))
                continue
            health.record_success(provider_name)
            response.cost_usd = estimate_cost(
                response.provider, response.model,
                response.usage.input_tokens, response.usage.output_tokens)
            if cache_enabled and response.mode != "fallback":
                await self._cache_set(cache_ns, cache_payload, response)
            await self._track(req, response, status="success")
            _metric_request(response.provider, response.model,
                            "success" if response.mode == "live" else response.mode)
            _metric_tokens(response)
            _metric_cost(response)
            return response

        raise AIGatewayError(
            f"All providers failed for feature={req.feature}: {last_error}")

    async def complete_pinned(
        self, req: LLMRequest, *, provider: str, reraise_original: bool = True,
    ) -> LLMResponse:
        """Run a completion against exactly one provider (no routing/fallback).

        Used by structured-output internal agents that require a deterministic
        provider and the provider's native exceptions for error mapping. Still
        flows through the gateway for cost tracking + telemetry. On failure the
        original provider exception is re-raised (so callers can map it) when
        ``reraise_original`` is set.
        """
        prov = new_provider(provider)
        call_req = LLMRequest(**{**req.__dict__, "provider": provider,
                                 "model": req.model or _default_model(provider)})
        start = time.perf_counter()
        try:
            response = await prov.generate(call_req)
        except ProviderError as exc:
            _metric_request(provider, call_req.model, "error")
            if reraise_original and exc.__cause__ is not None:
                raise exc.__cause__ from None
            raise AIGatewayError(str(exc)) from exc
        response.latency_ms = (time.perf_counter() - start) * 1000.0
        response.cost_usd = estimate_cost(
            response.provider, response.model,
            response.usage.input_tokens, response.usage.output_tokens)
        await self._track(req, response, status="success")
        _metric_request(response.provider, response.model,
                        "success" if response.mode == "live" else response.mode)
        _metric_tokens(response)
        _metric_cost(response)
        return response

    async def _call_with_retries(self, provider, req: LLMRequest, model: str) -> LLMResponse:
        attempts = settings.AI_PLATFORM_MAX_RETRIES + 1
        start = time.perf_counter()
        last_exc: Exception | None = None
        call_req = LLMRequest(**{**req.__dict__, "model": model, "provider": provider.name})
        for attempt in range(attempts):
            try:
                resp = await provider.generate(call_req)
                resp.latency_ms = (time.perf_counter() - start) * 1000.0
                return resp
            except ProviderError as exc:
                last_exc = exc
                if not exc.retriable or attempt == attempts - 1:
                    raise
                delay = settings.AI_PLATFORM_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                await asyncio.sleep(delay)
        raise last_exc  # pragma: no cover

    async def stream(
        self, req: LLMRequest, *, cancel: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the primary candidate (falls back to deterministic).

        ``cancel`` is an optional :class:`asyncio.Event`; when set, streaming
        stops cleanly at the next chunk boundary (client disconnects, user abort)
        so we never keep generating tokens nobody is reading.
        """
        if req.provider:
            provider_name, model = req.provider, req.model or _default_model(req.provider)
        else:
            router = ModelRouter(await self._org_routing(req.organization_id))
            provider_name, model = router.primary().as_tuple()
        provider = get_provider(provider_name)
        call_req = LLMRequest(**{**req.__dict__, "model": model, "provider": provider_name})
        cancelled = False
        async for chunk in provider.stream(call_req):
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            yield chunk
        _metric_request(provider_name, model, "stream_cancelled" if cancelled else "stream")

    # ----------------------------------------------------------- cache + cost
    async def _cache_get(self, namespace: str, payload: dict) -> LLMResponse | None:
        try:
            from app.redis import cache

            data = await cache.versioned_get(namespace, _hash_payload(payload))
            if data:
                return _response_from_dict(data)
        except Exception:  # pragma: no cover - cache optional
            return None
        return None

    async def _cache_set(self, namespace: str, payload: dict, response: LLMResponse) -> None:
        try:
            from app.redis import cache

            await cache.versioned_set(
                namespace, _hash_payload(payload), value=response.as_dict(),
                ttl=settings.AI_PLATFORM_CACHE_TTL_SECONDS)
        except Exception:  # pragma: no cover - cache optional
            pass

    async def _track(self, req: LLMRequest, response: LLMResponse, *, status: str) -> None:
        if self.session is None:
            return
        try:
            await CostTracker(self.session).record(
                organization_id=req.organization_id, feature=req.feature,
                response=response, status=status)
        except Exception:  # pragma: no cover - tracking must not break calls
            pass


def _default_model(provider: str) -> str:
    from app.ai.catalog import DEFAULT_MODEL

    return DEFAULT_MODEL.get(provider, "default")


def _provider_configured(provider: str) -> bool:
    try:
        return get_provider(provider).is_configured()
    except Exception:  # pragma: no cover
        return False


def _hash_payload(payload: dict) -> str:
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _response_from_dict(data: dict) -> LLMResponse:
    from app.ai.types import TokenUsage

    u = data.get("usage", {})
    return LLMResponse(
        text=data.get("text", ""), provider=data.get("provider", "unknown"),
        model=data.get("model", "unknown"),
        usage=TokenUsage(u.get("input_tokens", 0), u.get("output_tokens", 0)),
        mode=data.get("mode", "live"), cost_usd=data.get("cost_usd", 0.0),
        cached=True, latency_ms=data.get("latency_ms", 0.0),
        finish_reason=data.get("finish_reason"), tool_calls=data.get("tool_calls", []),
    )


# --- metrics helpers (lazy, never raise) ------------------------------------
def _metric_request(provider: str, model: str, status: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_llm_request(provider, model, status)
    except Exception:  # pragma: no cover
        pass


def _metric_tokens(response: LLMResponse) -> None:
    try:
        from app.observability import metrics

        metrics.record_ai_tokens(response.provider, response.model,
                                 response.usage.input_tokens, response.usage.output_tokens)
    except Exception:  # pragma: no cover
        pass


def _metric_cost(response: LLMResponse) -> None:
    try:
        from app.observability import metrics

        metrics.record_ai_cost(response.provider, response.model, response.cost_usd)
    except Exception:  # pragma: no cover
        pass
