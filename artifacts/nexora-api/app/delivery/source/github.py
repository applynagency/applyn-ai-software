"""GitHub source provider — uses GitHub REST API when token present."""

from __future__ import annotations

import urllib.error
import urllib.request
import json

from app.delivery.source.base import (
    BranchInfo,
    CommitInfo,
    PullRequestInfo,
    RepositoryInfo,
    SourceConnectionResult,
    SourceProvider,
)


def _headers(secret: dict) -> dict:
    token = secret.get("token") or secret.get("access_token") or secret.get("github_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _get(url: str, secret: dict) -> list | dict:
    req = urllib.request.Request(url, headers=_headers(secret))
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def _simulated_repos() -> list[RepositoryInfo]:
    return [
        RepositoryInfo("1", "checkout-api", "nexora/checkout-api", "main", "private",
                       "https://github.com/nexora/checkout-api", "Python", 12, 3, 2),
        RepositoryInfo("2", "payment-service", "nexora/payment-service", "main", "private",
                       "https://github.com/nexora/payment-service", "Go", 8, 1, 1),
        RepositoryInfo("3", "web-frontend", "nexora/web-frontend", "main", "public",
                       "https://github.com/nexora/web-frontend", "TypeScript", 24, 5, 4),
    ]


class GitHubSourceProvider(SourceProvider):
    provider = "GITHUB"

    def test_connection(self, secret: dict) -> SourceConnectionResult:
        if not _headers(secret):
            return SourceConnectionResult("sim-github", "GitHub (simulated)", "DEGRADED",
                                        ["repo:read", "workflow:read"])
        try:
            user = _get("https://api.github.com/user", secret)
            return SourceConnectionResult(
                str(user.get("id", "github")),
                user.get("login", "github"),
                "HEALTHY",
                ["repo:read", "workflow:read", "checks:read"],
            )
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return SourceConnectionResult("github-unreachable", "GitHub", "UNREACHABLE")

    def list_repositories(self, secret: dict) -> list[RepositoryInfo]:
        if not _headers(secret):
            return _simulated_repos()
        try:
            data = _get("https://api.github.com/user/repos?per_page=50&sort=updated", secret)
            return [
                RepositoryInfo(
                    str(r["id"]), r["name"], r["full_name"],
                    r.get("default_branch", "main"),
                    r.get("visibility", "private"),
                    r.get("html_url", ""),
                    r.get("language"),
                    r.get("stargazers_count", 0),
                    r.get("forks_count", 0),
                    0,
                )
                for r in data
            ]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return _simulated_repos()

    def list_branches(self, secret: dict, repo: str) -> list[BranchInfo]:
        if not _headers(secret):
            return [BranchInfo("main", "abc123", True), BranchInfo("develop", "def456", False)]
        try:
            data = _get(f"https://api.github.com/repos/{repo}/branches?per_page=30", secret)
            return [
                BranchInfo(b["name"], b["commit"]["sha"][:7],
                           b.get("protected", False))
                for b in data
            ]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return [BranchInfo("main", "abc123", True)]

    def list_commits(self, secret: dict, repo: str, *, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        if not _headers(secret):
            return [
                CommitInfo("abc123", "fix: checkout timeout", "dev@nexora.com", "2026-06-28T10:00:00Z"),
                CommitInfo("def456", "feat: payment retry", "dev@nexora.com", "2026-06-27T15:30:00Z"),
            ]
        try:
            data = _get(
                f"https://api.github.com/repos/{repo}/commits?sha={branch}&per_page={limit}",
                secret,
            )
            return [
                CommitInfo(
                    c["sha"][:7],
                    (c["commit"]["message"] or "").split("\n")[0],
                    c["commit"]["author"]["name"] if c.get("commit") else "unknown",
                    c["commit"]["author"]["date"] if c.get("commit") else "",
                )
                for c in data
            ]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return []

    def list_pull_requests(self, secret: dict, repo: str, *, state: str = "open") -> list[PullRequestInfo]:
        if not _headers(secret):
            return [
                PullRequestInfo(42, "Add canary deploy", "open", "alice", "feature/canary", "main",
                                f"https://github.com/{repo}/pull/42"),
            ]
        try:
            data = _get(
                f"https://api.github.com/repos/{repo}/pulls?state={state}&per_page=20",
                secret,
            )
            return [
                PullRequestInfo(
                    pr["number"], pr["title"], pr["state"],
                    pr["user"]["login"] if pr.get("user") else "unknown",
                    pr["head"]["ref"], pr["base"]["ref"], pr.get("html_url", ""),
                )
                for pr in data
            ]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return []

    def repository_stats(self, secret: dict, repo: str) -> dict:
        if not _headers(secret):
            return {"contributors": 8, "languages": {"Python": 62, "YAML": 18, "Dockerfile": 5}}
        try:
            langs = _get(f"https://api.github.com/repos/{repo}/languages", secret)
            contribs = _get(f"https://api.github.com/repos/{repo}/contributors?per_page=1", secret)
            return {"contributors": len(contribs) if isinstance(contribs, list) else 0, "languages": langs}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            return {"contributors": 0, "languages": {}}
