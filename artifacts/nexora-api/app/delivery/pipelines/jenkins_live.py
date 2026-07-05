"""Live Jenkins pipeline provider — reads jobs and builds via Jenkins REST API."""

from __future__ import annotations

from datetime import UTC, datetime

from app.delivery.pipelines.base import PipelineInfo, PipelineProvider, PipelineRunInfo
from app.delivery.pipelines.ci_http import get_json, get_text


def _job_base_url(endpoint: str, job_name: str) -> str:
    endpoint = endpoint.rstrip("/")
    return "/".join([endpoint] + [f"job/{part}" for part in job_name.split("/")])


def _flatten_jobs(jobs: list, prefix: str = "") -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        name = job.get("name") or ""
        full = job.get("fullName") or (f"{prefix}/{name}" if prefix else name)
        cls = job.get("_class") or ""
        if "Folder" in cls and job.get("jobs"):
            out.extend(_flatten_jobs(job.get("jobs"), full))
        elif name:
            out.append((full, job))
    return out


def _jenkins_status(result: str | None, building: bool | None = None) -> str:
    if building:
        return "RUNNING"
    mapping = {
        "SUCCESS": "SUCCEEDED",
        "FAILURE": "FAILED",
        "UNSTABLE": "FAILED",
        "ABORTED": "CANCELLED",
        "NOT_BUILT": "FAILED",
    }
    return mapping.get((result or "").upper(), "UNKNOWN")


class JenkinsProvider(PipelineProvider):
    provider = "JENKINS"

    def list_pipelines(self, secret: dict, *, repository: str | None = None) -> list[PipelineInfo]:
        endpoint = (secret.get("endpoint") or "").rstrip("/")
        if not endpoint or not secret.get("username") or not secret.get("api_token"):
            return []
        url = f"{endpoint}/api/json?tree=jobs[name,fullName,url,color,_class,jobs[name,fullName,url,color,_class]]"
        data = get_json(url, auth=(secret["username"], secret["api_token"]))
        repo_label = repository or endpoint
        pipelines: list[PipelineInfo] = []
        for full_name, job in _flatten_jobs(data.get("jobs", [])):
            color = (job.get("color") or "").replace("_anime", "")
            status = "ACTIVE"
            if color in ("red", "red_anime", "notbuilt"):
                status = "DEGRADED"
            pipelines.append(PipelineInfo(
                external_id=full_name,
                name=full_name.split("/")[-1],
                repository=repo_label,
                provider=self.provider,
                status=status,
            ))
        return pipelines

    def list_runs(
        self, secret: dict, pipeline: str, *, repository: str | None = None, limit: int = 20,
    ) -> list[PipelineRunInfo]:
        endpoint = (secret.get("endpoint") or "").rstrip("/")
        if not endpoint:
            return []
        base = _job_base_url(endpoint, pipeline)
        tree = "builds[number,result,url,timestamp,duration,building,changeSet[items[commitId]]]"
        data = get_json(f"{base}/api/json?tree={tree}", auth=(secret["username"], secret["api_token"]))
        runs: list[PipelineRunInfo] = []
        for build in (data.get("builds") or [])[:limit]:
            if not isinstance(build, dict):
                continue
            ts_ms = build.get("timestamp")
            started = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat() if ts_ms else ""
            duration = build.get("duration")
            finished = None
            if ts_ms and duration:
                finished = datetime.fromtimestamp((ts_ms + duration) / 1000, tz=UTC).isoformat()
            commits = build.get("changeSet", {}).get("items") or []
            sha = commits[0].get("commitId", "")[:40] if commits else ""
            result = build.get("result")
            status = _jenkins_status(result, build.get("building"))
            runs.append(PipelineRunInfo(
                external_id=str(build.get("number")),
                pipeline_name=pipeline,
                status=status,
                conclusion=(result or "").lower() or None,
                branch="main",
                commit_sha=sha,
                started_at=started,
                finished_at=finished,
                duration_seconds=int(duration / 1000) if duration else None,
                url=build.get("url") or base,
                logs_preview=f"Build #{build.get('number')} — {result or status}",
            ))
        return runs


def fetch_build_console_excerpt(
    secret: dict,
    job: str,
    build_number: str | int,
    *,
    max_chars: int = 4000,
) -> dict:
    """Fetch tail of Jenkins console output for failed-build triage."""
    endpoint = (secret.get("endpoint") or "").rstrip("/")
    username = secret.get("username")
    api_token = secret.get("api_token")
    if not endpoint or not username or not api_token:
        return {"available": False, "reason": "Jenkins credentials incomplete"}
    try:
        num = int(build_number)
    except (TypeError, ValueError):
        return {"available": False, "reason": "Invalid build number"}
    base = _job_base_url(endpoint, job)
    url = f"{base}/{num}/consoleText"
    try:
        text = get_text(url, auth=(username, api_token))
    except RuntimeError as exc:
        return {"available": False, "reason": str(exc)[:200]}
    excerpt = text[-max_chars:] if len(text) > max_chars else text
    build_url = f"{base}/{num}/"
    return {
        "available": True,
        "job": job,
        "build_number": num,
        "url": build_url,
        "console_excerpt": excerpt,
        "truncated": len(text) > max_chars,
        "total_chars": len(text),
    }
