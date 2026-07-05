"""Sprint 68A — First customer non-production pilot onboarding tests."""

from __future__ import annotations

from app.pilot.customer_onboarding_evidence import compute_onboarding_status, redact_onboarding_blob
from app.pilot.launch_readiness import _integrations_for_provider, evaluate_customer_launch_readiness
from app.tests.test_customer_pilot_deployment import _deploy_payload


def test_gitea_counts_as_github_for_launch_readiness():
    integrations = [{"provider_type": "GITEA", "lifecycle_state": "CONNECTED", "provider_mode": "live", "freshness_ok": True, "capabilities": {"read": True}}]
    assert _integrations_for_provider(integrations, "GITHUB")


def test_launch_readiness_go_with_gitea_provider():
    payload = {
        "pilot_mode_enabled": True,
        "org_allowlisted": True,
        "enrollment": {"id": "e1", "kill_switch": False, "operation_limit": 2},
        "integrations": [
            {"provider_type": "KUBERNETES", "lifecycle_state": "CONNECTED", "provider_mode": "live", "freshness_ok": True, "capabilities": {"kubernetes.workloads.write": True}, "rbac_evidence": {"namespace_scoped": True}},
            {"provider_type": "GITEA", "lifecycle_state": "CONNECTED", "provider_mode": "live", "freshness_ok": True, "capabilities": {"read": True}},
            {"provider_type": "PROMETHEUS", "lifecycle_state": "CONNECTED", "provider_mode": "live", "freshness_ok": True, "capabilities": {"read": True}},
        ],
        "environments": [{"tier": "STAGING", "name": "staging"}],
        "contacts": {"approval_contact": "Approver", "support_contact": "support@example.com"},
        "backup_restore_documented": True,
    }
    result = evaluate_customer_launch_readiness(payload)
    assert result["verdict"] == "GO"


def test_onboarding_status_ready_for_approval_package():
    evidence = {
        "integration_readiness": {"verdict": "GO"},
        "launch_readiness": {"verdict": "GO"},
        "operations_readiness": {"verdict": "GO"},
        "deployment_readiness": {"verdict": "GO"},
        "provider_onboarding": {
            "KUBERNETES": {"lifecycle": "CONNECTED", "provider_mode": "live"},
            "GITEA": {"lifecycle": "CONNECTED", "provider_mode": "live"},
            "PROMETHEUS": {"lifecycle": "CONNECTED", "provider_mode": "live"},
        },
        "assessment": {"completed": True},
        "baseline_capture": {"completed": True},
        "provider_mutation": False,
        "redaction_scan": {"passed": True},
    }
    status = compute_onboarding_status(evidence)
    assert status["status"] == "READY_FOR_CUSTOMER_APPROVAL_PACKAGE"
    assert status["execution_performed"] is False


def test_onboarding_status_stop_on_no_go():
    evidence = {
        "integration_readiness": {"verdict": "NO_GO"},
        "launch_readiness": {"verdict": "GO"},
        "operations_readiness": {"verdict": "GO"},
        "deployment_readiness": {"verdict": "GO"},
        "assessment": {"completed": False},
        "baseline_capture": {"completed": False},
        "provider_mutation": False,
        "redaction_scan": {"passed": True},
    }
    status = compute_onboarding_status(evidence)
    assert status["status"] == "STOP"


def test_redact_onboarding_strips_kubeconfig():
    redacted = redact_onboarding_blob({"kubeconfig": "apiVersion: v1", "title": "ok"})
    assert redacted["kubeconfig"] == "[REDACTED]"
    assert redacted["title"] == "ok"


from app.pilot.deployment_readiness import evaluate_pilot_deployment_readiness
from app.tests.test_customer_pilot_deployment import _deploy_payload


def test_gitea_pick_for_github_assessment():
    from app.pilot.launch_readiness import _PROVIDER_ALIASES
    from app.services.pilot import PilotService

    class Conn:
        def __init__(self, provider_type, lifecycle_state="CONNECTED", provider_mode="live", last_validated_at=None):
            self.provider_type = provider_type
            self.lifecycle_state = lifecycle_state
            self.provider_mode = provider_mode
            self.last_validated_at = last_validated_at
            self.id = f"id-{provider_type}"

    svc = PilotService.__new__(PilotService)
    conns = [Conn("GITEA")]
    picked = svc._pick_live_connection(conns, "GITHUB")
    assert picked is not None
    assert picked.provider_type == "GITEA"
    assert "GITEA" in _PROVIDER_ALIASES["GITHUB"]


def test_deployment_readiness_still_go_in_app_only():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        email_notifications_enabled=False,
        alert_receiver_configured=True,
        alert_delivery_verified=True,
    ))
    assert result["verdict"] == "GO"


def test_approval_package_includes_meridian_limitations():
    from app.pilot.approval_package import build_approval_package

    pack = build_approval_package(
        operation={"id": "op1", "action": "scale_deployment", "resource_name": "pilot-demo", "params": {"namespace": "nexora-pilot"}},
        approval={"id": "a1", "status": "PENDING", "operation_summary": "scale", "rollback_plan": "rollback"},
        enrollment={"id": "e1"},
        baseline=None,
        integration=None,
        preflight=None,
        maintenance_window="Saturday 02:00–04:00 UTC",
        evidence_limitations=["workflow history unavailable"],
        verification_plan=["three Ready pods"],
    )
    assert pack["maintenance_window"] == "Saturday 02:00–04:00 UTC"
    assert "workflow history unavailable" in pack["evidence_limitations"]
    assert pack["verification_plan"] == ["three Ready pods"]
