"""Live Azure DevOps source provider."""

from __future__ import annotations

import base64

from app.delivery.pipelines.ci_http import get_json
from app.delivery.source.base import (
    BranchInfo,
    RepositoryInfo,
    SourceConnectionResult,
    SourceProvider,
)


def _pat_header(pat: str) -> dict[str, str]:
    raw = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


class AzureDevOpsSourceProvider(SourceProvider):
    provider = "AZURE_DEVOPS"

    def test_connection(self, secret: dict) -> SourceConnectionResult:
        org = secret.get("organization")
        pat = secret.get("pat")
        if not org or not pat:
            return SourceConnectionResult("ado-missing", "Azure DevOps", "UNREACHABLE")
        try:
            data = get_json(
                f"https://dev.azure.com/{org}/_apis/projects?api-version=7.0&$top=1",
                headers=_pat_header(pat),
            )
            return SourceConnectionResult(
                org, org, "HEALTHY",
                ["projects:read", "repos:read"],
            )
        except Exception:  # noqa: BLE001
            return SourceConnectionResult("ado-failed", "Azure DevOps", "UNREACHABLE")

    def list_repositories(self, secret: dict) -> list[RepositoryInfo]:
        org = secret.get("organization")
        pat = secret.get("pat")
        if not org or not pat:
            return []
        headers = _pat_header(pat)
        repos: list[RepositoryInfo] = []
        try:
            projects = get_json(f"https://dev.azure.com/{org}/_apis/projects?api-version=7.0", headers=headers)
            for proj in (projects.get("value") or [])[:20]:
                if not isinstance(proj, dict):
                    continue
                pname = proj.get("name") or ""
                rdata = get_json(
                    f"https://dev.azure.com/{org}/{pname}/_apis/git/repositories?api-version=7.0",
                    headers=headers,
                )
                for r in (rdata.get("value") or [])[:50]:
                    if not isinstance(r, dict):
                        continue
                    repos.append(RepositoryInfo(
                        r.get("id", ""),
                        r.get("name") or "",
                        f"{pname}/{r.get('name', '')}",
                        r.get("defaultBranch", "refs/heads/main").replace("refs/heads/", ""),
                        "private",
                        r.get("webUrl") or "",
                        None, 0, 0, 0,
                    ))
        except Exception:  # noqa: BLE001
            return []
        return repos

    def list_branches(self, secret: dict, repo: str) -> list[BranchInfo]:
        return []
