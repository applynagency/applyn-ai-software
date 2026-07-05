"""Unit tests for live Argo CD GitOps helpers."""

from __future__ import annotations

from unittest.mock import patch

from app.delivery.gitops import argocd_live


def test_sync_application_missing_credentials():
    result = argocd_live.sync_application({}, "checkout")
    assert result["simulated"] is True
    assert result["status"] == "failed"


def test_sync_application_success():
    secret = {"endpoint": "https://argocd.example.com", "token": "tok"}
    with patch("app.delivery.gitops.argocd_live.post_json", return_value={"status": {"operationState": {"phase": "Running"}}}):
        result = argocd_live.sync_application(secret, "checkout", prune=True)
    assert result["simulated"] is False
    assert result["status"] == "sync_triggered"
    assert result["app"] == "checkout"


def test_rollback_application_success():
    secret = {"endpoint": "https://argocd.example.com", "token": "tok"}
    with patch("app.delivery.gitops.argocd_live.post_json", return_value={}):
        result = argocd_live.rollback_application(secret, "checkout", 3)
    assert result["simulated"] is False
    assert result["status"] == "rollback_initiated"
    assert result["revision"] == 3
