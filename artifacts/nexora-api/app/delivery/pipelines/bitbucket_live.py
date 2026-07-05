"""Live Bitbucket Pipelines provider."""

from __future__ import annotations

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import get_json


def _auth(secret: dict) -> tuple[str, str]:
    return secret["username"], secret["app_password"]


def _repos(secret: dict) -> list[dict]:
    auth = _auth(secret)
    data = get_json("https://api.bitbucket.org/2.0/repositories?pagelen=50&role=member", auth=auth)
    return [r for r in (data.get("values") or []) if isinstance(r, dict)]


class BitbucketPipelinesProvider(PipelineProvider):
    provider = "BITBUCKET_PIPELINES"

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        if not secret.get("username") or not secret.get("app_password"):
            return []
        auth = _auth(secret)
        pipelines: list[PipelineInfo] = []
        if repository:
            repos = [{"full_name": repository}]
        else:
            repos = _repos(secret)
        for repo in repos[:50]:
            full = repo.get("full_name") or ""
            if not full or "/" not in full:
                continue
            name = full.split("/")[-1]
            pipelines.append(PipelineInfo(
                external_id=full,
                name=name,
                repository=full,
                provider=self.provider,
            ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        if not secret.get("username") or not secret.get("app_password"):
            return []
        repo = pipeline or repository or ""
        if "/" not in repo:
            return []
        workspace, slug = repo.split("/", 1)
        auth = _auth(secret)
        url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{slug}/pipelines/?pagelen={limit}"
        data = get_json(url, auth=auth)
        runs: list[PipelineRunInfo] = []
        for pl in (data.get("values") or [])[:limit]:
            if not isinstance(pl, dict):
                continue
            state = pl.get("state") or {}
            result = (state.get("result") or {}).get("name") or state.get("name") or ""
            status = "SUCCEEDED" if result == "SUCCESSFUL" else "FAILED" if result == "FAILED" else "RUNNING"
            runs.append(PipelineRunInfo(
                external_id=str(pl.get("uuid") or pl.get("build_number")),
                pipeline_name=pipeline,
                status=status,
                conclusion=result.lower() or None,
                branch=(pl.get("target") or {}).get("ref_name") or "main",
                commit_sha=((pl.get("target") or {}).get("commit") or {}).get("hash", "")[:40],
                started_at=pl.get("created_on") or "",
                finished_at=pl.get("completed_on"),
                duration_seconds=None,
                url=(pl.get("links") or {}).get("html", {}).get("href", ""),
                logs_preview=f"Pipeline #{pl.get('build_number')} — {result or status}",
            ))
        return runs
