"""Additional source providers — simulated catalog when credentials absent."""

from __future__ import annotations

from app.delivery.source.base import (
    BranchInfo,
    CommitInfo,
    PullRequestInfo,
    RepositoryInfo,
    SourceConnectionResult,
    SourceProvider,
)
from app.delivery.source.github import _simulated_repos


class _SimulatedSourceProvider(SourceProvider):
    def __init__(self, provider: str, account: str) -> None:
        self.provider = provider
        self._account = account

    def test_connection(self, secret: dict) -> SourceConnectionResult:
        ok = bool(secret.get("token") or secret.get("access_token") or secret.get("password"))
        return SourceConnectionResult(
            f"sim-{self.provider.lower()}",
            f"{self.provider} ({'connected' if ok else 'simulated'})",
            "HEALTHY" if ok else "DEGRADED",
            ["repo:read"],
        )

    def list_repositories(self, secret: dict) -> list[RepositoryInfo]:
        repos = _simulated_repos()
        return [
            RepositoryInfo(
                f"{self.provider}-{r.external_id}", r.name,
                f"{self._account}/{r.name}", r.default_branch, r.visibility,
                r.url.replace("github.com", f"{self.provider.lower()}.example"),
                r.language, r.stars, r.forks, r.open_prs,
            )
            for r in repos
        ]

    def list_branches(self, secret: dict, repo: str) -> list[BranchInfo]:
        return [BranchInfo("main", "a1b2c3d", True), BranchInfo("release/1.2", "e4f5g6h", True)]

    def list_commits(self, secret: dict, repo: str, *, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        return [CommitInfo("a1b2c3d", f"chore: sync {repo}", "ci-bot", "2026-06-29T08:00:00Z")]

    def list_pull_requests(self, secret: dict, repo: str, *, state: str = "open") -> list[PullRequestInfo]:
        return [PullRequestInfo(1, f"Update {repo}", state, "bot", "feature/update", "main", "#")]


class GitLabSourceProvider(_SimulatedSourceProvider):
    def __init__(self) -> None:
        super().__init__("GITLAB", "nexora-group")


class AzureDevOpsSourceProvider(_SimulatedSourceProvider):
    def __init__(self) -> None:
        super().__init__("AZURE_DEVOPS", "nexora-org")


class BitbucketSourceProvider(_SimulatedSourceProvider):
    def __init__(self) -> None:
        super().__init__("BITBUCKET", "nexora")


class GiteaSourceProvider(_SimulatedSourceProvider):
    def __init__(self) -> None:
        super().__init__("GITEA", "nexora")
