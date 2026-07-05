"""Unit tests for Terraform Cloud live IaC adapter."""

from __future__ import annotations

from unittest.mock import patch

from app.platform_engineering.iac import terraform_cloud_live


def test_create_plan_run_live():
    secret = {"token": "tfc-token", "organization": "acme"}
    with patch.object(terraform_cloud_live, "post_json", return_value={"data": {"id": "run-plan-1"}}):
        with patch.object(terraform_cloud_live, "_run_status", return_value={"status": "pending", "message": "queued"}):
            with patch.object(terraform_cloud_live, "_resolve_workspace_id", return_value="ws-1"):
                result = terraform_cloud_live.create_plan_run(secret, variables={"workspace_id": "ws-1"})
    assert result.success is True
    assert result.simulated is False
    assert result.outputs["run_id"] == "run-plan-1"
    assert result.outputs["operation"] == "plan"


def test_create_apply_run_live():
    secret = {"token": "tfc-token", "organization": "acme"}
    with patch.object(terraform_cloud_live, "post_json", return_value={"data": {"id": "run-apply-1"}}):
        with patch.object(terraform_cloud_live, "_run_status", return_value={"status": "pending", "message": "queued"}):
            with patch.object(terraform_cloud_live, "_resolve_workspace_id", return_value="ws-1"):
                result = terraform_cloud_live.create_apply_run(secret, variables={"workspace_id": "ws-1"})
    assert result.success is True
    assert result.simulated is False
    assert result.outputs["operation"] == "apply"


def test_create_destroy_run_live():
    secret = {"token": "tfc-token", "organization": "acme"}
    with patch.object(terraform_cloud_live, "post_json", return_value={"data": {"id": "run-destroy-1"}}):
        with patch.object(terraform_cloud_live, "_run_status", return_value={"status": "pending", "message": "queued", "is_destroy": True}):
            with patch.object(terraform_cloud_live, "_resolve_workspace_id", return_value="ws-1"):
                result = terraform_cloud_live.create_destroy_run(secret, variables={"workspace_id": "ws-1"})
    assert result.success is True
    assert result.simulated is False
    assert result.outputs["operation"] == "destroy"
    assert result.plan.destroy == 1
