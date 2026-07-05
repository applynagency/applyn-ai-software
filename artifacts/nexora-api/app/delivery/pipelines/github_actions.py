"""GitHub Actions pipeline provider."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo


def _headers(secret: dict) -> dict:
    token = secret.get("token") or secret.get("access_token") or secret.get("github_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _get(url: str, secret: dict) -> dict | list:
    req = urllib.request.Request(url, headers=_headers(secret))
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def _sim_pipelines(repo: str) -> list[PipelineInfo]:
    return [
        PipelineInfo("ci", "CI", repo, "GITHUB_ACTIONS"),
        PipelineInfo("deploy", "Deploy", repo, "GITHUB_ACTIONS"),
        PipelineInfo("security", "Security Scan", repo, "GITHUB_ACTIONS"),
    ]


def _sim_runs(pipeline: str) -> list[PipelineRunInfo]:
    return [
        PipelineRunInfo(
            "run-1001", pipeline, "SUCCEEDED", "success", "main", "abc1234",
            "2026-06-30T10:00:00Z", "2026-06-30T10:08:00Z", 480,
            "https://github.com/actions/runs/1001",
            "npm test\nnpm build\npush image",
            [{"name": "image", "digest": "sha256:abc"}],
        ),
        PipelineRunInfo(
            "run-1000", pipeline, "FAILED", "failure", "feature/x", "def5678",
            "2026-06-29T14:00:00Z", "2026-06-29T14:03:00Z", 180,
            "https://github.com/actions/runs/1000",
            "npm test\nFAIL integration suite",
            [],
        ),
    ]


class GitHubActionsProvider(PipelineProvider):
    provider = "GITHUB_ACTIONS"

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        if not _headers(secret):
            return []
        repos: list[str] = []
        if repository:
            repos = [repository]
        elif secret.get("repository"):
            repos = [secret["repository"]]
        else:
            try:
                data = _get("https://api.github.com/user/repos?per_page=30&sort=updated", secret)
                repos = [r["full_name"] for r in data if isinstance(r, dict) and r.get("full_name")]
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
                return []
        pipelines: list[PipelineInfo] = []
        for repo in repos[:15]:
            try:
                data = _get(f"https://api.github.com/repos/{repo}/actions/workflows", secret)
                workflows = data.get("workflows", []) if isinstance(data, dict) else []
                for w in workflows:
                    pipelines.append(PipelineInfo(
                        external_id=f"{repo}:{w['id']}",
                        name=w["name"],
                        repository=repo,
                        provider=self.provider,
                        status=w.get("state", "ACTIVE"),
                    ))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
                continue
        return pipelines

    def list_runs(self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20) -> list[PipelineRunInfo]:
        if not _headers(secret):
            return []
        if ":" in pipeline:
            repo, pipe_id = pipeline.rsplit(":", 1)
        else:
            repo = repository or secret.get("repository")
            pipe_id = pipeline
        if not repo:
            return []
        try:
            url = f"https://api.github.com/repos/{repo}/actions/workflows/{pipe_id}/runs?per_page={limit}"
            data = _get(url, secret)
            runs = data.get("workflow_runs", []) if isinstance(data, dict) else []
            out: list[PipelineRunInfo] = []
            for r in runs:
                started = r.get("run_started_at") or r.get("created_at", "")
                updated = r.get("updated_at")
                dur = None
                if started and updated:
                    try:
                        from datetime import datetime

                        s = datetime.fromisoformat(started.replace("Z", "+00:00"))
                        e = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        dur = int((e - s).total_seconds())
                    except ValueError:
                        dur = None
                out.append(PipelineRunInfo(
                    str(r["id"]), r.get("name", pipeline),
                    r.get("status", "UNKNOWN").upper(),
                    r.get("conclusion"),
                    r.get("head_branch", "main"),
                    (r.get("head_sha") or "")[:7],
                    started, updated, dur,
                    r.get("html_url", ""),
                ))
            return out
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return []
