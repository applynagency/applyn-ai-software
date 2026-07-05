#!/usr/bin/env python3
"""Smoke test for a running Nexora API instance."""

from __future__ import annotations

import os
import sys
import uuid

import httpx

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000/nexora-api").rstrip("/")
TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "30"))
ALLOW_AGENT_FAILURE = os.environ.get("SMOKE_ALLOW_AGENT_FAILURE", "0") == "1"


def ok(name: str) -> None:
    print(f"OK  {name}")


def fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}", file=sys.stderr)
    raise SystemExit(1)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"smoke-{suffix}@example.com"
    username = f"smoke{suffix}"
    password = "password123"

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        health = client.get("/health")
        if health.status_code != 200:
            fail("health", f"status={health.status_code}")
        ok("health")

        register = client.post(
            "/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "full_name": "Smoke Tester",
                "password": password,
            },
        )
        if register.status_code != 201:
            fail("register", register.text)
        ok("register")

        login = client.post(
            "/v1/auth/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            fail("login", login.text)
        tokens = login.json()
        access_token = tokens["access_token"]
        ok("login")

        me = client.get("/v1/auth/me", headers=auth_headers(access_token))
        if me.status_code != 200:
            fail("auth/me", me.text)
        ok("auth/me")

        org = client.post(
            "/v1/organizations",
            headers=auth_headers(access_token),
            json={"name": f"Smoke Org {suffix}", "slug": f"smoke-org-{suffix}"},
        )
        if org.status_code != 201:
            fail("organization", org.text)
        organization_id = org.json()["id"]
        ok("organization")

        switched = client.post(
            f"/v1/organizations/{organization_id}/switch",
            headers=auth_headers(access_token),
        )
        if switched.status_code != 200:
            fail("organization switch", switched.text)
        access_token = switched.json()["access_token"]
        ok("organization switch")

        team = client.post(
            "/v1/teams",
            headers=auth_headers(access_token),
            json={"name": f"Smoke Team {suffix}", "team_type": "PRODUCT"},
        )
        if team.status_code != 201:
            fail("team", team.text)
        team_id = team.json()["id"]
        ok("team")

        workflow = client.post(
            "/v1/workflows",
            headers=auth_headers(access_token),
            json={"name": f"Smoke Workflow {suffix}", "status": "ACTIVE"},
        )
        if workflow.status_code != 201:
            fail("workflow", workflow.text)
        workflow_id = workflow.json()["id"]
        ok("workflow")

        stage = client.post(
            f"/v1/workflows/{workflow_id}/stages",
            headers=auth_headers(access_token),
            json={"name": "Planning", "sequence": 1, "stage_type": "PLANNING"},
        )
        if stage.status_code != 201:
            fail("workflow stage", stage.text)
        stage_id = stage.json()["id"]

        assign = client.post(
            f"/v1/stages/{stage_id}/teams",
            headers=auth_headers(access_token),
            json={"team_id": team_id, "execution_order": 1},
        )
        if assign.status_code != 201:
            fail("stage team assignment", assign.text)
        ok("workflow stage + team")

        workspace = client.post(
            "/v1/workspaces",
            headers=auth_headers(access_token),
            json={"name": f"Smoke Workspace {suffix}", "slug": f"smoke-ws-{suffix}"},
        )
        if workspace.status_code != 201:
            fail("workspace", workspace.text)

        project = client.post(
            "/v1/projects",
            headers=auth_headers(access_token),
            json={
                "name": f"Smoke Project {suffix}",
                "slug": f"smoke-proj-{suffix}",
                "workspace_id": workspace.json()["id"],
            },
        )
        if project.status_code != 201:
            fail("project", project.text)

        requirement = client.post(
            "/v1/requirements",
            headers=auth_headers(access_token),
            json={
                "title": "Smoke requirement",
                "content": "Validate end-to-end platform wiring.",
                "project_id": project.json()["id"],
            },
        )
        if requirement.status_code != 201:
            fail("requirement", requirement.text)
        requirement_id = requirement.json()["id"]

        execution = client.post(
            f"/v1/workflows/{workflow_id}/execute",
            headers=auth_headers(access_token),
            json={
                "project_id": project.json()["id"],
                "requirement_id": requirement_id,
            },
        )
        if execution.status_code != 201:
            if ALLOW_AGENT_FAILURE and execution.status_code in {400, 422, 500}:
                ok("workflow execute (agent failure allowed)")
            else:
                fail("workflow execute", execution.text)
        else:
            data = execution.json()
            status = data.get("status")
            if status not in {"WAITING_FOR_APPROVAL", "COMPLETED", "RUNNING", "FAILED"}:
                fail("workflow execution status", str(status))
            ok(f"workflow execute ({status})")

        deployments = client.get("/v1/deployments", headers=auth_headers(access_token))
        if deployments.status_code != 200:
            fail("deployment list", deployments.text)
        ok("deployment flow")

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
