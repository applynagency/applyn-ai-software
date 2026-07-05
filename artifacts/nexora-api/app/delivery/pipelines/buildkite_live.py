"""Live Buildkite pipeline provider."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import bearer_header, get_json


def _buildkite_status(state: str | None) -> str:
    mapping = {
        "passed": "SUCCEEDED",
        "failed": "FAILED",
        "running": "RUNNING",
        "canceled": "CANCELLED",
        "cancelled": "CANCELLED",
        "blocked": "RUNNING",
        "scheduled": "QUEUED",
    }
    return mapping.get((state or "").lower(), "UNKNOWN")


class BuildkiteProvider(PipelineProvider):
    provider = "BUILDKITE"

    def _headers(self, secret: dict) -> dict[str, str]:
        return {**bearer_header(secret.get("api_token", "")), "Accept": "application/json"}

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        org = secret.get("organization")
        token = secret.get("api_token")
        if not org or not token:
            return []
        headers = self._headers(secret)
        data = get_json(
            f"https://api.buildkite.com/v2/organizations/{org}/pipelines",
            headers=headers,
        )
        pipelines: list[PipelineInfo] = []
        for pipe in (data if isinstance(data, list) else data.get("items") or [])[:50]:
            if not isinstance(pipe, dict):
                continue
            slug = pipe.get("slug") or pipe.get("name") or ""
            if not slug:
                continue
            pipelines.append(PipelineInfo(
                external_id=slug,
                name=pipe.get("name") or slug,
                repository=repository or org,
                provider=self.provider,
                status="ACTIVE",
            ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        org = secret.get("organization")
        token = secret.get("api_token")
        if not org or not token:
            return []
        headers = self._headers(secret)
        slug = pipeline.split("/")[-1] if "/" in pipeline else pipeline
        url = f"https://api.buildkite.com/v2/organizations/{org}/pipelines/{slug}/builds"
        data = get_json(url, headers=headers)
        runs: list[PipelineRunInfo] = []
        for build in (data if isinstance(data, list) else data.get("items") or [])[:limit]:
            if not isinstance(build, dict):
                continue
            state = build.get("state") or ""
            status = _buildkite_status(state)
            commit = (build.get("commit") or "")[:40]
            runs.append(PipelineRunInfo(
                external_id=str(build.get("number") or build.get("id")),
                pipeline_name=slug,
                status=status,
                conclusion=state,
                branch=build.get("branch") or "main",
                commit_sha=commit,
                started_at=build.get("created_at") or "",
                finished_at=build.get("finished_at"),
                duration_seconds=None,
                url=build.get("web_url") or "",
                logs_preview=f"Build #{build.get('number')} — {state}",
            ))
        return runs
