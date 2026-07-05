"""Pipeline provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PipelineInfo:
    external_id: str
    name: str
    repository: str
    provider: str
    default_branch: str = "main"
    status: str = "ACTIVE"


@dataclass
class PipelineRunInfo:
    external_id: str
    pipeline_name: str
    status: str
    conclusion: str | None
    branch: str
    commit_sha: str
    started_at: str
    finished_at: str | None
    duration_seconds: int | None
    url: str
    logs_preview: str = ""
    artifacts: list[dict] = field(default_factory=list)


class PipelineProvider(ABC):
    provider: str

    @abstractmethod
    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        ...

    @abstractmethod
    def list_runs(self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20) -> list[PipelineRunInfo]:
        ...

    def get_run_logs(self, secret: dict, run_id: str, *, repository: str | None = None) -> str:
        return "[simulated] pipeline completed successfully\nall tests passed\n"

    def cancel_run(self, secret: dict, run_id: str, *, repository: str | None = None) -> dict:
        return {"run_id": run_id, "status": "cancelled", "simulated": True}

    def retry_run(self, secret: dict, run_id: str, *, repository: str | None = None) -> dict:
        return {"run_id": run_id, "status": "queued", "simulated": True}
