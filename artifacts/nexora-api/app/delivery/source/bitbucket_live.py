"""Live Bitbucket source provider."""

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


class BitbucketSourceProvider(SourceProvider):
    provider = "BITBUCKET"

    def _auth(self, secret: dict) -> tuple[str, str] | None:
        if secret.get("username") and secret.get("app_password"):
            return secret["username"], secret["app_password"]
        return None

    def test_connection(self, secret: dict) -> SourceConnectionResult:
        auth = self._auth(secret)
        if not auth:
            return SourceConnectionResult("bb-missing", "Bitbucket", "UNREACHABLE")
        try:
            me = get_json("https://api.bitbucket.org/2.0/user", auth=auth)
            return SourceConnectionResult(
                me.get("account_id", "bitbucket"),
                me.get("username", "bitbucket"),
                "HEALTHY",
                ["repositories:read"],
            )
        except Exception:  # noqa: BLE001
            return SourceConnectionResult("bb-failed", "Bitbucket", "UNREACHABLE")

    def list_repositories(self, secret: dict) -> list[RepositoryInfo]:
        auth = self._auth(secret)
        if not auth:
            return []
        try:
            data = get_json("https://api.bitbucket.org/2.0/repositories?pagelen=50&role=member", auth=auth)
            return [
                RepositoryInfo(
                    str(r.get("uuid") or r.get("full_name")),
                    r.get("name") or "",
                    r.get("full_name") or "",
                    (r.get("mainbranch") or {}).get("name") or "main",
                    "private" if r.get("is_private") else "public",
                    (r.get("links") or {}).get("html", {}).get("href", ""),
                    (r.get("language") or ""),
                    0, 0, 0,
                )
                for r in (data.get("values") or []) if isinstance(r, dict)
            ]
        except Exception:  # noqa: BLE001
            return []

    def list_branches(self, secret: dict, repo: str) -> list[BranchInfo]:
        auth = self._auth(secret)
        if not auth or "/" not in repo:
            return []
        ws, slug = repo.split("/", 1)
        try:
            data = get_json(
                f"https://api.bitbucket.org/2.0/repositories/{ws}/{slug}/refs/branches?pagelen=20",
                auth=auth,
            )
            return [
                BranchInfo(b.get("name", ""), "", b.get("name") == "main")
                for b in (data.get("values") or []) if isinstance(b, dict)
            ]
        except Exception:  # noqa: BLE001
            return []

    def list_commits(self, secret: dict, repo: str, *, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        auth = self._auth(secret)
        if not auth or "/" not in repo:
            return []
        ws, slug = repo.split("/", 1)
        try:
            data = get_json(
                f"https://api.bitbucket.org/2.0/repositories/{ws}/{slug}/commits/{branch}?pagelen={limit}",
                auth=auth,
            )
            return [
                CommitInfo(
                    (c.get("hash") or "")[:12],
                    (c.get("message") or "")[:120],
                    (c.get("author") or {}).get("user", {}).get("display_name", ""),
                    c.get("date") or "",
                )
                for c in (data.get("values") or []) if isinstance(c, dict)
            ]
        except Exception:  # noqa: BLE001
            return []

    def list_pull_requests(self, secret: dict, repo: str, *, state: str = "open") -> list[PullRequestInfo]:
        auth = self._auth(secret)
        if not auth or "/" not in repo:
            return []
        ws, slug = repo.split("/", 1)
        try:
            data = get_json(
                f"https://api.bitbucket.org/2.0/repositories/{ws}/{slug}/pullrequests?state={state}&pagelen=20",
                auth=auth,
            )
            return [
                PullRequestInfo(
                    pr.get("id", 0),
                    pr.get("title") or "",
                    state,
                    (pr.get("author") or {}).get("display_name", ""),
                    (pr.get("source") or {}).get("branch", {}).get("name", ""),
                    (pr.get("destination") or {}).get("branch", {}).get("name", "main"),
                    (pr.get("links") or {}).get("html", {}).get("href", ""),
                )
                for pr in (data.get("values") or []) if isinstance(pr, dict)
            ]
        except Exception:  # noqa: BLE001
            return []
