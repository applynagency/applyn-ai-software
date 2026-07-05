"""Live Terraform Cloud plan runs via the TFC API v2."""

from __future__ import annotations

from app.delivery.pipelines.ci_http import bearer_header, get_json, post_json
from app.platform_engineering.iac.base import IaCPlanResult, IaCRunResult


def _headers(secret: dict) -> dict:
    return bearer_header(secret["token"])


def list_workspaces(secret: dict, *, page_size: int = 20) -> list[dict]:
    org = secret.get("organization")
    token = secret.get("token")
    if not org or not token:
        return []
    data = get_json(
        f"https://app.terraform.io/api/v2/organizations/{org}/workspaces?page[size]={page_size}",
        headers=_headers(secret),
    )
    return [
        {
            "id": (row.get("id") or ""),
            "name": ((row.get("attributes") or {}).get("name") or ""),
        }
        for row in (data.get("data") or [])
        if isinstance(row, dict)
    ]


def _resolve_workspace_id(secret: dict, variables: dict) -> str | None:
    workspace_id = variables.get("terraform_workspace_id") or variables.get("workspace_id")
    if workspace_id:
        return str(workspace_id)
    workspace_name = variables.get("terraform_workspace") or variables.get("workspace_name")
    if workspace_name:
        for ws in list_workspaces(secret):
            if ws.get("name") == workspace_name:
                return ws.get("id")
    workspaces = list_workspaces(secret, page_size=1)
    return workspaces[0]["id"] if workspaces else None


def _run_status(secret: dict, run_id: str) -> dict:
    data = get_json(
        f"https://app.terraform.io/api/v2/runs/{run_id}",
        headers=_headers(secret),
    )
    attrs = (data.get("data") or {}).get("attributes") or {}
    return {
        "run_id": run_id,
        "status": attrs.get("status") or "unknown",
        "message": attrs.get("message") or "",
        "plan_only": bool(attrs.get("plan-only")),
    }


def create_plan_run(secret: dict, *, workspace_id: str | None = None, variables: dict | None = None) -> IaCRunResult:
    variables = variables or {}
    ws_id = workspace_id or _resolve_workspace_id(secret, variables)
    if not ws_id:
        return IaCRunResult(success=False, logs="", error="No Terraform Cloud workspace configured")
    body = {
        "data": {
            "attributes": {
                "message": "Nexora plan-only run",
                "is-destroy": False,
                "plan-only": True,
            },
            "relationships": {
                "workspace": {"data": {"type": "workspaces", "id": ws_id}},
            },
        },
    }
    try:
        created = post_json("https://app.terraform.io/api/v2/runs", body, headers=_headers(secret))
    except RuntimeError as exc:
        return IaCRunResult(success=False, logs="", error=str(exc)[:300])
    run_id = (created.get("data") or {}).get("id") or ""
    status = _run_status(secret, run_id) if run_id else {}
    plan = IaCPlanResult(
        add=0,
        change=0,
        destroy=0,
        output_preview=f"Terraform Cloud plan run {run_id} — status {status.get('status', 'pending')}",
        outputs={"run_id": run_id, "workspace_id": ws_id, **status},
    )
    logs = (
        f"terraform cloud run create\n"
        f"workspace={ws_id} run={run_id} status={status.get('status')}\n"
        f"{status.get('message', '')}"
    )
    return IaCRunResult(success=True, logs=logs, plan=plan, outputs=plan.outputs)
