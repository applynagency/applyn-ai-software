"""Live GitLab source provider."""

from __future__ import annotations

from app.delivery.pipelines.ci_http import get_json
from app.delivery.source.base import (
    BranchInfo,
    CommitInfo,
    PullRequestInfo,
    RepositoryInfo,
    SourceConnectionResult,
    SourceProvider,
)


class GitLabSourceProvider(SourceProvider):
    provider = "GITLAB"

    def _base(self, secret: dict) -> str:
        return (secret.get("base_url") or "https://gitlab.com").rstrip("/")

    def _headers(self, secret: dict) -> dict[str, str]:
        return {"PRIVATE-TOKEN": secret.get("token", "")}

    def test_connection(self, secret: dict) -> SourceConnectionResult:
        token = secret.get("token")
        if not token:
            return SourceConnectionResult("gl-missing", "GitLab", "UNREACHABLE")
        try:
            user = get_json(f"{self._base(secret)}/api/v4/user", headers=self._headers(secret))
            return SourceConnectionResult(
                str(user.get("id", "gitlab")),
                user.get("username", "gitlab"),
                "HEALTHY",
                ["projects:read", "pipelines:read"],
            )
        except Exception:  # noqa: BLE001
            return SourceConnectionResult("gl-failed", "GitLab", "UNREACHABLE")

    def list_repositories(self, secret: dict) -> list[RepositoryInfo]:
        token = secret.get("token")
        if not token:
            return []
        try:
            data = get_json(
                f"{self._base(secret)}/api/v4/projects?membership=true&per_page=50",
                headers=self._headers(secret),
            )
            return [
                RepositoryInfo(
                    str(p.get("id")),
                    p.get("name") or "",
                    p.get("path_with_namespace") or "",
                    p.get("default_branch") or "main",
                    p.get("visibility") or "private",
                    p.get("web_url") or "",
                    None, 0, 0, 0,
                )
                for p in (data if isinstance(data, list) else [])
                if isinstance(p, dict)
            ]
        except Exception:  # noqa: BLE001
            return []

    def list_branches(self, secret: dict, repo: str) -> list[BranchInfo]:
        token = secret.get("token")
        if not token:
            return []
        pid = repo.replace("/", "%2F") if not repo.isdigit() else repo
        try:
            data = get_json(
                f"{self._base(secret)}/api/v4/projects/{pid}/repository/branches?per_page=20",
                headers=self._headers(secret),
            )
            return [
                BranchInfo(b.get("name", ""), b.get("commit", {}).get("id", "")[:12],
                           b.get("name") == "main")
                for b in (data if isinstance(data, list) else []) if isinstance(b, dict)
            ]
        except Exception:  # noqa: BLE001
            return []

    def list_commits(self, secret: dict, repo: str, *, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        return []

    def list_pull_requests(self, secret: dict, repo: str, *, state: str = "open") -> list[PullRequestInfo]:
        return []
