"""Verify pilot activation API state without printing tokens."""

from __future__ import annotations

import asyncio
import json

import httpx

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
BASE = "http://api:8000/nexora-api"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        health = await client.get("/health")
        login = await client.post(
            "/v1/auth/login",
            json={"email": "nexora-pilot-test-admin@example.com", "password": "PilotTestInternalOnly2026!"},
        )
        token = login.json().get("access_token") if login.status_code == 200 else None
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        switch = await client.post(
            "/v1/auth/switch-organization",
            headers=headers,
            json={"organization_id": ORG_ID},
        )
        token2 = switch.json().get("access_token") if switch.status_code == 200 else token
        headers2 = {"Authorization": f"Bearer {token2}"} if token2 else {}
        readiness = await client.get("/v1/pilot/readiness", headers=headers2)
        execution = await client.get("/v1/pilot/execution/status", headers=headers2)
        print(json.dumps({
            "health_status": health.status_code,
            "health_body_status": health.json().get("status"),
            "login_status": login.status_code,
            "switch_status": switch.status_code,
            "pilot_readiness_status": readiness.status_code,
            "pilot_execution_status": execution.status_code,
            "execution_status": execution.json().get("execution_status") if execution.status_code == 200 else None,
            "operation_limit": execution.json().get("operation_limit") if execution.status_code == 200 else None,
            "cooldown_minutes": execution.json().get("cooldown_minutes") if execution.status_code == 200 else None,
            "kill_switch": execution.json().get("kill_switch") if execution.status_code == 200 else None,
            "stages_count": len(execution.json().get("stages") or []) if execution.status_code == 200 else None,
        }))
        return 0 if readiness.status_code == 200 and execution.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
