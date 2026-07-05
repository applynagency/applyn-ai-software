"""Source control provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SourceConnectionResult:
    account_id: str
    display_name: str
    health: str = "HEALTHY"
    permissions: list[str] = field(default_factory=list)


@dataclass
class RepositoryInfo:
    external_id: str
    name: str
    full_name: str
    default_branch: str
    visibility: str
    url: str
    language: str | None = None
    stars: int = 0
    forks: int = 0
    open_prs: int = 0
    health: str = "HEALTHY"


@dataclass
class BranchInfo:
    name: str
    commit_sha: str
    protected: bool = False


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    committed_at: str


@dataclass
class PullRequestInfo:
    number: int
    title: str
    state: str
    author: str
    source_branch: str
    target_branch: str
    url: str


class SourceProvider(ABC):
    provider: str

    @abstractmethod
    def test_connection(self, secret: dict) -> SourceConnectionResult:
        ...

    @abstractmethod
    def list_repositories(self, secret: dict) -> list[RepositoryInfo]:
        ...

    def list_branches(self, secret: dict, repo: str) -> list[BranchInfo]:
        return []

    def list_commits(self, secret: dict, repo: str, *, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        return []

    def list_pull_requests(self, secret: dict, repo: str, *, state: str = "open") -> list[PullRequestInfo]:
        return []

    def repository_stats(self, secret: dict, repo: str) -> dict:
        return {"contributors": 0, "languages": {}}
