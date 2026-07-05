"""Model routing policies + automatic fallback (Sprint 61D).

Given a routing policy and (optionally) an organization's provider configuration,
the router produces an ordered list of (provider, model) candidates. The gateway
tries them in order until one succeeds — that is the automatic fallback.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from app.ai.catalog import CATALOG, DEFAULT_MODEL, ModelSpec, get_spec
from app.core.config import settings


class RoutingPolicy(str, enum.Enum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    HIGHEST_QUALITY = "highest_quality"
    DETERMINISTIC = "deterministic"
    CUSTOM = "custom"


@dataclass
class RouteCandidate:
    provider: str
    model: str

    def as_tuple(self) -> tuple[str, str]:
        return (self.provider, self.model)


def _avg_cost(spec: ModelSpec) -> float:
    return (spec.input_per_1k + spec.output_per_1k) / 2.0


def _sort_key(policy: RoutingPolicy):
    if policy == RoutingPolicy.CHEAPEST:
        return lambda s: (_avg_cost(s), -s.quality)
    if policy == RoutingPolicy.FASTEST:
        return lambda s: (s.typical_latency_ms, -s.quality)
    if policy == RoutingPolicy.HIGHEST_QUALITY:
        return lambda s: (-s.quality, _avg_cost(s))
    # deterministic / custom default to quality then cost
    return lambda s: (-s.quality, _avg_cost(s))


@dataclass
class OrgRoutingConfig:
    """Resolved per-org routing inputs (from AIProviderConfig or defaults)."""

    policy: RoutingPolicy = RoutingPolicy.HIGHEST_QUALITY
    enabled_providers: list[str] | None = None     # None => all configured/known
    preferred: list[tuple[str, str]] | None = None  # explicit ordering for CUSTOM
    deterministic_seed_model: tuple[str, str] | None = None


class ModelRouter:
    def __init__(self, config: OrgRoutingConfig | None = None) -> None:
        self.config = config or OrgRoutingConfig()

    def _candidate_specs(self) -> list[ModelSpec]:
        providers = self.config.enabled_providers
        specs = []
        for (provider, model), spec in CATALOG.items():
            if providers and provider not in providers:
                continue
            specs.append(spec)
        return specs

    def route(self) -> list[RouteCandidate]:
        policy = self.config.policy

        if policy == RoutingPolicy.CUSTOM and self.config.preferred:
            ordered = [RouteCandidate(p, m) for p, m in self.config.preferred]
        elif policy == RoutingPolicy.DETERMINISTIC:
            seed = self.config.deterministic_seed_model or (
                settings.AI_PLATFORM_DEFAULT_PROVIDER,
                DEFAULT_MODEL.get(settings.AI_PLATFORM_DEFAULT_PROVIDER, "default"),
            )
            ordered = [RouteCandidate(*seed)]
        else:
            specs = sorted(self._candidate_specs(), key=_sort_key(policy))
            ordered = [RouteCandidate(s.provider, s.model) for s in specs]

        if not ordered:
            ordered = [RouteCandidate(
                settings.AI_PLATFORM_DEFAULT_PROVIDER,
                DEFAULT_MODEL.get(settings.AI_PLATFORM_DEFAULT_PROVIDER, "default"),
            )]

        # Always append the configured default as a final fallback.
        default = RouteCandidate(
            settings.AI_PLATFORM_DEFAULT_PROVIDER,
            DEFAULT_MODEL.get(settings.AI_PLATFORM_DEFAULT_PROVIDER, "default"),
        )
        if default.as_tuple() not in {c.as_tuple() for c in ordered}:
            ordered.append(default)
        return ordered

    def primary(self) -> RouteCandidate:
        return self.route()[0]


def resolve_policy(value: str | None) -> RoutingPolicy:
    if not value:
        return RoutingPolicy.HIGHEST_QUALITY
    try:
        return RoutingPolicy(value)
    except ValueError:
        return RoutingPolicy.HIGHEST_QUALITY


def is_known_model(provider: str, model: str) -> bool:
    return get_spec(provider, model) is not None
