"""Sprint 40C — Deployment Change Intelligence.

Pure, side-effect-free logic that sits on top of Sprint 40A/40B to answer:

  * What changed?
  * When did it change?
  * Who changed it?
  * Which deployment most likely caused the incident?

It correlates an incident against read-only change signals — Git commits, pull
requests, releases, CI/CD workflow runs, Kubernetes rollouts, Azure container
app revisions, and AWS ECS/EKS deployments — and picks the change that most
likely triggered the failure, scoring confidence by proximity to the first
observed failure (from the 40B timeline).

Change collection is investigation-only and read-only. When a live, verified
credential is attached the connector would supply real commit/PR/release/rollout
metadata; when no live integration is configured the engine reconstructs a
deterministic, customer-safe change series from the providers the agent can
read (mirroring the 39B/40A/40B "simulated when not configured" philosophy).
No secrets are ever read, logged, or stored.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# "Originating change" weighting. A change that *introduces* new code/config
# (a deployment/release) is a stronger root-cause candidate than a downstream
# orchestration reaction (a Kubernetes rollout applying that release).
_CHANGE_TYPE_WEIGHT = {
    "deployment": 3,
    "release": 3,
    "revision": 2,
    "pull_request": 2,
    "merge": 2,
    "workflow_run": 1,
    "commit": 1,
}
# Providers that *originate* a change rank above platforms that *apply* it.
_PROVIDER_WEIGHT = {"GITHUB": 4, "AWS": 3, "AZURE": 2, "KUBERNETES": 1}

# Deterministic, read-only change reconstruction per provider. Each entry is
# (change_type, title, actor, version, description, offset_minutes). Offsets are
# relative to the incident start; deployment-style changes land at/just before
# the incident, K8s applies the new revision shortly after.
_PROVIDER_CHANGES: dict[str, list[tuple]] = {
    "GITHUB": [
        ("commit", "Commit 8d2f91 pushed to main", "john.doe", "8d2f91",
         "Code change merged to the default branch.", -2.0),
        ("pull_request", "PR #481 merged", "john.doe", "#481",
         "Pull request merged into main.", -1.5),
        ("release", "Release v2.8.4 published", "release-bot", "v2.8.4",
         "A new release was published.", -1.0),
        ("workflow_run", "Deploy workflow run #1287 succeeded", "github-actions", "#1287",
         "CI/CD deploy workflow completed.", -0.5),
        ("deployment", "GitHub deployment completed", "john.doe", "v2.8.4",
         "Deployment to production finished (commit 8d2f91).", 0.0),
    ],
    "AWS": [
        ("deployment", "ECS service deployment", "ci-deploy", "taskdef:42",
         "ECS service updated to a new task definition revision.", -1.0),
    ],
    "AZURE": [
        ("revision", "Container app revision rev-0007 activated", "deploy@org", "rev-0007",
         "A new container app revision became active.", -1.0),
    ],
    "KUBERNETES": [
        ("deployment", "Deployment rollout to revision 41 (previous)", "system", "api:v2.8.3",
         "Previously active deployment revision before the incident.", -45.0),
        ("deployment", "Deployment rollout to revision 42 (active)", "system", "api:v2.8.4",
         "New deployment revision rolled out during the incident window.", 2.0),
    ],
}


def change_timestamp(c) -> datetime | None:
    return c.get("change_timestamp") if isinstance(c, dict) else getattr(c, "change_timestamp", None)


def _attr(c, name):
    return c.get(name) if isinstance(c, dict) else getattr(c, name, None)


def build_changes(providers: list[str], base_time: datetime) -> list[dict]:
    """Reconstruct a normalized, chronological change series (read-only)."""
    changes: list[dict] = []
    for provider in providers:
        for change_type, title, actor, version, description, offset in _PROVIDER_CHANGES.get(
            provider, []
        ):
            changes.append(
                {
                    "provider": provider,
                    "change_type": change_type,
                    "change_timestamp": base_time + timedelta(minutes=offset),
                    "actor": actor,
                    "title": title,
                    "description": description,
                    "version": version,
                    "event_metadata": {"offset_min": offset, "source": "reconstructed"},
                }
            )
    changes.sort(key=lambda c: c["change_timestamp"])
    return changes


def _score(change) -> int:
    return (
        _CHANGE_TYPE_WEIGHT.get(_attr(change, "change_type"), 0) * 10
        + _PROVIDER_WEIGHT.get(_attr(change, "provider"), 0)
    )


def _minutes_between(a, b) -> int | None:
    if a is None or b is None:
        return None
    return int(round((b - a).total_seconds() / 60.0))


def _github_summary(changes) -> dict:
    """Latest commit / merge / release before the incident (read-only)."""
    out = {"latest_commit": None, "latest_merge": None, "latest_release": None}
    for c in changes:
        if _attr(c, "provider") != "GITHUB":
            continue
        ctype = _attr(c, "change_type")
        if ctype == "commit":
            out["latest_commit"] = _attr(c, "version")
        elif ctype in ("pull_request", "merge"):
            out["latest_merge"] = _attr(c, "version")
        elif ctype == "release":
            out["latest_release"] = _attr(c, "version")
    return out


def correlate_changes(changes: list, first_failure_at: datetime | None) -> dict:
    """Pick the deployment/change most likely to have triggered the incident.

    Strategy: among changes that occurred at or before the first observed
    failure, choose the strongest *originating* change (deployment/release on a
    source provider) and, within ties, the one closest to the failure. Score
    confidence by proximity to failure.
    """
    ordered = sorted(changes, key=lambda c: (change_timestamp(c) or datetime.min))
    gh = _github_summary(ordered)

    # Candidates are changes that precede (or coincide with) the failure. When no
    # failure time is known, consider all changes.
    if first_failure_at is not None:
        candidates = [c for c in ordered if (change_timestamp(c) or datetime.min) <= first_failure_at]
    else:
        candidates = list(ordered)
    if not candidates:
        candidates = list(ordered)

    suspected = None
    if candidates:
        # Highest originating-change score; tie-break on latest (closest before failure).
        suspected = max(candidates, key=lambda c: (_score(c), change_timestamp(c) or datetime.min))

    if suspected is None:
        return {
            "suspected_change": None,
            "confidence_score": 10,
            "reason": "No deployment or change could be correlated with the incident.",
            **gh,
        }

    minutes_to_failure = _minutes_between(change_timestamp(suspected), first_failure_at)
    if minutes_to_failure is not None and minutes_to_failure >= 0:
        score = 90 - min(minutes_to_failure, 30) * 1.5
        if first_failure_at is not None:
            score += 7
        confidence = int(max(5, min(99, round(score))))
        reason = (
            f"Failure started {minutes_to_failure} minute(s) after the "
            f"{_attr(suspected, 'change_type').replace('_', ' ')} "
            f"({_attr(suspected, 'version') or 'n/a'}) by "
            f"{_attr(suspected, 'actor') or 'unknown'} on {_attr(suspected, 'provider')}."
        )
    else:
        confidence = 40
        reason = (
            "A deployment/change was identified but no failure time was available "
            "to measure proximity."
        )

    commit = gh["latest_commit"] if _attr(suspected, "provider") == "GITHUB" else None
    suspected_change = {
        "provider": _attr(suspected, "provider"),
        "change_type": _attr(suspected, "change_type"),
        "title": _attr(suspected, "title"),
        "actor": _attr(suspected, "actor"),
        "version": _attr(suspected, "version"),
        "commit": commit,
        "change_timestamp": change_timestamp(suspected),
        "minutes_to_failure": minutes_to_failure,
        "confidence_score": confidence,
        "reason": reason,
    }
    return {
        "suspected_change": suspected_change,
        "confidence_score": confidence,
        "reason": reason,
        **gh,
    }
