"""Live Azure DevOps pipeline provider."""

from __future__ import annotations

import base64

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import get_json


def _pat_header(pat: str) -> dict[str, str]:
    raw = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


class AzurePipelinesProvider(PipelineProvider):
    provider = "AZURE_PIPELINES"

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        org = secret.get("organization")
        pat = secret.get("pat")
        if not org or not pat:
            return []
        headers = _pat_header(pat)
        base = f"https://dev.azure.com/{org}"
        projects = get_json(f"{base}/_apis/projects?api-version=7.0", headers=headers)
        pipelines: list[PipelineInfo] = []
        for proj in (projects.get("value") or [])[:20]:
            if not isinstance(proj, dict):
                continue
            pid = proj.get("id")
            pname = proj.get("name") or ""
            pl_data = get_json(
                f"{base}/{pname}/_apis/pipelines?api-version=7.0",
                headers=headers,
            )
            for pl in (pl_data.get("value") or [])[:50]:
                if not isinstance(pl, dict):
                    continue
                pipelines.append(PipelineInfo(
                    external_id=f"{pname}:{pl.get('id')}",
                    name=pl.get("name") or str(pl.get("id")),
                    repository=pname,
                    provider=self.provider,
                ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        org = secret.get("organization")
        pat = secret.get("pat")
        if not org or not pat or ":" not in pipeline:
            return []
        project, pipe_id = pipeline.split(":", 1)
        headers = _pat_header(pat)
        base = f"https://dev.azure.com/{org}/{project}"
        data = get_json(
            f"{base}/_apis/pipelines/{pipe_id}/runs?api-version=7.0&$top={limit}",
            headers=headers,
        )
        runs: list[PipelineRunInfo] = []
        for run in (data.get("value") or [])[:limit]:
            if not isinstance(run, dict):
                continue
            result = (run.get("result") or run.get("state") or "").upper()
            status = "SUCCEEDED" if result == "SUCCEEDED" else "FAILED" if result in ("FAILED", "CANCELED") else "RUNNING"
            runs.append(PipelineRunInfo(
                external_id=str(run.get("id")),
                pipeline_name=pipeline,
                status=status,
                conclusion=run.get("result"),
                branch="main",
                commit_sha="",
                started_at=run.get("createdDate") or "",
                finished_at=run.get("finishedDate"),
                duration_seconds=None,
                url=run.get("url") or run.get("_links", {}).get("web", {}).get("href", ""),
                logs_preview=f"Run {run.get('id')} — {run.get('result') or run.get('state')}",
            ))
        return runs
