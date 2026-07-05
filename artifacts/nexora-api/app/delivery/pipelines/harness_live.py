"""Live Harness NG pipeline provider."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import get_json


def _harness_status(status: str | None) -> str:
    raw = (status or "").upper()
    if raw in ("SUCCESS", "SUCCEEDED", "COMPLETED"):
        return "SUCCEEDED"
    if raw in ("FAILED", "ERROR", "ABORTED"):
        return "FAILED"
    if raw in ("RUNNING", "ACTIVE", "EXECUTING"):
        return "RUNNING"
    if raw in ("QUEUED", "PENDING"):
        return "QUEUED"
    if raw in ("CANCELLED", "CANCELED"):
        return "CANCELLED"
    return "UNKNOWN"


class HarnessProvider(PipelineProvider):
    provider = "HARNESS"

    _BASE = "https://app.harness.io"

    def _headers(self, secret: dict) -> dict[str, str]:
        return {"x-api-key": secret.get("api_key", ""), "Accept": "application/json"}

    def _org(self, secret: dict) -> str:
        return secret.get("org_identifier") or "default"

    def _project(self, secret: dict) -> str:
        return secret.get("project_identifier") or "default"

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        account = secret.get("account_id")
        api_key = secret.get("api_key")
        if not account or not api_key:
            return []
        headers = self._headers(secret)
        org = self._org(secret)
        project = self._project(secret)
        params = f"accountIdentifier={account}&orgIdentifier={org}&projectIdentifier={project}"
        data = get_json(f"{self._BASE}/pipeline/api/pipelines/list?{params}", headers=headers)
        content = (
            (data.get("data") or {}).get("content")
            or data.get("content")
            or []
        )
        pipelines: list[PipelineInfo] = []
        for pipe in content[:50]:
            if not isinstance(pipe, dict):
                continue
            ident = pipe.get("identifier") or pipe.get("name") or ""
            if not ident:
                continue
            pipelines.append(PipelineInfo(
                external_id=ident,
                name=pipe.get("name") or ident,
                repository=repository or account,
                provider=self.provider,
                status="ACTIVE",
            ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        account = secret.get("account_id")
        api_key = secret.get("api_key")
        if not account or not api_key:
            return []
        headers = self._headers(secret)
        org = self._org(secret)
        project = self._project(secret)
        params = (
            f"accountIdentifier={account}&orgIdentifier={org}"
            f"&projectIdentifier={project}&pipelineIdentifier={pipeline}&size={min(limit, 25)}"
        )
        data = get_json(
            f"{self._BASE}/pipeline/api/pipelines/execution/summary?{params}",
            headers=headers,
        )
        content = (
            (data.get("data") or {}).get("content")
            or data.get("content")
            or []
        )
        runs: list[PipelineRunInfo] = []
        for ex in content[:limit]:
            if not isinstance(ex, dict):
                continue
            status_raw = ex.get("status") or ex.get("executionStatus") or ex.get("pipelineExecutionSummary", {}).get("status")
            status = _harness_status(status_raw)
            plan = ex.get("planExecutionId") or ex.get("executionId") or ex.get("id") or ""
            started = ex.get("startTs") or ex.get("startedAt") or ""
            finished = ex.get("endTs") or ex.get("finishedAt")
            runs.append(PipelineRunInfo(
                external_id=str(plan),
                pipeline_name=pipeline,
                status=status,
                conclusion=(status_raw or "").lower() or None,
                branch=ex.get("branch") or "main",
                commit_sha=(ex.get("commitId") or ex.get("commit") or "")[:40],
                started_at=str(started) if started else "",
                finished_at=str(finished) if finished else None,
                duration_seconds=None,
                url=ex.get("url") or "",
                logs_preview=f"Execution {plan} — {status_raw or status}",
            ))
        return runs
