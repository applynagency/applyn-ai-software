"""Live GitLab CI pipeline provider."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import get_json


class GitLabCIProvider(PipelineProvider):
    provider = "GITLAB_CI"

    def _base(self, secret: dict) -> str:
        return (secret.get("base_url") or "https://gitlab.com").rstrip("/")

    def _headers(self, secret: dict) -> dict[str, str]:
        return {"PRIVATE-TOKEN": secret.get("token", "")}

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        token = secret.get("token")
        if not token:
            return []
        base = self._base(secret)
        headers = self._headers(secret)
        pipelines: list[PipelineInfo] = []
        if repository:
            pid = repository.replace("/", "%2F")
            data = get_json(f"{base}/api/v4/projects/{pid}", headers=headers)
            pipelines.append(PipelineInfo(
                external_id=str(data.get("id") or repository),
                name=data.get("name") or repository,
                repository=data.get("path_with_namespace") or repository,
                provider=self.provider,
            ))
            return pipelines
        data = get_json(f"{base}/api/v4/projects?membership=true&per_page=50", headers=headers)
        for proj in (data if isinstance(data, list) else []):
            if not isinstance(proj, dict):
                continue
            pipelines.append(PipelineInfo(
                external_id=str(proj.get("id")),
                name=proj.get("name") or str(proj.get("id")),
                repository=proj.get("path_with_namespace") or "",
                provider=self.provider,
            ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        token = secret.get("token")
        if not token:
            return []
        base = self._base(secret)
        headers = self._headers(secret)
        pid = pipeline if pipeline.isdigit() else (repository or pipeline).replace("/", "%2F")
        data = get_json(
            f"{base}/api/v4/projects/{pid}/pipelines?per_page={limit}",
            headers=headers,
        )
        runs: list[PipelineRunInfo] = []
        for pl in (data if isinstance(data, list) else [])[:limit]:
            if not isinstance(pl, dict):
                continue
            st = (pl.get("status") or "").upper()
            status = "SUCCEEDED" if st == "SUCCESS" else "FAILED" if st in ("FAILED", "CANCELED") else "RUNNING"
            runs.append(PipelineRunInfo(
                external_id=str(pl.get("id")),
                pipeline_name=pipeline,
                status=status,
                conclusion=pl.get("status"),
                branch=pl.get("ref") or "main",
                commit_sha=(pl.get("sha") or "")[:40],
                started_at=pl.get("created_at") or "",
                finished_at=pl.get("updated_at"),
                duration_seconds=None,
                url=pl.get("web_url") or "",
                logs_preview=f"Pipeline #{pl.get('id')} — {pl.get('status')}",
            ))
        return runs
