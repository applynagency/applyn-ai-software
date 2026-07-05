"""IaC provider abstraction for Platform Engineering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.platform_engineering.types import IaCProviderType, IaCRunKind


@dataclass
class IaCPlanResult:
    add: int = 0
    change: int = 0
    destroy: int = 0
    output_preview: str = ""
    outputs: dict = field(default_factory=dict)
    drift_detected: bool = False


@dataclass
class IaCRunResult:
    success: bool
    logs: str
    plan: IaCPlanResult | None = None
    outputs: dict = field(default_factory=dict)
    state_metadata: dict = field(default_factory=dict)
    error: str | None = None
    simulated: bool = False


class IaCProvider(Protocol):
    provider_type: IaCProviderType

    def validate(self, *, working_dir: str, variables: dict) -> IaCRunResult: ...
    def fmt(self, *, working_dir: str) -> IaCRunResult: ...
    def plan(self, *, working_dir: str, variables: dict) -> IaCRunResult: ...
    def apply(self, *, working_dir: str, variables: dict) -> IaCRunResult: ...
    def destroy(self, *, working_dir: str, variables: dict) -> IaCRunResult: ...
    def refresh(self, *, working_dir: str, variables: dict) -> IaCRunResult: ...
    def graph(self, *, working_dir: str) -> IaCRunResult: ...
