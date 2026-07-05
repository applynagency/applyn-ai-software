"""Live CircleCI pipeline provider."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import get_json


class CircleCIProvider(PipelineProvider):
    provider = "CIRCLECI"

    def _headers(self, secret: dict) -> dict[str, str]:
        return {"Circle-Token": secret.get("api_token", "")}

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        token = secret.get("api_token")
        if not token:
            return []
        headers = self._headers(secret)
        me = get_json("https://circleci.com/api/v2/me", headers=headers)
        login = me.get("login") or me.get("name") or "circleci"
        collabs = get_json("https://circleci.com/api/v2/me/collaborations", headers=headers)
        pipelines: list[PipelineInfo] = []
        items = collabs if isinstance(collabs, list) else collabs.get("items", [])
        for collab in (items or [])[:30]:
            if not isinstance(collab, dict):
                continue
            slug = collab.get("vcs_url") or collab.get("slug") or collab.get("name") or ""
            name = slug.split("/")[-1] if slug else "project"
            pipelines.append(PipelineInfo(
                external_id=slug or name,
                name=name,
                repository=slug or login,
                provider=self.provider,
            ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        token = secret.get("api_token")
        if not token:
            return []
        headers = self._headers(secret)
        slug = pipeline.replace("https://github.com/", "gh/").replace("https://gitlab.com/", "gl/")
        if not slug.startswith(("gh/", "bb/")):
            slug = f"gh/{slug}" if "/" in slug else pipeline
        url = f"https://circleci.com/api/v2/project/{slug}/pipeline"
        data = get_json(url, headers=headers)
        runs: list[PipelineRunInfo] = []
        for pl in (data.get("items") or [])[:limit]:
            if not isinstance(pl, dict):
                continue
            state = (pl.get("state") or "").upper()
            status = "SUCCEEDED" if state == "SUCCESS" else "FAILED" if state in ("FAILED", "ERROR") else "RUNNING"
            runs.append(PipelineRunInfo(
                external_id=str(pl.get("id")),
                pipeline_name=pipeline,
                status=status,
                conclusion=pl.get("state"),
                branch=(pl.get("vcs") or {}).get("branch") or "main",
                commit_sha=((pl.get("vcs") or {}).get("revision") or "")[:40],
                started_at=pl.get("created_at") or "",
                finished_at=pl.get("updated_at"),
                duration_seconds=None,
                url=pl.get("web_url") or "",
                logs_preview=f"Pipeline {pl.get('id')} — {pl.get('state')}",
            ))
        return runs
