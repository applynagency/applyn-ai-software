"""Unit tests for Terraform Cloud live plan helper."""

from __future__ import annotations

from unittest.mock import patch

from app.platform_engineering.iac import terraform_cloud_live


def test_create_plan_run_no_workspace():
    secret = {"organization": "acme", "token": "tok"}
    with patch("app.platform_engineering.iac.terraform_cloud_live.list_workspaces", return_value=[]):
        result = terraform_cloud_live.create_plan_run(secret)
    assert result.success is False
    assert "workspace" in (result.error or "").lower()


def test_create_plan_run_success():
    secret = {"organization": "acme", "token": "tok"}
    created = {"data": {"id": "run-abc"}}
    status = {"data": {"attributes": {"status": "pending", "message": "queued", "plan-only": True}}}
    with patch("app.platform_engineering.iac.terraform_cloud_live.post_json", return_value=created), patch(
        "app.platform_engineering.iac.terraform_cloud_live.get_json", return_value=status,
    ):
        result = terraform_cloud_live.create_plan_run(secret, workspace_id="ws-1")
    assert result.success is True
    assert result.plan is not None
    assert result.outputs.get("run_id") == "run-abc"
