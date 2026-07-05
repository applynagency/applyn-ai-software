"""Auto-generated Nexora Python SDK. Do not edit by hand.

Regenerate with ``python -m scripts.generate_sdk``.
"""

from __future__ import annotations

from typing import Any

import httpx


class NexoraClient:
    def __init__(self, base_url: str, token: str | None = None,
                 *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(base_url=self.base_url, headers=headers,
                                    timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "NexoraClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, method: str, path: str, *, params: dict | None = None,
                json: Any = None) -> Any:
        resp = self._client.request(method, path, params=params, json=json)
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.text

    def abort_rollout_nexora_api_v1_delivery_release_reliability_reliability_id_abort_post(self, reliability_id: str) -> Any:
        """Abort Rollout"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/abort".format(reliability_id=reliability_id))

    def academy_dashboard_nexora_api_v1_customer_success_academy_get(self, *, params: dict | None = None) -> Any:
        """Academy Dashboard"""
        return self.request("GET", "/nexora-api/v1/customer-success/academy", params=params)

    def academy_progress_nexora_api_v1_customer_success_academy_progress_post(self, *, json: Any = None) -> Any:
        """Academy Progress"""
        return self.request("POST", "/nexora-api/v1/customer-success/academy/progress", json=json)

    def academy_track_nexora_api_v1_customer_success_academy_tracks_key_get(self, key: str, *, params: dict | None = None) -> Any:
        """Academy Track"""
        return self.request("GET", "/nexora-api/v1/customer-success/academy/tracks/{key}".format(key=key), params=params)

    def academy_track_progress_nexora_api_v1_customer_success_academy_tracks_key_progress_post(self, key: str, *, json: Any = None) -> Any:
        """Academy Track Progress"""
        return self.request("POST", "/nexora-api/v1/customer-success/academy/tracks/{key}/progress".format(key=key), json=json)

    def academy_tracks_nexora_api_v1_customer_success_academy_tracks_get(self, *, params: dict | None = None) -> Any:
        """Academy Tracks"""
        return self.request("GET", "/nexora-api/v1/customer-success/academy/tracks", params=params)

    def accept_invitation_nexora_api_v1_invitations_accept_post(self, *, json: Any = None) -> Any:
        """Accept Invitation"""
        return self.request("POST", "/nexora-api/v1/invitations/accept", json=json)

    def acknowledge_communication_nexora_api_v1_customer_pilot_communications_communication_id_acknowledge_post(self, communication_id: str) -> Any:
        """Acknowledge Communication"""
        return self.request("POST", "/nexora-api/v1/customer-pilot/communications/{communication_id}/acknowledge".format(communication_id=communication_id))

    def acknowledge_connection_expiry_nexora_api_v1_integrations_connections_connection_id_acknowledge_expiry_post(self, connection_id: str, *, json: Any = None) -> Any:
        """Acknowledge Connection Expiry"""
        return self.request("POST", "/nexora-api/v1/integrations/connections/{connection_id}/acknowledge-expiry".format(connection_id=connection_id), json=json)

    def acknowledge_drift_nexora_api_v1_platform_engineering_drift_finding_id_acknowledge_post(self, finding_id: str) -> Any:
        """Acknowledge Drift"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/drift/{finding_id}/acknowledge".format(finding_id=finding_id))

    def acknowledge_incident_nexora_api_v1_incidents_investigation_id_acknowledge_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Acknowledge Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/acknowledge".format(investigation_id=investigation_id), json=json)

    def acknowledge_nexora_api_v1_oncall_incidents_incident_id_acknowledge_post(self, incident_id: str, *, json: Any = None) -> Any:
        """Acknowledge"""
        return self.request("POST", "/nexora-api/v1/oncall/incidents/{incident_id}/acknowledge".format(incident_id=incident_id), json=json)

    def acknowledge_session_nexora_api_v1_onboarding_integrations_sessions_session_id_acknowledge_post(self, session_id: str, *, json: Any = None) -> Any:
        """Acknowledge Session"""
        return self.request("POST", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/acknowledge".format(session_id=session_id), json=json)

    def add_comment_nexora_api_v1_product_collaboration_resource_type_resource_id_comments_post(self, resource_type: str, resource_id: str, *, json: Any = None) -> Any:
        """Add Comment"""
        return self.request("POST", "/nexora-api/v1/product/collaboration/{resource_type}/{resource_id}/comments".format(resource_type=resource_type, resource_id=resource_id), json=json)

    def add_incident_comment_nexora_api_v1_incidents_investigation_id_comments_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Add Incident Comment"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/comments".format(investigation_id=investigation_id), json=json)

    def add_organization_member_nexora_api_v1_organizations_organization_id_members_post(self, organization_id: str, *, json: Any = None) -> Any:
        """Add Organization Member"""
        return self.request("POST", "/nexora-api/v1/organizations/{organization_id}/members".format(organization_id=organization_id), json=json)

    def add_reaction_nexora_api_v1_product_collaboration_reactions_post(self, *, params: dict | None = None, json: Any = None) -> Any:
        """Add Reaction"""
        return self.request("POST", "/nexora-api/v1/product/collaboration/reactions", params=params, json=json)

    def add_status_component_nexora_api_v1_incidents_status_pages_page_id_components_post(self, page_id: str, *, json: Any = None) -> Any:
        """Add Status Component"""
        return self.request("POST", "/nexora-api/v1/incidents/status-pages/{page_id}/components".format(page_id=page_id), json=json)

    def adoption_analytics_analyze_nexora_api_v1_customer_success_adoption_analytics_analyze_post(self, *, json: Any = None) -> Any:
        """Adoption Analytics Analyze"""
        return self.request("POST", "/nexora-api/v1/customer-success/adoption-analytics/analyze", json=json)

    def adoption_analytics_nexora_api_v1_customer_success_adoption_analytics_get(self) -> Any:
        """Adoption Analytics"""
        return self.request("GET", "/nexora-api/v1/customer-success/adoption-analytics")

    def advance_execution_stage_nexora_api_v1_pilot_execution_stages_stage_key_advance_post(self, stage_key: str) -> Any:
        """Advance Execution Stage"""
        return self.request("POST", "/nexora-api/v1/pilot/execution/stages/{stage_key}/advance".format(stage_key=stage_key))

    def ai_budget_nexora_api_v1_ai_budget_get(self) -> Any:
        """Ai Budget"""
        return self.request("GET", "/nexora-api/v1/ai/budget")

    def ai_context_nexora_api_v1_operator_ai_context_get(self) -> Any:
        """Ai Context"""
        return self.request("GET", "/nexora-api/v1/operator/ai-context")

    def ai_context_nexora_api_v1_ops_workspace_ai_context_post(self, *, json: Any = None) -> Any:
        """Ai Context"""
        return self.request("POST", "/nexora-api/v1/ops-workspace/ai-context", json=json)

    def ai_context_nexora_api_v1_platform_engineering_ai_context_get(self, *, params: dict | None = None) -> Any:
        """Ai Context"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/ai-context", params=params)

    def ai_health_nexora_api_v1_ai_health_get(self) -> Any:
        """Ai Health"""
        return self.request("GET", "/nexora-api/v1/ai/health")

    def ai_tool_connection_status_nexora_api_v1_ai_tools_tool_id_connection_status_get(self, tool_id: str) -> Any:
        """Ai Tool Connection Status"""
        return self.request("GET", "/nexora-api/v1/ai-tools/{tool_id}/connection-status".format(tool_id=tool_id))

    def alert_intelligence_nexora_api_v1_observability_alerts_intelligence_get(self) -> Any:
        """Alert Intelligence"""
        return self.request("GET", "/nexora-api/v1/observability/alerts/intelligence")

    def analytics_nexora_api_v1_security_analytics_get(self) -> Any:
        """Analytics"""
        return self.request("GET", "/nexora-api/v1/security/analytics")

    def analytics_summary_nexora_api_v1_product_analytics_summary_get(self, *, params: dict | None = None) -> Any:
        """Analytics Summary"""
        return self.request("GET", "/nexora-api/v1/product/analytics/summary", params=params)

    def analyze_change_failure_nexora_api_v1_change_failure_prediction_analyze_post(self, *, json: Any = None) -> Any:
        """Analyze Change Failure"""
        return self.request("POST", "/nexora-api/v1/change-failure-prediction/analyze", json=json)

    def analyze_cost_nexora_api_v1_cost_optimization_analyze_post(self, *, json: Any = None) -> Any:
        """Analyze Cost"""
        return self.request("POST", "/nexora-api/v1/cost-optimization/analyze", json=json)

    def analyze_deployment_risk_nexora_api_v1_deployment_risk_analyze_post(self, *, json: Any = None) -> Any:
        """Analyze Deployment Risk"""
        return self.request("POST", "/nexora-api/v1/deployment-risk/analyze", json=json)

    def analyze_deployment_safety_nexora_api_v1_deployment_safety_analyze_post(self, *, json: Any = None) -> Any:
        """Analyze Deployment Safety"""
        return self.request("POST", "/nexora-api/v1/deployment-safety/analyze", json=json)

    def analyze_nexora_api_v1_operator_analyze_post(self, *, json: Any = None) -> Any:
        """Analyze"""
        return self.request("POST", "/nexora-api/v1/operator/analyze", json=json)

    def analyze_nexora_api_v1_reliability_analyze_post(self) -> Any:
        """Analyze"""
        return self.request("POST", "/nexora-api/v1/reliability/analyze")

    def analyze_rca_nexora_api_v1_sre_rca_incident_id_analyze_post(self, incident_id: str) -> Any:
        """Analyze Rca"""
        return self.request("POST", "/nexora-api/v1/sre/rca/{incident_id}/analyze".format(incident_id=incident_id))

    def annotation_summary_nexora_api_v1_customer_success_annotations_summary_get(self) -> Any:
        """Annotation Summary"""
        return self.request("GET", "/nexora-api/v1/customer-success/annotations/summary")

    def apply_ai_agent_template_nexora_api_v1_ai_agent_templates_apply_post(self, *, json: Any = None) -> Any:
        """Apply Ai Agent Template"""
        return self.request("POST", "/nexora-api/v1/ai-agent-templates/apply", json=json)

    def apply_team_template_nexora_api_v1_team_templates_apply_post(self, *, json: Any = None) -> Any:
        """Apply Team Template"""
        return self.request("POST", "/nexora-api/v1/team-templates/apply", json=json)

    def apply_workflow_template_nexora_api_v1_workflow_templates_apply_post(self, *, json: Any = None) -> Any:
        """Apply Workflow Template"""
        return self.request("POST", "/nexora-api/v1/workflow-templates/apply", json=json)

    def approve_agent_nexora_api_v1_ai_agents_run_id_approve_post(self, run_id: str) -> Any:
        """Approve Agent"""
        return self.request("POST", "/nexora-api/v1/ai/agents/{run_id}/approve".format(run_id=run_id))

    def approve_artifact_nexora_api_v1_approval_artifact_id_approve_post(self, artifact_id: str, *, json: Any = None) -> Any:
        """Approve Artifact"""
        return self.request("POST", "/nexora-api/v1/approval/{artifact_id}/approve".format(artifact_id=artifact_id), json=json)

    def approve_commander_nexora_api_v1_sre_commander_commander_id_approve_post(self, commander_id: str) -> Any:
        """Approve Commander"""
        return self.request("POST", "/nexora-api/v1/sre/commander/{commander_id}/approve".format(commander_id=commander_id))

    def approve_execution_nexora_api_v1_platform_executions_run_id_approve_post(self, run_id: str, *, json: Any = None) -> Any:
        """Approve Execution"""
        return self.request("POST", "/nexora-api/v1/platform/executions/{run_id}/approve".format(run_id=run_id), json=json)

    def approve_release_nexora_api_v1_delivery_releases_release_id_approve_post(self, release_id: str) -> Any:
        """Approve Release"""
        return self.request("POST", "/nexora-api/v1/delivery/releases/{release_id}/approve".format(release_id=release_id))

    def approve_remediation_action_nexora_api_v1_remediation_actions_action_id_approve_post(self, action_id: str, *, json: Any = None) -> Any:
        """Approve Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/approve".format(action_id=action_id), json=json)

    def approve_runbook_execution_nexora_api_v1_sre_runbooks_executions_execution_id_approve_post(self, execution_id: str) -> Any:
        """Approve Runbook Execution"""
        return self.request("POST", "/nexora-api/v1/sre/runbooks/executions/{execution_id}/approve".format(execution_id=execution_id))

    def approve_workflow_approval_nexora_api_v1_workflow_approvals_approval_id_approve_post(self, approval_id: str, *, json: Any = None) -> Any:
        """Approve Workflow Approval"""
        return self.request("POST", "/nexora-api/v1/workflow-approvals/{approval_id}/approve".format(approval_id=approval_id), json=json)

    def archive_ai_agent_nexora_api_v1_ai_agents_agent_id_archive_post(self, agent_id: str) -> Any:
        """Archive Ai Agent"""
        return self.request("POST", "/nexora-api/v1/ai-agents/{agent_id}/archive".format(agent_id=agent_id))

    def archive_team_nexora_api_v1_teams_team_id_archive_post(self, team_id: str) -> Any:
        """Archive Team"""
        return self.request("POST", "/nexora-api/v1/teams/{team_id}/archive".format(team_id=team_id))

    def archive_workflow_nexora_api_v1_workflows_workflow_id_archive_post(self, workflow_id: str) -> Any:
        """Archive Workflow"""
        return self.request("POST", "/nexora-api/v1/workflows/{workflow_id}/archive".format(workflow_id=workflow_id))

    def assess_change_risk_nexora_api_v1_sre_change_risk_assess_post(self, *, json: Any = None) -> Any:
        """Assess Change Risk"""
        return self.request("POST", "/nexora-api/v1/sre/change-risk/assess", json=json)

    def assign_agent_to_stage_nexora_api_v1_ai_agents_agent_id_assign_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Assign Agent To Stage"""
        return self.request("POST", "/nexora-api/v1/ai-agents/{agent_id}/assign".format(agent_id=agent_id), json=json)

    def assign_ai_team_agent_tool_nexora_api_v1_ai_team_agents_agent_id_tools_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Assign Ai Team Agent Tool"""
        return self.request("POST", "/nexora-api/v1/ai-team-agents/{agent_id}/tools".format(agent_id=agent_id), json=json)

    def assign_incident_nexora_api_v1_incidents_investigation_id_assign_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Assign Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/assign".format(investigation_id=investigation_id), json=json)

    def assign_plan_nexora_api_v1_billing_admin_orgs_org_id_assign_plan_post(self, org_id: str, *, json: Any = None) -> Any:
        """Assign Plan"""
        return self.request("POST", "/nexora-api/v1/billing/admin/orgs/{org_id}/assign-plan".format(org_id=org_id), json=json)

    def assign_team_nexora_api_v1_stages_stage_id_teams_post(self, stage_id: str, *, json: Any = None) -> Any:
        """Assign Team"""
        return self.request("POST", "/nexora-api/v1/stages/{stage_id}/teams".format(stage_id=stage_id), json=json)

    def attach_ai_tool_credential_nexora_api_v1_ai_tools_tool_id_credentials_post(self, tool_id: str, *, json: Any = None) -> Any:
        """Attach Ai Tool Credential"""
        return self.request("POST", "/nexora-api/v1/ai-tools/{tool_id}/credentials".format(tool_id=tool_id), json=json)

    def automation_suggestions_nexora_api_v1_ops_workspace_automation_suggestions_get(self) -> Any:
        """Automation Suggestions"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/automation-suggestions")

    def backfill_dry_run_nexora_api_v1_security_backfill_dry_run_post(self) -> Any:
        """Backfill Dry Run"""
        return self.request("POST", "/nexora-api/v1/security/backfill/dry-run")

    def backfill_execute_nexora_api_v1_security_backfill_execute_post(self) -> Any:
        """Backfill Execute"""
        return self.request("POST", "/nexora-api/v1/security/backfill/execute")

    def backfill_status_nexora_api_v1_security_backfill_status_get(self) -> Any:
        """Backfill Status"""
        return self.request("GET", "/nexora-api/v1/security/backfill/status")

    def bind_remediation_action_nexora_api_v1_remediation_actions_action_id_bind_post(self, action_id: str, *, json: Any = None) -> Any:
        """Bind Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/bind".format(action_id=action_id), json=json)

    def blast_radius_dashboard_nexora_api_v1_blast_radius_dashboard_get(self) -> Any:
        """Blast Radius Dashboard"""
        return self.request("GET", "/nexora-api/v1/blast-radius/dashboard")

    def bulk_nexora_api_v1_scim_v2_bulk_post(self) -> Any:
        """Bulk"""
        return self.request("POST", "/nexora-api/v1/scim/v2/Bulk")

    def cancel_agent_nexora_api_v1_ai_agents_run_id_cancel_post(self, run_id: str) -> Any:
        """Cancel Agent"""
        return self.request("POST", "/nexora-api/v1/ai/agents/{run_id}/cancel".format(run_id=run_id))

    def cancel_communication_nexora_api_v1_pilot_communications_communication_id_cancel_post(self, communication_id: str) -> Any:
        """Cancel Communication"""
        return self.request("POST", "/nexora-api/v1/pilot/communications/{communication_id}/cancel".format(communication_id=communication_id))

    def cancel_execution_nexora_api_v1_platform_executions_run_id_cancel_post(self, run_id: str) -> Any:
        """Cancel Execution"""
        return self.request("POST", "/nexora-api/v1/platform/executions/{run_id}/cancel".format(run_id=run_id))

    def cancel_job_nexora_api_v1_jobs_job_id_cancel_post(self, job_id: str) -> Any:
        """Cancel Job"""
        return self.request("POST", "/nexora-api/v1/jobs/{job_id}/cancel".format(job_id=job_id))

    def cancel_session_nexora_api_v1_onboarding_integrations_sessions_session_id_cancel_post(self, session_id: str, *, json: Any = None) -> Any:
        """Cancel Session"""
        return self.request("POST", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/cancel".format(session_id=session_id), json=json)

    def capacity_dashboard_nexora_api_v1_capacity_dashboard_get(self) -> Any:
        """Capacity Dashboard"""
        return self.request("GET", "/nexora-api/v1/capacity/dashboard")

    def capture_baseline_nexora_api_v1_pilot_baseline_capture_post(self) -> Any:
        """Capture Baseline"""
        return self.request("POST", "/nexora-api/v1/pilot/baseline/capture")

    def capture_incident_knowledge_nexora_api_v1_sre_learning_capture_post(self, *, json: Any = None) -> Any:
        """Capture Incident Knowledge"""
        return self.request("POST", "/nexora-api/v1/sre/learning/capture", json=json)

    def change_center_nexora_api_v1_ops_workspace_changes_get(self) -> Any:
        """Change Center"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/changes")

    def change_failure_dashboard_nexora_api_v1_change_failure_prediction_dashboard_get(self) -> Any:
        """Change Failure Dashboard"""
        return self.request("GET", "/nexora-api/v1/change-failure-prediction/dashboard")

    def chat_nexora_api_v1_copilot_chat_post(self, *, json: Any = None) -> Any:
        """Chat"""
        return self.request("POST", "/nexora-api/v1/copilot/chat", json=json)

    def chat_stream_nexora_api_v1_copilot_chat_stream_post(self, *, json: Any = None) -> Any:
        """Chat Stream"""
        return self.request("POST", "/nexora-api/v1/copilot/chat/stream", json=json)

    def check_execution_readiness_nexora_api_v1_pilot_live_operations_operation_id_execution_readiness_post(self, operation_id: str) -> Any:
        """Check Execution Readiness"""
        return self.request("POST", "/nexora-api/v1/pilot/live-operations/{operation_id}/execution-readiness".format(operation_id=operation_id))

    def check_pilot_readiness_nexora_api_v1_pilot_readiness_check_post(self) -> Any:
        """Check Pilot Readiness"""
        return self.request("POST", "/nexora-api/v1/pilot/readiness/check")

    def checkpoint_execution_nexora_api_v1_platform_executions_run_id_checkpoint_post(self, run_id: str, *, json: Any = None) -> Any:
        """Checkpoint Execution"""
        return self.request("POST", "/nexora-api/v1/platform/executions/{run_id}/checkpoint".format(run_id=run_id), json=json)

    def clone_plan_nexora_api_v1_billing_admin_plans_plan_id_clone_post(self, plan_id: str, *, json: Any = None) -> Any:
        """Clone Plan"""
        return self.request("POST", "/nexora-api/v1/billing/admin/plans/{plan_id}/clone".format(plan_id=plan_id), json=json)

    def close_internal_pilot_nexora_api_v1_pilot_closure_post(self, *, json: Any = None) -> Any:
        """Close Internal Pilot"""
        return self.request("POST", "/nexora-api/v1/pilot/closure", json=json)

    def cloud_costs_nexora_api_v1_control_plane_cloud_accounts_account_id_costs_get(self, account_id: str) -> Any:
        """Cloud Costs"""
        return self.request("GET", "/nexora-api/v1/control-plane/cloud-accounts/{account_id}/costs".format(account_id=account_id))

    def cloud_posture_nexora_api_v1_security_cloud_get(self) -> Any:
        """Cloud Posture"""
        return self.request("GET", "/nexora-api/v1/security/cloud")

    def cluster_read_nexora_api_v1_control_plane_clusters_cluster_id_read_post(self, cluster_id: str, *, params: dict | None = None) -> Any:
        """Cluster Read"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/read".format(cluster_id=cluster_id), params=params)

    def collect_diagnostics_nexora_api_v1_control_plane_clusters_cluster_id_k8s_diagnostics_post(self, cluster_id: str, *, json: Any = None) -> Any:
        """Collect Diagnostics"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/diagnostics".format(cluster_id=cluster_id), json=json)

    def command_palette_nexora_api_v1_product_commands_get(self, *, params: dict | None = None) -> Any:
        """Command Palette"""
        return self.request("GET", "/nexora-api/v1/product/commands", params=params)

    def comment_communication_nexora_api_v1_customer_pilot_communications_communication_id_comment_post(self, communication_id: str, *, json: Any = None) -> Any:
        """Comment Communication"""
        return self.request("POST", "/nexora-api/v1/customer-pilot/communications/{communication_id}/comment".format(communication_id=communication_id), json=json)

    def competitive_comparison_nexora_api_v1_sales_competitive_comparison_get(self, *, params: dict | None = None) -> Any:
        """Competitive Comparison"""
        return self.request("GET", "/nexora-api/v1/sales/competitive-comparison", params=params)

    def complete_nexora_api_v1_ai_complete_post(self, *, json: Any = None) -> Any:
        """Complete"""
        return self.request("POST", "/nexora-api/v1/ai/complete", json=json)

    def complete_onboarding_nexora_api_v1_onboarding_session_id_complete_post(self, session_id: str) -> Any:
        """Complete Onboarding"""
        return self.request("POST", "/nexora-api/v1/onboarding/{session_id}/complete".format(session_id=session_id))

    def complete_tour_nexora_api_v1_product_tours_tour_id_complete_post(self, tour_id: str) -> Any:
        """Complete Tour"""
        return self.request("POST", "/nexora-api/v1/product-tours/{tour_id}/complete".format(tour_id=tour_id))

    def compliance_nexora_api_v1_security_compliance_get(self) -> Any:
        """Compliance"""
        return self.request("GET", "/nexora-api/v1/security/compliance")

    def confirm_live_operation_nexora_api_v1_pilot_live_operations_operation_id_confirm_post(self, operation_id: str, *, json: Any = None) -> Any:
        """Confirm Live Operation"""
        return self.request("POST", "/nexora-api/v1/pilot/live-operations/{operation_id}/confirm".format(operation_id=operation_id), json=json)

    def confirm_mfa_nexora_api_v1_auth_mfa_confirm_post(self, *, json: Any = None) -> Any:
        """Confirm Mfa"""
        return self.request("POST", "/nexora-api/v1/auth/mfa/confirm", json=json)

    def connect_integration_nexora_api_v1_integrations_connect_post(self, *, json: Any = None) -> Any:
        """Connect Integration"""
        return self.request("POST", "/nexora-api/v1/integrations/connect", json=json)

    def connect_source_nexora_api_v1_delivery_source_connections_post(self, *, json: Any = None) -> Any:
        """Connect Source"""
        return self.request("POST", "/nexora-api/v1/delivery/source-connections", json=json)

    def consistency_nexora_api_v1_customer_success_consistency_get(self) -> Any:
        """Consistency"""
        return self.request("GET", "/nexora-api/v1/customer-success/consistency")

    def contextual_help_nexora_api_v1_product_tours_contextual_get(self, *, params: dict | None = None) -> Any:
        """Contextual Help"""
        return self.request("GET", "/nexora-api/v1/product-tours/contextual", params=params)

    def coordinate_incident_nexora_api_v1_incidents_coordinate_post(self, *, json: Any = None) -> Any:
        """Coordinate Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/coordinate", json=json)

    def correlate_nexora_api_v1_observability_correlation_post(self, *, json: Any = None) -> Any:
        """Correlate"""
        return self.request("POST", "/nexora-api/v1/observability/correlation", json=json)

    def cost_dashboard_nexora_api_v1_cost_optimization_dashboard_get(self) -> Any:
        """Cost Dashboard"""
        return self.request("GET", "/nexora-api/v1/cost-optimization/dashboard")

    def cost_operations_nexora_api_v1_ops_workspace_cost_get(self) -> Any:
        """Cost Operations"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/cost")

    def cost_report_nexora_api_v1_ai_cost_get(self, *, params: dict | None = None) -> Any:
        """Cost Report"""
        return self.request("GET", "/nexora-api/v1/ai/cost", params=params)

    def create_agent_input_nexora_api_v1_ai_agents_agent_id_inputs_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Create Agent Input"""
        return self.request("POST", "/nexora-api/v1/ai-agents/{agent_id}/inputs".format(agent_id=agent_id), json=json)

    def create_agent_output_nexora_api_v1_ai_agents_agent_id_outputs_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Create Agent Output"""
        return self.request("POST", "/nexora-api/v1/ai-agents/{agent_id}/outputs".format(agent_id=agent_id), json=json)

    def create_agent_responsibility_nexora_api_v1_ai_agents_agent_id_responsibilities_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Create Agent Responsibility"""
        return self.request("POST", "/nexora-api/v1/ai-agents/{agent_id}/responsibilities".format(agent_id=agent_id), json=json)

    def create_ai_agent_nexora_api_v1_ai_agents_post(self, *, json: Any = None) -> Any:
        """Create Ai Agent"""
        return self.request("POST", "/nexora-api/v1/ai-agents", json=json)

    def create_ai_team_agent_memory_nexora_api_v1_ai_team_agents_agent_id_memory_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Create Ai Team Agent Memory"""
        return self.request("POST", "/nexora-api/v1/ai-team-agents/{agent_id}/memory".format(agent_id=agent_id), json=json)

    def create_ai_team_agent_nexora_api_v1_ai_team_agents_post(self, *, json: Any = None) -> Any:
        """Create Ai Team Agent"""
        return self.request("POST", "/nexora-api/v1/ai-team-agents", json=json)

    def create_ai_team_nexora_api_v1_ai_teams_post(self, *, json: Any = None) -> Any:
        """Create Ai Team"""
        return self.request("POST", "/nexora-api/v1/ai-teams", json=json)

    def create_ai_team_workflow_nexora_api_v1_ai_team_workflows_post(self, *, json: Any = None) -> Any:
        """Create Ai Team Workflow"""
        return self.request("POST", "/nexora-api/v1/ai-team-workflows", json=json)

    def create_ai_tool_nexora_api_v1_ai_tools_post(self, *, json: Any = None) -> Any:
        """Create Ai Tool"""
        return self.request("POST", "/nexora-api/v1/ai-tools", json=json)

    def create_article_nexora_api_v1_docs_articles_post(self, *, json: Any = None) -> Any:
        """Create Article"""
        return self.request("POST", "/nexora-api/v1/docs/articles", json=json)

    def create_asset_nexora_api_v1_demo_assets_post(self, *, json: Any = None) -> Any:
        """Create Asset"""
        return self.request("POST", "/nexora-api/v1/demo-assets", json=json)

    def create_backup_nexora_api_v1_ga_backups_post(self, *, json: Any = None) -> Any:
        """Create Backup"""
        return self.request("POST", "/nexora-api/v1/ga/backups", json=json)

    def create_change_request_nexora_api_v1_change_requests_post(self, *, json: Any = None) -> Any:
        """Create Change Request"""
        return self.request("POST", "/nexora-api/v1/change-requests", json=json)

    def create_communication_nexora_api_v1_incidents_communications_post(self, *, json: Any = None) -> Any:
        """Create Communication"""
        return self.request("POST", "/nexora-api/v1/incidents/communications", json=json)

    def create_communication_template_nexora_api_v1_incidents_communications_templates_post(self, *, json: Any = None) -> Any:
        """Create Communication Template"""
        return self.request("POST", "/nexora-api/v1/incidents/communications/templates", json=json)

    def create_connection_nexora_api_v1_auth_sso_connections_post(self, *, json: Any = None) -> Any:
        """Create Connection"""
        return self.request("POST", "/nexora-api/v1/auth/sso/connections", json=json)

    def create_credential_nexora_api_v1_credentials_post(self, *, json: Any = None) -> Any:
        """Create Credential"""
        return self.request("POST", "/nexora-api/v1/credentials", json=json)

    def create_customer_approval_nexora_api_v1_pilot_approvals_post(self, *, json: Any = None) -> Any:
        """Create Customer Approval"""
        return self.request("POST", "/nexora-api/v1/pilot/approvals", json=json)

    def create_dashboard_nexora_api_v1_product_dashboards_post(self, *, json: Any = None) -> Any:
        """Create Dashboard"""
        return self.request("POST", "/nexora-api/v1/product/dashboards", json=json)

    def create_demo_organization_nexora_api_v1_demo_organizations_post(self, *, json: Any = None) -> Any:
        """Create Demo Organization"""
        return self.request("POST", "/nexora-api/v1/demo-organizations", json=json)

    def create_dependency_nexora_api_v1_service_dependencies_post(self, *, json: Any = None) -> Any:
        """Create Dependency"""
        return self.request("POST", "/nexora-api/v1/service-dependencies", json=json)

    def create_environment_nexora_api_v1_platform_engineering_environments_post(self, *, json: Any = None) -> Any:
        """Create Environment"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/environments", json=json)

    def create_forecast_nexora_api_v1_capacity_forecasts_post(self, *, json: Any = None) -> Any:
        """Create Forecast"""
        return self.request("POST", "/nexora-api/v1/capacity/forecasts", json=json)

    def create_freeze_window_nexora_api_v1_delivery_freeze_windows_post(self, *, json: Any = None) -> Any:
        """Create Freeze Window"""
        return self.request("POST", "/nexora-api/v1/delivery/freeze-windows", json=json)

    def create_goal_nexora_api_v1_operator_goals_post(self, *, json: Any = None) -> Any:
        """Create Goal"""
        return self.request("POST", "/nexora-api/v1/operator/goals", json=json)

    def create_golden_template_nexora_api_v1_platform_engineering_golden_templates_post(self, *, json: Any = None) -> Any:
        """Create Golden Template"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/golden-templates", json=json)

    def create_group_nexora_api_v1_scim_v2_groups_post(self) -> Any:
        """Create Group"""
        return self.request("POST", "/nexora-api/v1/scim/v2/Groups")

    def create_incident_task_nexora_api_v1_incidents_investigation_id_tasks_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Create Incident Task"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/tasks".format(investigation_id=investigation_id), json=json)

    def create_integration_nexora_api_v1_observability_integrations_post(self, *, json: Any = None) -> Any:
        """Create Integration"""
        return self.request("POST", "/nexora-api/v1/observability/integrations", json=json)

    def create_investigation_nexora_api_v1_security_investigations_post(self, *, json: Any = None) -> Any:
        """Create Investigation"""
        return self.request("POST", "/nexora-api/v1/security/investigations", json=json)

    def create_invitation_nexora_api_v1_invitations_post(self, *, json: Any = None) -> Any:
        """Create Invitation"""
        return self.request("POST", "/nexora-api/v1/invitations", json=json)

    def create_maintenance_nexora_api_v1_ops_workspace_maintenance_post(self, *, json: Any = None) -> Any:
        """Create Maintenance"""
        return self.request("POST", "/nexora-api/v1/ops-workspace/maintenance", json=json)

    def create_org_key_nexora_api_v1_api_keys_organization_post(self, *, json: Any = None) -> Any:
        """Create Org Key"""
        return self.request("POST", "/nexora-api/v1/api-keys/organization", json=json)

    def create_organization_nexora_api_v1_organizations_post(self, *, json: Any = None) -> Any:
        """Create Organization"""
        return self.request("POST", "/nexora-api/v1/organizations", json=json)

    def create_personal_key_nexora_api_v1_api_keys_personal_post(self, *, json: Any = None) -> Any:
        """Create Personal Key"""
        return self.request("POST", "/nexora-api/v1/api-keys/personal", json=json)

    def create_plan_nexora_api_v1_billing_admin_plans_post(self, *, json: Any = None) -> Any:
        """Create Plan"""
        return self.request("POST", "/nexora-api/v1/billing/admin/plans", json=json)

    def create_playbook_nexora_api_v1_test_playbooks_post(self, *, json: Any = None) -> Any:
        """Create Playbook"""
        return self.request("POST", "/nexora-api/v1/test-playbooks", json=json)

    def create_policy_nexora_api_v1_oncall_escalation_policies_post(self, *, json: Any = None) -> Any:
        """Create Policy"""
        return self.request("POST", "/nexora-api/v1/oncall/escalation-policies", json=json)

    def create_policy_nexora_api_v1_operator_policies_post(self, *, json: Any = None) -> Any:
        """Create Policy"""
        return self.request("POST", "/nexora-api/v1/operator/policies", json=json)

    def create_project_nexora_api_v1_projects_post(self, *, json: Any = None) -> Any:
        """Create Project"""
        return self.request("POST", "/nexora-api/v1/projects", json=json)

    def create_promotion_policy_nexora_api_v1_delivery_promotion_policies_post(self, *, json: Any = None) -> Any:
        """Create Promotion Policy"""
        return self.request("POST", "/nexora-api/v1/delivery/promotion-policies", json=json)

    def create_prompt_nexora_api_v1_ai_prompts_post(self, *, json: Any = None) -> Any:
        """Create Prompt"""
        return self.request("POST", "/nexora-api/v1/ai/prompts", json=json)

    def create_provider_nexora_api_v1_security_providers_post(self, *, json: Any = None) -> Any:
        """Create Provider"""
        return self.request("POST", "/nexora-api/v1/security/providers", json=json)

    def create_release_nexora_api_v1_delivery_releases_post(self, *, json: Any = None) -> Any:
        """Create Release"""
        return self.request("POST", "/nexora-api/v1/delivery/releases", json=json)

    def create_release_nexora_api_v1_releases_post(self, *, json: Any = None) -> Any:
        """Create Release"""
        return self.request("POST", "/nexora-api/v1/releases", json=json)

    def create_release_reliability_nexora_api_v1_delivery_release_reliability_post(self, *, json: Any = None) -> Any:
        """Create Release Reliability"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability", json=json)

    def create_remediation_workflow_nexora_api_v1_sre_remediation_workflows_post(self, *, json: Any = None) -> Any:
        """Create Remediation Workflow"""
        return self.request("POST", "/nexora-api/v1/sre/remediation/workflows", json=json)

    def create_report_schedule_nexora_api_v1_product_reports_schedules_post(self, *, json: Any = None) -> Any:
        """Create Report Schedule"""
        return self.request("POST", "/nexora-api/v1/product/reports/schedules", json=json)

    def create_repository_nexora_api_v1_platform_engineering_repositories_post(self, *, json: Any = None) -> Any:
        """Create Repository"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/repositories", json=json)

    def create_rule_nexora_api_v1_workflows_workflow_id_rules_post(self, workflow_id: str, *, json: Any = None) -> Any:
        """Create Rule"""
        return self.request("POST", "/nexora-api/v1/workflows/{workflow_id}/rules".format(workflow_id=workflow_id), json=json)

    def create_saved_search_nexora_api_v1_observability_logs_saved_searches_post(self, *, json: Any = None) -> Any:
        """Create Saved Search"""
        return self.request("POST", "/nexora-api/v1/observability/logs/saved-searches", json=json)

    def create_saved_view_nexora_api_v1_product_views_post(self, *, json: Any = None) -> Any:
        """Create Saved View"""
        return self.request("POST", "/nexora-api/v1/product/views", json=json)

    def create_schedule_nexora_api_v1_oncall_schedules_post(self, *, json: Any = None) -> Any:
        """Create Schedule"""
        return self.request("POST", "/nexora-api/v1/oncall/schedules", json=json)

    def create_schedule_override_nexora_api_v1_incidents_oncall_overrides_post(self, *, json: Any = None) -> Any:
        """Create Schedule Override"""
        return self.request("POST", "/nexora-api/v1/incidents/oncall/overrides", json=json)

    def create_scim_token_nexora_api_v1_scim_v2_admin_tokens_post(self, *, json: Any = None) -> Any:
        """Create Scim Token"""
        return self.request("POST", "/nexora-api/v1/scim/v2/admin/tokens", json=json)

    def create_secret_ref_nexora_api_v1_platform_engineering_secrets_post(self, *, json: Any = None) -> Any:
        """Create Secret Ref"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/secrets", json=json)

    def create_service_account_nexora_api_v1_service_accounts_post(self, *, json: Any = None) -> Any:
        """Create Service Account"""
        return self.request("POST", "/nexora-api/v1/service-accounts", json=json)

    def create_service_nexora_api_v1_services_post(self, *, json: Any = None) -> Any:
        """Create Service"""
        return self.request("POST", "/nexora-api/v1/services", json=json)

    def create_service_owner_nexora_api_v1_oncall_service_owners_post(self, *, json: Any = None) -> Any:
        """Create Service Owner"""
        return self.request("POST", "/nexora-api/v1/oncall/service-owners", json=json)

    def create_session_nexora_api_v1_onboarding_integrations_sessions_post(self, *, json: Any = None) -> Any:
        """Create Session"""
        return self.request("POST", "/nexora-api/v1/onboarding/integrations/sessions", json=json)

    def create_slo_nexora_api_v1_services_service_id_slos_post(self, service_id: str, *, json: Any = None) -> Any:
        """Create Slo"""
        return self.request("POST", "/nexora-api/v1/services/{service_id}/slos".format(service_id=service_id), json=json)

    def create_stack_nexora_api_v1_platform_engineering_stacks_post(self, *, json: Any = None) -> Any:
        """Create Stack"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/stacks", json=json)

    def create_stage_nexora_api_v1_workflows_workflow_id_stages_post(self, workflow_id: str, *, json: Any = None) -> Any:
        """Create Stage"""
        return self.request("POST", "/nexora-api/v1/workflows/{workflow_id}/stages".format(workflow_id=workflow_id), json=json)

    def create_status_page_nexora_api_v1_incidents_status_pages_post(self, *, json: Any = None) -> Any:
        """Create Status Page"""
        return self.request("POST", "/nexora-api/v1/incidents/status-pages", json=json)

    def create_team_nexora_api_v1_teams_post(self, *, json: Any = None) -> Any:
        """Create Team"""
        return self.request("POST", "/nexora-api/v1/teams", json=json)

    def create_team_responsibility_nexora_api_v1_teams_team_id_responsibilities_post(self, team_id: str, *, json: Any = None) -> Any:
        """Create Team Responsibility"""
        return self.request("POST", "/nexora-api/v1/teams/{team_id}/responsibilities".format(team_id=team_id), json=json)

    def create_user_nexora_api_v1_scim_v2_users_post(self) -> Any:
        """Create User"""
        return self.request("POST", "/nexora-api/v1/scim/v2/Users")

    def create_variable_nexora_api_v1_org_config_variables_post(self, *, json: Any = None) -> Any:
        """Create Variable"""
        return self.request("POST", "/nexora-api/v1/org-config/variables", json=json)

    def create_war_room_nexora_api_v1_war_rooms_post(self, *, json: Any = None) -> Any:
        """Create War Room"""
        return self.request("POST", "/nexora-api/v1/war-rooms", json=json)

    def create_webhook_nexora_api_v1_billing_webhooks_post(self, *, json: Any = None) -> Any:
        """Create Webhook"""
        return self.request("POST", "/nexora-api/v1/billing/webhooks", json=json)

    def create_workflow_nexora_api_v1_workflows_post(self, *, json: Any = None) -> Any:
        """Create Workflow"""
        return self.request("POST", "/nexora-api/v1/workflows", json=json)

    def create_workflow_schedule_nexora_api_v1_ai_team_workflow_schedules_post(self, *, json: Any = None) -> Any:
        """Create Workflow Schedule"""
        return self.request("POST", "/nexora-api/v1/ai-team-workflow-schedules", json=json)

    def create_workspace_nexora_api_v1_workspaces_post(self, *, json: Any = None) -> Any:
        """Create Workspace"""
        return self.request("POST", "/nexora-api/v1/workspaces", json=json)

    def credential_status_nexora_api_v1_credentials_credential_id_status_get(self, credential_id: str) -> Any:
        """Credential Status"""
        return self.request("GET", "/nexora-api/v1/credentials/{credential_id}/status".format(credential_id=credential_id))

    def current_oncall_nexora_api_v1_oncall_current_get(self) -> Any:
        """Current Oncall"""
        return self.request("GET", "/nexora-api/v1/oncall/current")

    def customer_success_nexora_api_v1_ga_success_get(self) -> Any:
        """Customer Success"""
        return self.request("GET", "/nexora-api/v1/ga/success")

    def dashboard_nexora_api_v1_architecture_dashboard_get(self) -> Any:
        """Dashboard"""
        return self.request("GET", "/nexora-api/v1/architecture/dashboard")

    def dashboard_nexora_api_v1_delivery_dashboard_get(self) -> Any:
        """Dashboard"""
        return self.request("GET", "/nexora-api/v1/delivery/dashboard")

    def dashboard_nexora_api_v1_observability_dashboard_get(self) -> Any:
        """Dashboard"""
        return self.request("GET", "/nexora-api/v1/observability/dashboard")

    def dashboard_nexora_api_v1_operator_dashboard_get(self) -> Any:
        """Dashboard"""
        return self.request("GET", "/nexora-api/v1/operator/dashboard")

    def dashboard_nexora_api_v1_platform_engineering_dashboard_get(self) -> Any:
        """Dashboard"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/dashboard")

    def dashboard_nexora_api_v1_reliability_dashboard_get(self) -> Any:
        """Dashboard"""
        return self.request("GET", "/nexora-api/v1/reliability/dashboard")

    def decide_approval_nexora_api_v1_customer_pilot_operation_operation_id_approval_decide_post(self, operation_id: str, *, json: Any = None) -> Any:
        """Decide Approval"""
        return self.request("POST", "/nexora-api/v1/customer-pilot/operation/{operation_id}/approval/decide".format(operation_id=operation_id), json=json)

    def decide_catalog_request_nexora_api_v1_platform_engineering_catalog_requests_request_id_decide_post(self, request_id: str, *, params: dict | None = None) -> Any:
        """Decide Catalog Request"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/catalog/requests/{request_id}/decide".format(request_id=request_id), params=params)

    def decide_change_request_nexora_api_v1_change_requests_run_id_decide_post(self, run_id: str, *, json: Any = None) -> Any:
        """Decide Change Request"""
        return self.request("POST", "/nexora-api/v1/change-requests/{run_id}/decide".format(run_id=run_id), json=json)

    def decide_customer_approval_nexora_api_v1_pilot_approvals_approval_id_decide_post(self, approval_id: str, *, json: Any = None) -> Any:
        """Decide Customer Approval"""
        return self.request("POST", "/nexora-api/v1/pilot/approvals/{approval_id}/decide".format(approval_id=approval_id), json=json)

    def decide_environment_nexora_api_v1_platform_engineering_environments_environment_id_decide_post(self, environment_id: str, *, params: dict | None = None) -> Any:
        """Decide Environment"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/environments/{environment_id}/decide".format(environment_id=environment_id), params=params)

    def decide_k8s_operation_nexora_api_v1_control_plane_clusters_cluster_id_k8s_operations_operation_id_decide_post(self, cluster_id: str, operation_id: str, *, json: Any = None) -> Any:
        """Decide K8S Operation"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/operations/{operation_id}/decide".format(cluster_id=cluster_id, operation_id=operation_id), json=json)

    def decide_maintenance_nexora_api_v1_ops_workspace_maintenance_window_id_decide_post(self, window_id: str, *, params: dict | None = None) -> Any:
        """Decide Maintenance"""
        return self.request("POST", "/nexora-api/v1/ops-workspace/maintenance/{window_id}/decide".format(window_id=window_id), params=params)

    def decide_operation_nexora_api_v1_control_plane_operations_operation_id_decide_post(self, operation_id: str, *, json: Any = None) -> Any:
        """Decide Operation"""
        return self.request("POST", "/nexora-api/v1/control-plane/operations/{operation_id}/decide".format(operation_id=operation_id), json=json)

    def decide_operation_nexora_api_v1_delivery_operations_operation_id_decide_post(self, operation_id: str, *, json: Any = None) -> Any:
        """Decide Operation"""
        return self.request("POST", "/nexora-api/v1/delivery/operations/{operation_id}/decide".format(operation_id=operation_id), json=json)

    def decide_proposal_nexora_api_v1_operator_proposals_proposal_id_decide_post(self, proposal_id: str, *, params: dict | None = None) -> Any:
        """Decide Proposal"""
        return self.request("POST", "/nexora-api/v1/operator/proposals/{proposal_id}/decide".format(proposal_id=proposal_id), params=params)

    def decide_provision_nexora_api_v1_platform_engineering_provisions_provision_id_decide_post(self, provision_id: str, *, params: dict | None = None) -> Any:
        """Decide Provision"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/provisions/{provision_id}/decide".format(provision_id=provision_id), params=params)

    def decide_remediation_nexora_api_v1_security_remediation_proposal_id_decide_post(self, proposal_id: str, *, params: dict | None = None) -> Any:
        """Decide Remediation"""
        return self.request("POST", "/nexora-api/v1/security/remediation/{proposal_id}/decide".format(proposal_id=proposal_id), params=params)

    def decide_run_nexora_api_v1_platform_engineering_runs_run_id_decide_post(self, run_id: str, *, params: dict | None = None) -> Any:
        """Decide Run"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/runs/{run_id}/decide".format(run_id=run_id), params=params)

    def delete_agent_input_nexora_api_v1_ai_agent_inputs_input_id_delete(self, input_id: str) -> Any:
        """Delete Agent Input"""
        return self.request("DELETE", "/nexora-api/v1/ai-agent-inputs/{input_id}".format(input_id=input_id))

    def delete_agent_output_nexora_api_v1_ai_agent_outputs_output_id_delete(self, output_id: str) -> Any:
        """Delete Agent Output"""
        return self.request("DELETE", "/nexora-api/v1/ai-agent-outputs/{output_id}".format(output_id=output_id))

    def delete_agent_responsibility_nexora_api_v1_ai_agent_responsibilities_responsibility_id_delete(self, responsibility_id: str) -> Any:
        """Delete Agent Responsibility"""
        return self.request("DELETE", "/nexora-api/v1/ai-agent-responsibilities/{responsibility_id}".format(responsibility_id=responsibility_id))

    def delete_ai_agent_nexora_api_v1_ai_agents_agent_id_delete(self, agent_id: str) -> Any:
        """Delete Ai Agent"""
        return self.request("DELETE", "/nexora-api/v1/ai-agents/{agent_id}".format(agent_id=agent_id))

    def delete_ai_team_agent_memory_nexora_api_v1_ai_team_agents_memory_memory_id_delete(self, memory_id: str) -> Any:
        """Delete Ai Team Agent Memory"""
        return self.request("DELETE", "/nexora-api/v1/ai-team-agents/memory/{memory_id}".format(memory_id=memory_id))

    def delete_ai_team_agent_nexora_api_v1_ai_team_agents_agent_id_delete(self, agent_id: str) -> Any:
        """Delete Ai Team Agent"""
        return self.request("DELETE", "/nexora-api/v1/ai-team-agents/{agent_id}".format(agent_id=agent_id))

    def delete_ai_team_document_nexora_api_v1_ai_teams_documents_document_id_delete(self, document_id: str) -> Any:
        """Delete Ai Team Document"""
        return self.request("DELETE", "/nexora-api/v1/ai-teams/documents/{document_id}".format(document_id=document_id))

    def delete_ai_team_nexora_api_v1_ai_teams_team_id_delete(self, team_id: str) -> Any:
        """Delete Ai Team"""
        return self.request("DELETE", "/nexora-api/v1/ai-teams/{team_id}".format(team_id=team_id))

    def delete_ai_team_workflow_nexora_api_v1_ai_team_workflows_workflow_id_delete(self, workflow_id: str) -> Any:
        """Delete Ai Team Workflow"""
        return self.request("DELETE", "/nexora-api/v1/ai-team-workflows/{workflow_id}".format(workflow_id=workflow_id))

    def delete_ai_tool_nexora_api_v1_ai_tools_tool_id_delete(self, tool_id: str) -> Any:
        """Delete Ai Tool"""
        return self.request("DELETE", "/nexora-api/v1/ai-tools/{tool_id}".format(tool_id=tool_id))

    def delete_article_nexora_api_v1_docs_articles_article_id_delete(self, article_id: str) -> Any:
        """Delete Article"""
        return self.request("DELETE", "/nexora-api/v1/docs/articles/{article_id}".format(article_id=article_id))

    def delete_asset_nexora_api_v1_demo_assets_asset_id_delete(self, asset_id: str) -> Any:
        """Delete Asset"""
        return self.request("DELETE", "/nexora-api/v1/demo-assets/{asset_id}".format(asset_id=asset_id))

    def delete_connection_nexora_api_v1_auth_sso_connections_connection_id_delete(self, connection_id: str) -> Any:
        """Delete Connection"""
        return self.request("DELETE", "/nexora-api/v1/auth/sso/connections/{connection_id}".format(connection_id=connection_id))

    def delete_credential_nexora_api_v1_credentials_credential_id_delete(self, credential_id: str) -> Any:
        """Delete Credential"""
        return self.request("DELETE", "/nexora-api/v1/credentials/{credential_id}".format(credential_id=credential_id))

    def delete_dashboard_nexora_api_v1_product_dashboards_dash_id_delete(self, dash_id: str) -> Any:
        """Delete Dashboard"""
        return self.request("DELETE", "/nexora-api/v1/product/dashboards/{dash_id}".format(dash_id=dash_id))

    def delete_demo_organization_nexora_api_v1_demo_organizations_organization_id_delete(self, organization_id: str) -> Any:
        """Delete Demo Organization"""
        return self.request("DELETE", "/nexora-api/v1/demo-organizations/{organization_id}".format(organization_id=organization_id))

    def delete_dependency_nexora_api_v1_service_dependencies_dependency_id_delete(self, dependency_id: str) -> Any:
        """Delete Dependency"""
        return self.request("DELETE", "/nexora-api/v1/service-dependencies/{dependency_id}".format(dependency_id=dependency_id))

    def delete_deployment_nexora_api_v1_deployments_deployment_id_delete(self, deployment_id: str) -> Any:
        """Delete Deployment"""
        return self.request("DELETE", "/nexora-api/v1/deployments/{deployment_id}".format(deployment_id=deployment_id))

    def delete_group_nexora_api_v1_scim_v2_groups_scim_id_delete(self, scim_id: str) -> Any:
        """Delete Group"""
        return self.request("DELETE", "/nexora-api/v1/scim/v2/Groups/{scim_id}".format(scim_id=scim_id))

    def delete_organization_nexora_api_v1_organizations_organization_id_delete(self, organization_id: str) -> Any:
        """Delete Organization"""
        return self.request("DELETE", "/nexora-api/v1/organizations/{organization_id}".format(organization_id=organization_id))

    def delete_playbook_nexora_api_v1_test_playbooks_playbook_id_delete(self, playbook_id: str) -> Any:
        """Delete Playbook"""
        return self.request("DELETE", "/nexora-api/v1/test-playbooks/{playbook_id}".format(playbook_id=playbook_id))

    def delete_policy_nexora_api_v1_oncall_escalation_policies_policy_id_delete(self, policy_id: str) -> Any:
        """Delete Policy"""
        return self.request("DELETE", "/nexora-api/v1/oncall/escalation-policies/{policy_id}".format(policy_id=policy_id))

    def delete_project_nexora_api_v1_projects_project_id_delete(self, project_id: str) -> Any:
        """Delete Project"""
        return self.request("DELETE", "/nexora-api/v1/projects/{project_id}".format(project_id=project_id))

    def delete_responsibility_nexora_api_v1_responsibilities_responsibility_id_delete(self, responsibility_id: str) -> Any:
        """Delete Responsibility"""
        return self.request("DELETE", "/nexora-api/v1/responsibilities/{responsibility_id}".format(responsibility_id=responsibility_id))

    def delete_saved_view_nexora_api_v1_product_views_view_id_delete(self, view_id: str) -> Any:
        """Delete Saved View"""
        return self.request("DELETE", "/nexora-api/v1/product/views/{view_id}".format(view_id=view_id))

    def delete_schedule_nexora_api_v1_oncall_schedules_schedule_id_delete(self, schedule_id: str) -> Any:
        """Delete Schedule"""
        return self.request("DELETE", "/nexora-api/v1/oncall/schedules/{schedule_id}".format(schedule_id=schedule_id))

    def delete_secret_ref_nexora_api_v1_platform_engineering_secrets_ref_id_delete(self, ref_id: str) -> Any:
        """Delete Secret Ref"""
        return self.request("DELETE", "/nexora-api/v1/platform-engineering/secrets/{ref_id}".format(ref_id=ref_id))

    def delete_service_nexora_api_v1_services_service_id_delete(self, service_id: str) -> Any:
        """Delete Service"""
        return self.request("DELETE", "/nexora-api/v1/services/{service_id}".format(service_id=service_id))

    def delete_service_owner_nexora_api_v1_oncall_service_owners_owner_id_delete(self, owner_id: str) -> Any:
        """Delete Service Owner"""
        return self.request("DELETE", "/nexora-api/v1/oncall/service-owners/{owner_id}".format(owner_id=owner_id))

    def delete_slo_nexora_api_v1_services_slos_slo_id_delete(self, slo_id: str) -> Any:
        """Delete Slo"""
        return self.request("DELETE", "/nexora-api/v1/services/slos/{slo_id}".format(slo_id=slo_id))

    def delete_stage_nexora_api_v1_stages_stage_id_delete(self, stage_id: str) -> Any:
        """Delete Stage"""
        return self.request("DELETE", "/nexora-api/v1/stages/{stage_id}".format(stage_id=stage_id))

    def delete_team_nexora_api_v1_teams_team_id_delete(self, team_id: str) -> Any:
        """Delete Team"""
        return self.request("DELETE", "/nexora-api/v1/teams/{team_id}".format(team_id=team_id))

    def delete_user_nexora_api_v1_scim_v2_users_scim_id_delete(self, scim_id: str) -> Any:
        """Delete User"""
        return self.request("DELETE", "/nexora-api/v1/scim/v2/Users/{scim_id}".format(scim_id=scim_id))

    def delete_variable_nexora_api_v1_org_config_variables_variable_id_delete(self, variable_id: str) -> Any:
        """Delete Variable"""
        return self.request("DELETE", "/nexora-api/v1/org-config/variables/{variable_id}".format(variable_id=variable_id))

    def delete_workflow_nexora_api_v1_workflows_workflow_id_delete(self, workflow_id: str) -> Any:
        """Delete Workflow"""
        return self.request("DELETE", "/nexora-api/v1/workflows/{workflow_id}".format(workflow_id=workflow_id))

    def delete_workflow_schedule_nexora_api_v1_ai_team_workflow_schedules_schedule_id_delete(self, schedule_id: str) -> Any:
        """Delete Workflow Schedule"""
        return self.request("DELETE", "/nexora-api/v1/ai-team-workflow-schedules/{schedule_id}".format(schedule_id=schedule_id))

    def delete_workspace_nexora_api_v1_workspaces_workspace_id_delete(self, workspace_id: str) -> Any:
        """Delete Workspace"""
        return self.request("DELETE", "/nexora-api/v1/workspaces/{workspace_id}".format(workspace_id=workspace_id))

    def demo_dashboard_nexora_api_v1_customer_success_demos_get(self) -> Any:
        """Demo Dashboard"""
        return self.request("GET", "/nexora-api/v1/customer-success/demos")

    def demo_launch_nexora_api_v1_customer_success_demos_scenarios_key_launch_post(self, key: str) -> Any:
        """Demo Launch"""
        return self.request("POST", "/nexora-api/v1/customer-success/demos/scenarios/{key}/launch".format(key=key))

    def demo_recordings_nexora_api_v1_sales_demo_recordings_get(self, *, params: dict | None = None) -> Any:
        """Demo Recordings"""
        return self.request("GET", "/nexora-api/v1/sales/demo-recordings", params=params)

    def demo_sales_mode_nexora_api_v1_customer_success_demos_scenarios_key_sales_mode_get(self, key: str) -> Any:
        """Demo Sales Mode"""
        return self.request("GET", "/nexora-api/v1/customer-success/demos/scenarios/{key}/sales-mode".format(key=key))

    def demo_scenario_nexora_api_v1_customer_success_demos_scenarios_key_get(self, key: str) -> Any:
        """Demo Scenario"""
        return self.request("GET", "/nexora-api/v1/customer-success/demos/scenarios/{key}".format(key=key))

    def demo_state_nexora_api_v1_customer_success_demos_scenarios_key_state_post(self, key: str, *, json: Any = None) -> Any:
        """Demo State"""
        return self.request("POST", "/nexora-api/v1/customer-success/demos/scenarios/{key}/state".format(key=key), json=json)

    def dependency_graph_nexora_api_v1_service_dependencies_graph_get(self) -> Any:
        """Dependency Graph"""
        return self.request("GET", "/nexora-api/v1/service-dependencies/graph")

    def deployment_safety_dashboard_nexora_api_v1_deployment_safety_dashboard_get(self) -> Any:
        """Deployment Safety Dashboard"""
        return self.request("GET", "/nexora-api/v1/deployment-safety/dashboard")

    def deregister_mcp_server_nexora_api_v1_ai_mcp_servers_server_id_delete(self, server_id: str) -> Any:
        """Deregister Mcp Server"""
        return self.request("DELETE", "/nexora-api/v1/ai/mcp/servers/{server_id}".format(server_id=server_id))

    def detach_ai_tool_credential_nexora_api_v1_ai_tools_tool_id_credentials_credential_id_delete(self, tool_id: str, credential_id: str) -> Any:
        """Detach Ai Tool Credential"""
        return self.request("DELETE", "/nexora-api/v1/ai-tools/{tool_id}/credentials/{credential_id}".format(tool_id=tool_id, credential_id=credential_id))

    def diagnostics_json_nexora_api_v1_ga_diagnostics_get(self) -> Any:
        """Diagnostics Json"""
        return self.request("GET", "/nexora-api/v1/ga/diagnostics")

    def diagnostics_zip_nexora_api_v1_ga_diagnostics_zip_get(self) -> Any:
        """Diagnostics Zip"""
        return self.request("GET", "/nexora-api/v1/ga/diagnostics/zip")

    def disable_mfa_nexora_api_v1_auth_mfa_disable_post(self) -> Any:
        """Disable Mfa"""
        return self.request("POST", "/nexora-api/v1/auth/mfa/disable")

    def disable_service_account_nexora_api_v1_service_accounts_sa_id_disable_post(self, sa_id: str) -> Any:
        """Disable Service Account"""
        return self.request("POST", "/nexora-api/v1/service-accounts/{sa_id}/disable".format(sa_id=sa_id))

    def disconnect_integration_nexora_api_v1_integrations_connections_connection_id_delete(self, connection_id: str) -> Any:
        """Disconnect Integration"""
        return self.request("DELETE", "/nexora-api/v1/integrations/connections/{connection_id}".format(connection_id=connection_id))

    def discover_cluster_nexora_api_v1_control_plane_clusters_cluster_id_discover_post(self, cluster_id: str) -> Any:
        """Discover Cluster"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/discover".format(cluster_id=cluster_id))

    def discover_metrics_nexora_api_v1_observability_metrics_discover_get(self, *, params: dict | None = None) -> Any:
        """Discover Metrics"""
        return self.request("GET", "/nexora-api/v1/observability/metrics/discover", params=params)

    def discover_nexora_api_v1_architecture_discover_post(self) -> Any:
        """Discover"""
        return self.request("POST", "/nexora-api/v1/architecture/discover")

    def discovery_assets_nexora_api_v1_discovery_assets_get(self, *, params: dict | None = None) -> Any:
        """Discovery Assets"""
        return self.request("GET", "/nexora-api/v1/discovery/assets", params=params)

    def discovery_context_nexora_api_v1_discovery_context_get(self, *, params: dict | None = None) -> Any:
        """Discovery Context"""
        return self.request("GET", "/nexora-api/v1/discovery/context", params=params)

    def discovery_events_nexora_api_v1_discovery_events_get(self, *, params: dict | None = None) -> Any:
        """Discovery Events"""
        return self.request("GET", "/nexora-api/v1/discovery/events", params=params)

    def discovery_graph_nexora_api_v1_discovery_graph_get(self) -> Any:
        """Discovery Graph"""
        return self.request("GET", "/nexora-api/v1/discovery/graph")

    def discovery_progress_nexora_api_v1_discovery_progress_get(self) -> Any:
        """Discovery Progress"""
        return self.request("GET", "/nexora-api/v1/discovery/progress")

    def discovery_summary_nexora_api_v1_discovery_summary_get(self) -> Any:
        """Discovery Summary"""
        return self.request("GET", "/nexora-api/v1/discovery/summary")

    def dismiss_automation_nexora_api_v1_ops_workspace_automation_suggestions_suggestion_id_dismiss_post(self, suggestion_id: str) -> Any:
        """Dismiss Automation"""
        return self.request("POST", "/nexora-api/v1/ops-workspace/automation-suggestions/{suggestion_id}/dismiss".format(suggestion_id=suggestion_id))

    def documentation_audit_guide_nexora_api_v1_customer_success_documentation_audit_guides_key_get(self, key: str) -> Any:
        """Documentation Audit Guide"""
        return self.request("GET", "/nexora-api/v1/customer-success/documentation-audit/guides/{key}".format(key=key))

    def documentation_audit_nexora_api_v1_customer_success_documentation_audit_get(self) -> Any:
        """Documentation Audit"""
        return self.request("GET", "/nexora-api/v1/customer-success/documentation-audit")

    def documentation_certification_dashboard_nexora_api_v1_customer_success_certification_dashboard_get(self) -> Any:
        """Documentation Certification Dashboard"""
        return self.request("GET", "/nexora-api/v1/customer-success/certification/dashboard")

    def documentation_certification_nexora_api_v1_customer_success_certification_get(self) -> Any:
        """Documentation Certification"""
        return self.request("GET", "/nexora-api/v1/customer-success/certification")

    def documentation_diagrams_nexora_api_v1_product_docs_diagrams_get(self) -> Any:
        """Documentation Diagrams"""
        return self.request("GET", "/nexora-api/v1/product/docs/diagrams")

    def dora_metrics_nexora_api_v1_delivery_dora_get(self, *, params: dict | None = None) -> Any:
        """Dora Metrics"""
        return self.request("GET", "/nexora-api/v1/delivery/dora", params=params)

    def draft_communication_nexora_api_v1_pilot_communications_draft_post(self, *, json: Any = None) -> Any:
        """Draft Communication"""
        return self.request("POST", "/nexora-api/v1/pilot/communications/draft", json=json)

    def drain_events_nexora_api_v1_platform_events_drain_post(self, *, params: dict | None = None) -> Any:
        """Drain Events"""
        return self.request("POST", "/nexora-api/v1/platform/events/drain", params=params)

    def drift_nexora_api_v1_customer_success_drift_get(self) -> Any:
        """Drift"""
        return self.request("GET", "/nexora-api/v1/customer-success/drift")

    def duplicate_ai_agent_nexora_api_v1_ai_agents_agent_id_duplicate_post(self, agent_id: str) -> Any:
        """Duplicate Ai Agent"""
        return self.request("POST", "/nexora-api/v1/ai-agents/{agent_id}/duplicate".format(agent_id=agent_id))

    def duplicate_team_nexora_api_v1_teams_team_id_duplicate_post(self, team_id: str) -> Any:
        """Duplicate Team"""
        return self.request("POST", "/nexora-api/v1/teams/{team_id}/duplicate".format(team_id=team_id))

    def duplicate_workflow_nexora_api_v1_workflows_workflow_id_duplicate_post(self, workflow_id: str) -> Any:
        """Duplicate Workflow"""
        return self.request("POST", "/nexora-api/v1/workflows/{workflow_id}/duplicate".format(workflow_id=workflow_id))

    def enable_live_operations_nexora_api_v1_pilot_live_operations_enable_post(self) -> Any:
        """Enable Live Operations"""
        return self.request("POST", "/nexora-api/v1/pilot/live-operations/enable")

    def end_major_incident_nexora_api_v1_incidents_major_major_id_end_post(self, major_id: str) -> Any:
        """End Major Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/major/{major_id}/end".format(major_id=major_id))

    def enroll_mfa_nexora_api_v1_auth_mfa_enroll_post(self) -> Any:
        """Enroll Mfa"""
        return self.request("POST", "/nexora-api/v1/auth/mfa/enroll")

    def error_budgets_nexora_api_v1_observability_error_budget_get(self) -> Any:
        """Error Budgets"""
        return self.request("GET", "/nexora-api/v1/observability/error-budget")

    def escalate_incident_nexora_api_v1_incidents_investigation_id_escalate_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Escalate Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/escalate".format(investigation_id=investigation_id), json=json)

    def escalation_dashboard_nexora_api_v1_incidents_escalation_get(self) -> Any:
        """Escalation Dashboard"""
        return self.request("GET", "/nexora-api/v1/incidents/escalation")

    def evaluate_sla_nexora_api_v1_security_sla_evaluate_post(self) -> Any:
        """Evaluate Sla"""
        return self.request("POST", "/nexora-api/v1/security/sla/evaluate")

    def evaluate_slos_nexora_api_v1_observability_slo_evaluate_post(self) -> Any:
        """Evaluate Slos"""
        return self.request("POST", "/nexora-api/v1/observability/slo/evaluate")

    def evaluation_summary_nexora_api_v1_ai_evaluations_summary_get(self, *, params: dict | None = None) -> Any:
        """Evaluation Summary"""
        return self.request("GET", "/nexora-api/v1/ai/evaluations/summary", params=params)

    def events_pending_nexora_api_v1_platform_events_pending_get(self) -> Any:
        """Events Pending"""
        return self.request("GET", "/nexora-api/v1/platform/events/pending")

    def execute_ai_team_agent_nexora_api_v1_ai_team_agents_agent_id_execute_post(self, agent_id: str, *, json: Any = None) -> Any:
        """Execute Ai Team Agent"""
        return self.request("POST", "/nexora-api/v1/ai-team-agents/{agent_id}/execute".format(agent_id=agent_id), json=json)

    def execute_ai_team_nexora_api_v1_ai_teams_team_id_execute_post(self, team_id: str, *, json: Any = None) -> Any:
        """Execute Ai Team"""
        return self.request("POST", "/nexora-api/v1/ai-teams/{team_id}/execute".format(team_id=team_id), json=json)

    def execute_ai_team_workflow_nexora_api_v1_ai_team_workflows_workflow_id_execute_post(self, workflow_id: str, *, json: Any = None) -> Any:
        """Execute Ai Team Workflow"""
        return self.request("POST", "/nexora-api/v1/ai-team-workflows/{workflow_id}/execute".format(workflow_id=workflow_id), json=json)

    def execute_ai_tool_nexora_api_v1_ai_tools_tool_id_execute_post(self, tool_id: str, *, json: Any = None) -> Any:
        """Execute Ai Tool"""
        return self.request("POST", "/nexora-api/v1/ai-tools/{tool_id}/execute".format(tool_id=tool_id), json=json)

    def execute_k8s_operation_nexora_api_v1_control_plane_clusters_cluster_id_k8s_operations_operation_id_execute_post(self, cluster_id: str, operation_id: str) -> Any:
        """Execute K8S Operation"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/operations/{operation_id}/execute".format(cluster_id=cluster_id, operation_id=operation_id))

    def execute_operation_nexora_api_v1_control_plane_operations_operation_id_execute_post(self, operation_id: str) -> Any:
        """Execute Operation"""
        return self.request("POST", "/nexora-api/v1/control-plane/operations/{operation_id}/execute".format(operation_id=operation_id))

    def execute_operation_nexora_api_v1_delivery_operations_operation_id_execute_post(self, operation_id: str) -> Any:
        """Execute Operation"""
        return self.request("POST", "/nexora-api/v1/delivery/operations/{operation_id}/execute".format(operation_id=operation_id))

    def execute_playbook_nexora_api_v1_test_playbooks_playbook_id_execute_post(self, playbook_id: str, *, json: Any = None) -> Any:
        """Execute Playbook"""
        return self.request("POST", "/nexora-api/v1/test-playbooks/{playbook_id}/execute".format(playbook_id=playbook_id), json=json)

    def execute_regeneration_nexora_api_v1_regeneration_post(self, *, json: Any = None) -> Any:
        """Execute Regeneration"""
        return self.request("POST", "/nexora-api/v1/regeneration", json=json)

    def execute_remediation_nexora_api_v1_security_remediation_proposal_id_execute_post(self, proposal_id: str) -> Any:
        """Execute Remediation"""
        return self.request("POST", "/nexora-api/v1/security/remediation/{proposal_id}/execute".format(proposal_id=proposal_id))

    def execute_runbook_nexora_api_v1_sre_runbooks_runbook_id_execute_post(self, runbook_id: str, *, json: Any = None) -> Any:
        """Execute Runbook"""
        return self.request("POST", "/nexora-api/v1/sre/runbooks/{runbook_id}/execute".format(runbook_id=runbook_id), json=json)

    def execute_scan_nexora_api_v1_security_scans_scan_id_execute_post(self, scan_id: str) -> Any:
        """Execute Scan"""
        return self.request("POST", "/nexora-api/v1/security/scans/{scan_id}/execute".format(scan_id=scan_id))

    def execute_tool_nexora_api_v1_ai_tools_name_execute_post(self, name: str, *, json: Any = None) -> Any:
        """Execute Tool"""
        return self.request("POST", "/nexora-api/v1/ai/tools/{name}/execute".format(name=name), json=json)

    def execute_war_room_nexora_api_v1_war_rooms_war_room_id_execute_post(self, war_room_id: str) -> Any:
        """Execute War Room"""
        return self.request("POST", "/nexora-api/v1/war-rooms/{war_room_id}/execute".format(war_room_id=war_room_id))

    def execute_workflow_nexora_api_v1_workflows_workflow_id_execute_post(self, workflow_id: str, *, json: Any = None) -> Any:
        """Execute Workflow"""
        return self.request("POST", "/nexora-api/v1/workflows/{workflow_id}/execute".format(workflow_id=workflow_id), json=json)

    def execution_analytics_nexora_api_v1_platform_executions_analytics_get(self) -> Any:
        """Execution Analytics"""
        return self.request("GET", "/nexora-api/v1/platform/executions/analytics")

    def executive_ai_report_nexora_api_v1_sre_reports_executive_post(self, *, json: Any = None) -> Any:
        """Executive Ai Report"""
        return self.request("POST", "/nexora-api/v1/sre/reports/executive", json=json)

    def executive_pdf_nexora_api_v1_ops_workspace_executive_export_pdf_get(self) -> Any:
        """Executive Pdf"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/executive/export/pdf")

    def executive_view_nexora_api_v1_ops_workspace_executive_get(self) -> Any:
        """Executive View"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/executive")

    def export_article_nexora_api_v1_docs_articles_article_id_export_get(self, article_id: str, *, params: dict | None = None) -> Any:
        """Export Article"""
        return self.request("GET", "/nexora-api/v1/docs/articles/{article_id}/export".format(article_id=article_id), params=params)

    def export_comparison_nexora_api_v1_sales_competitive_comparison_export_get(self, *, params: dict | None = None) -> Any:
        """Export Comparison"""
        return self.request("GET", "/nexora-api/v1/sales/competitive-comparison/export", params=params)

    def export_config_nexora_api_v1_ops_config_export_get(self) -> Any:
        """Export Config"""
        return self.request("GET", "/nexora-api/v1/ops/config/export")

    def export_dashboard_nexora_api_v1_reliability_dashboard_export_get(self, *, params: dict | None = None) -> Any:
        """Export Dashboard"""
        return self.request("GET", "/nexora-api/v1/reliability-dashboard/export", params=params)

    def export_evidence_nexora_api_v1_customer_pilot_operation_operation_id_evidence_export_get(self, operation_id: str) -> Any:
        """Export Evidence"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation/{operation_id}/evidence/export".format(operation_id=operation_id))

    def export_evidence_pack_nexora_api_v1_pilot_evidence_pack_export_get(self) -> Any:
        """Export Evidence Pack"""
        return self.request("GET", "/nexora-api/v1/pilot/evidence-pack/export")

    def export_human_guide_nexora_api_v1_customer_success_human_guides_key_export_get(self, key: str, *, params: dict | None = None) -> Any:
        """Export Human Guide"""
        return self.request("GET", "/nexora-api/v1/customer-success/human-guides/{key}/export".format(key=key), params=params)

    def export_logs_nexora_api_v1_audit_logs_export_get(self, *, params: dict | None = None) -> Any:
        """Export Logs"""
        return self.request("GET", "/nexora-api/v1/audit/logs/export", params=params)

    def export_manual_nexora_api_v1_docs_manual_get(self, *, params: dict | None = None) -> Any:
        """Export Manual"""
        return self.request("GET", "/nexora-api/v1/docs/manual", params=params)

    def export_pilot_report_nexora_api_v1_pilot_report_export_get(self) -> Any:
        """Export Pilot Report"""
        return self.request("GET", "/nexora-api/v1/pilot/report/export")

    def export_postmortem_nexora_api_v1_postmortems_postmortem_id_export_get(self, postmortem_id: str, *, params: dict | None = None) -> Any:
        """Export Postmortem"""
        return self.request("GET", "/nexora-api/v1/postmortems/{postmortem_id}/export".format(postmortem_id=postmortem_id), params=params)

    def export_proposal_nexora_api_v1_sales_proposal_export_post(self, *, params: dict | None = None, json: Any = None) -> Any:
        """Export Proposal"""
        return self.request("POST", "/nexora-api/v1/sales/proposal/export", params=params, json=json)

    def export_report_nexora_api_v1_executive_reports_report_id_export_get(self, report_id: str, *, params: dict | None = None) -> Any:
        """Export Report"""
        return self.request("GET", "/nexora-api/v1/executive-reports/{report_id}/export".format(report_id=report_id), params=params)

    def export_run_nexora_api_v1_test_playbooks_runs_run_id_export_get(self, run_id: str, *, params: dict | None = None) -> Any:
        """Export Run"""
        return self.request("GET", "/nexora-api/v1/test-playbooks/runs/{run_id}/export".format(run_id=run_id), params=params)

    def export_success_playbook_nexora_api_v1_customer_success_success_playbooks_key_export_get(self, key: str, *, params: dict | None = None) -> Any:
        """Export Success Playbook"""
        return self.request("GET", "/nexora-api/v1/customer-success/success-playbooks/{key}/export".format(key=key), params=params)

    def export_support_diagnostics_nexora_api_v1_pilot_support_diagnostics_export_get(self) -> Any:
        """Export Support Diagnostics"""
        return self.request("GET", "/nexora-api/v1/pilot/support/diagnostics/export")

    def export_timeline_nexora_api_v1_customer_pilot_timeline_export_get(self, *, params: dict | None = None) -> Any:
        """Export Timeline"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/timeline/export", params=params)

    def export_value_proposition_nexora_api_v1_sales_value_proposition_export_post(self, *, params: dict | None = None, json: Any = None) -> Any:
        """Export Value Proposition"""
        return self.request("POST", "/nexora-api/v1/sales/value-proposition/export", params=params, json=json)

    def export_video_nexora_api_v1_customer_success_videos_video_id_export_get(self, video_id: str, *, params: dict | None = None) -> Any:
        """Export Video"""
        return self.request("GET", "/nexora-api/v1/customer-success/videos/{video_id}/export".format(video_id=video_id), params=params)

    def export_visual_docs_nexora_api_v1_customer_success_export_get(self, *, params: dict | None = None) -> Any:
        """Export Visual Docs"""
        return self.request("GET", "/nexora-api/v1/customer-success/export", params=params)

    def feature_flags_nexora_api_v1_billing_feature_flags_get(self) -> Any:
        """Feature Flags"""
        return self.request("GET", "/nexora-api/v1/billing/feature-flags")

    def featured_videos_nexora_api_v1_customer_success_videos_featured_get(self) -> Any:
        """Featured Videos"""
        return self.request("GET", "/nexora-api/v1/customer-success/videos/featured")

    def gallery_nexora_api_v1_customer_success_gallery_get(self, *, params: dict | None = None) -> Any:
        """Gallery"""
        return self.request("GET", "/nexora-api/v1/customer-success/gallery", params=params)

    def generate_compliance_report_nexora_api_v1_ga_compliance_reports_post(self, *, json: Any = None) -> Any:
        """Generate Compliance Report"""
        return self.request("POST", "/nexora-api/v1/ga/compliance/reports", json=json)

    def generate_daily_briefing_nexora_api_v1_ops_workspace_briefing_daily_post(self) -> Any:
        """Generate Daily Briefing"""
        return self.request("POST", "/nexora-api/v1/ops-workspace/briefing/daily")

    def generate_documentation_nexora_api_v1_docs_generate_post(self) -> Any:
        """Generate Documentation"""
        return self.request("POST", "/nexora-api/v1/docs/generate")

    def generate_executive_briefing_nexora_api_v1_operator_executive_briefing_post(self) -> Any:
        """Generate Executive Briefing"""
        return self.request("POST", "/nexora-api/v1/operator/executive/briefing")

    def generate_handover_nexora_api_v1_ops_workspace_handover_post(self) -> Any:
        """Generate Handover"""
        return self.request("POST", "/nexora-api/v1/ops-workspace/handover")

    def generate_postmortem_nexora_api_v1_incidents_investigation_id_generate_postmortem_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Generate Postmortem"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/generate-postmortem".format(investigation_id=investigation_id), json=json)

    def generate_postmortem_nexora_api_v1_incidents_postmortems_incident_id_generate_post(self, incident_id: str) -> Any:
        """Generate Postmortem"""
        return self.request("POST", "/nexora-api/v1/incidents/postmortems/{incident_id}/generate".format(incident_id=incident_id))

    def generate_report_nexora_api_v1_executive_reports_generate_post(self, *, json: Any = None) -> Any:
        """Generate Report"""
        return self.request("POST", "/nexora-api/v1/executive-reports/generate", json=json)

    def generate_runbook_nexora_api_v1_runbooks_generate_post(self, *, json: Any = None) -> Any:
        """Generate Runbook"""
        return self.request("POST", "/nexora-api/v1/runbooks/generate", json=json)

    def generate_sample_incident_nexora_api_v1_onboarding_session_id_sample_incident_post(self, session_id: str) -> Any:
        """Generate Sample Incident"""
        return self.request("POST", "/nexora-api/v1/onboarding/{session_id}/sample-incident".format(session_id=session_id))

    def generate_screenshot_assets_nexora_api_v1_customer_success_screenshot_assets_generate_post(self) -> Any:
        """Generate Screenshot Assets"""
        return self.request("POST", "/nexora-api/v1/customer-success/screenshot-assets/generate")

    def get_agent_run_nexora_api_v1_agents_runs_run_id_get(self, run_id: str) -> Any:
        """Get Agent Run"""
        return self.request("GET", "/nexora-api/v1/agents/runs/{run_id}".format(run_id=run_id))

    def get_agent_run_nexora_api_v1_ai_agents_run_id_get(self, run_id: str) -> Any:
        """Get Agent Run"""
        return self.request("GET", "/nexora-api/v1/ai/agents/{run_id}".format(run_id=run_id))

    def get_ai_agent_nexora_api_v1_ai_agents_agent_id_get(self, agent_id: str) -> Any:
        """Get Ai Agent"""
        return self.request("GET", "/nexora-api/v1/ai-agents/{agent_id}".format(agent_id=agent_id))

    def get_ai_agent_template_nexora_api_v1_ai_agent_templates_slug_get(self, slug: str) -> Any:
        """Get Ai Agent Template"""
        return self.request("GET", "/nexora-api/v1/ai-agent-templates/{slug}".format(slug=slug))

    def get_ai_team_agent_nexora_api_v1_ai_team_agents_agent_id_get(self, agent_id: str) -> Any:
        """Get Ai Team Agent"""
        return self.request("GET", "/nexora-api/v1/ai-team-agents/{agent_id}".format(agent_id=agent_id))

    def get_ai_team_nexora_api_v1_ai_teams_team_id_get(self, team_id: str) -> Any:
        """Get Ai Team"""
        return self.request("GET", "/nexora-api/v1/ai-teams/{team_id}".format(team_id=team_id))

    def get_ai_team_run_nexora_api_v1_ai_teams_runs_run_id_get(self, run_id: str) -> Any:
        """Get Ai Team Run"""
        return self.request("GET", "/nexora-api/v1/ai-teams/runs/{run_id}".format(run_id=run_id))

    def get_ai_team_workflow_nexora_api_v1_ai_team_workflows_workflow_id_get(self, workflow_id: str) -> Any:
        """Get Ai Team Workflow"""
        return self.request("GET", "/nexora-api/v1/ai-team-workflows/{workflow_id}".format(workflow_id=workflow_id))

    def get_ai_tool_nexora_api_v1_ai_tools_tool_id_get(self, tool_id: str) -> Any:
        """Get Ai Tool"""
        return self.request("GET", "/nexora-api/v1/ai-tools/{tool_id}".format(tool_id=tool_id))

    def get_alert_nexora_api_v1_monitoring_alerts_alert_id_get(self, alert_id: str) -> Any:
        """Get Alert"""
        return self.request("GET", "/nexora-api/v1/monitoring/alerts/{alert_id}".format(alert_id=alert_id))

    def get_analysis_nexora_api_v1_cost_optimization_analyses_analysis_id_get(self, analysis_id: str) -> Any:
        """Get Analysis"""
        return self.request("GET", "/nexora-api/v1/cost-optimization/analyses/{analysis_id}".format(analysis_id=analysis_id))

    def get_approval_artifact_nexora_api_v1_agents_approval_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Approval Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/approval/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_approval_package_nexora_api_v1_customer_pilot_operation_operation_id_approval_package_get(self, operation_id: str) -> Any:
        """Get Approval Package"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation/{operation_id}/approval-package".format(operation_id=operation_id))

    def get_approval_run_nexora_api_v1_agents_approval_runs_run_id_get(self, run_id: str) -> Any:
        """Get Approval Run"""
        return self.request("GET", "/nexora-api/v1/agents/approval/runs/{run_id}".format(run_id=run_id))

    def get_architecture_nexora_api_v1_customer_success_architecture_key_get(self, key: str) -> Any:
        """Get Architecture"""
        return self.request("GET", "/nexora-api/v1/customer-success/architecture/{key}".format(key=key))

    def get_article_nexora_api_v1_docs_articles_article_id_get(self, article_id: str, *, params: dict | None = None) -> Any:
        """Get Article"""
        return self.request("GET", "/nexora-api/v1/docs/articles/{article_id}".format(article_id=article_id), params=params)

    def get_assessment_nexora_api_v1_pilot_assessment_get(self) -> Any:
        """Get Assessment"""
        return self.request("GET", "/nexora-api/v1/pilot/assessment")

    def get_assessment_nexora_api_v1_reliability_assessment_id_get(self, assessment_id: str) -> Any:
        """Get Assessment"""
        return self.request("GET", "/nexora-api/v1/reliability/{assessment_id}".format(assessment_id=assessment_id))

    def get_asset_nexora_api_v1_demo_assets_asset_id_get(self, asset_id: str) -> Any:
        """Get Asset"""
        return self.request("GET", "/nexora-api/v1/demo-assets/{asset_id}".format(asset_id=asset_id))

    def get_assignment_nexora_api_v1_oncall_incidents_incident_id_assignment_get(self, incident_id: str) -> Any:
        """Get Assignment"""
        return self.request("GET", "/nexora-api/v1/oncall/incidents/{incident_id}/assignment".format(incident_id=incident_id))

    def get_backend_architect_artifact_nexora_api_v1_agents_backend_architect_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Backend Architect Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/backend-architect/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_backend_architect_run_nexora_api_v1_agents_backend_architect_runs_run_id_get(self, run_id: str) -> Any:
        """Get Backend Architect Run"""
        return self.request("GET", "/nexora-api/v1/agents/backend-architect/runs/{run_id}".format(run_id=run_id))

    def get_backend_code_review_artifact_nexora_api_v1_agents_backend_code_review_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Backend Code Review Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/backend-code-review/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_backend_code_review_run_nexora_api_v1_agents_backend_code_review_runs_run_id_get(self, run_id: str) -> Any:
        """Get Backend Code Review Run"""
        return self.request("GET", "/nexora-api/v1/agents/backend-code-review/runs/{run_id}".format(run_id=run_id))

    def get_backend_execution_artifact_nexora_api_v1_agents_backend_execution_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Backend Execution Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/backend-execution/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_backend_execution_run_nexora_api_v1_agents_backend_execution_runs_run_id_get(self, run_id: str) -> Any:
        """Get Backend Execution Run"""
        return self.request("GET", "/nexora-api/v1/agents/backend-execution/runs/{run_id}".format(run_id=run_id))

    def get_backend_v1_artifact_nexora_api_v1_agents_backend_v1_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Backend V1 Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v1/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_backend_v1_run_nexora_api_v1_agents_backend_v1_runs_run_id_get(self, run_id: str) -> Any:
        """Get Backend V1 Run"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v1/runs/{run_id}".format(run_id=run_id))

    def get_backend_v2_artifact_nexora_api_v1_agents_backend_v2_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Backend V2 Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v2/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_backend_v2_run_nexora_api_v1_agents_backend_v2_runs_run_id_get(self, run_id: str) -> Any:
        """Get Backend V2 Run"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v2/runs/{run_id}".format(run_id=run_id))

    def get_backend_v3_artifact_nexora_api_v1_agents_backend_v3_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Backend V3 Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v3/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_backend_v3_run_nexora_api_v1_agents_backend_v3_runs_run_id_get(self, run_id: str) -> Any:
        """Get Backend V3 Run"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v3/runs/{run_id}".format(run_id=run_id))

    def get_business_analyst_artifact_nexora_api_v1_agents_business_analyst_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Business Analyst Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/business-analyst/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_business_analyst_run_nexora_api_v1_agents_business_analyst_runs_run_id_get(self, run_id: str) -> Any:
        """Get Business Analyst Run"""
        return self.request("GET", "/nexora-api/v1/agents/business-analyst/runs/{run_id}".format(run_id=run_id))

    def get_change_failure_nexora_api_v1_change_failure_prediction_prediction_id_get(self, prediction_id: str) -> Any:
        """Get Change Failure"""
        return self.request("GET", "/nexora-api/v1/change-failure-prediction/{prediction_id}".format(prediction_id=prediction_id))

    def get_change_request_nexora_api_v1_change_requests_run_id_get(self, run_id: str) -> Any:
        """Get Change Request"""
        return self.request("GET", "/nexora-api/v1/change-requests/{run_id}".format(run_id=run_id))

    def get_cicd_artifact_nexora_api_v1_agents_cicd_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Cicd Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/cicd/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_cicd_run_nexora_api_v1_agents_cicd_runs_run_id_get(self, run_id: str) -> Any:
        """Get Cicd Run"""
        return self.request("GET", "/nexora-api/v1/agents/cicd/runs/{run_id}".format(run_id=run_id))

    def get_closeout_nexora_api_v1_customer_pilot_closeout_get(self) -> Any:
        """Get Closeout"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/closeout")

    def get_cluster_nexora_api_v1_control_plane_clusters_cluster_id_get(self, cluster_id: str) -> Any:
        """Get Cluster"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}".format(cluster_id=cluster_id))

    def get_commander_nexora_api_v1_sre_commander_commander_id_get(self, commander_id: str) -> Any:
        """Get Commander"""
        return self.request("GET", "/nexora-api/v1/sre/commander/{commander_id}".format(commander_id=commander_id))

    def get_communication_nexora_api_v1_customer_pilot_communications_communication_id_get(self, communication_id: str) -> Any:
        """Get Communication"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/communications/{communication_id}".format(communication_id=communication_id))

    def get_config_nexora_api_v1_platform_config_key_get(self, key: str) -> Any:
        """Get Config"""
        return self.request("GET", "/nexora-api/v1/platform/config/{key}".format(key=key))

    def get_connection_capabilities_nexora_api_v1_integrations_connections_connection_id_capabilities_get(self, connection_id: str) -> Any:
        """Get Connection Capabilities"""
        return self.request("GET", "/nexora-api/v1/integrations/connections/{connection_id}/capabilities".format(connection_id=connection_id))

    def get_connection_expiry_nexora_api_v1_integrations_connections_connection_id_expiry_get(self, connection_id: str) -> Any:
        """Get Connection Expiry"""
        return self.request("GET", "/nexora-api/v1/integrations/connections/{connection_id}/expiry".format(connection_id=connection_id))

    def get_connection_health_nexora_api_v1_integrations_connections_connection_id_health_get(self, connection_id: str) -> Any:
        """Get Connection Health"""
        return self.request("GET", "/nexora-api/v1/integrations/connections/{connection_id}/health".format(connection_id=connection_id))

    def get_connection_history_nexora_api_v1_integrations_connections_connection_id_history_get(self, connection_id: str) -> Any:
        """Get Connection History"""
        return self.request("GET", "/nexora-api/v1/integrations/connections/{connection_id}/history".format(connection_id=connection_id))

    def get_connection_nexora_api_v1_auth_sso_connections_connection_id_get(self, connection_id: str) -> Any:
        """Get Connection"""
        return self.request("GET", "/nexora-api/v1/auth/sso/connections/{connection_id}".format(connection_id=connection_id))

    def get_conversation_nexora_api_v1_copilot_conversations_conversation_id_get(self, conversation_id: str) -> Any:
        """Get Conversation"""
        return self.request("GET", "/nexora-api/v1/copilot/conversations/{conversation_id}".format(conversation_id=conversation_id))

    def get_credential_nexora_api_v1_credentials_credential_id_get(self, credential_id: str) -> Any:
        """Get Credential"""
        return self.request("GET", "/nexora-api/v1/credentials/{credential_id}".format(credential_id=credential_id))

    def get_current_operation_nexora_api_v1_customer_pilot_operation_get(self) -> Any:
        """Get Current Operation"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation")

    def get_customer_approval_nexora_api_v1_pilot_approvals_approval_id_get(self, approval_id: str) -> Any:
        """Get Customer Approval"""
        return self.request("GET", "/nexora-api/v1/pilot/approvals/{approval_id}".format(approval_id=approval_id))

    def get_customer_pilot_prerequisites_nexora_api_v1_onboarding_integrations_customer_pilot_prerequisites_get(self) -> Any:
        """Get Customer Pilot Prerequisites"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/customer-pilot-prerequisites")

    def get_dashboard_nexora_api_v1_customer_success_dashboard_get(self) -> Any:
        """Get Dashboard"""
        return self.request("GET", "/nexora-api/v1/customer-success/dashboard")

    def get_dashboard_nexora_api_v1_monitoring_dashboard_get(self) -> Any:
        """Get Dashboard"""
        return self.request("GET", "/nexora-api/v1/monitoring/dashboard")

    def get_dashboard_nexora_api_v1_reliability_dashboard_get(self, *, params: dict | None = None) -> Any:
        """Get Dashboard"""
        return self.request("GET", "/nexora-api/v1/reliability-dashboard", params=params)

    def get_deployment_artifact_nexora_api_v1_agents_deployment_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Deployment Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/deployment/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_deployment_dry_run_status_nexora_api_v1_pilot_deployment_readiness_dry_run_get(self) -> Any:
        """Get Deployment Dry Run Status"""
        return self.request("GET", "/nexora-api/v1/pilot/deployment-readiness/dry-run")

    def get_deployment_logs_nexora_api_v1_deployments_deployment_id_logs_get(self, deployment_id: str, *, params: dict | None = None) -> Any:
        """Get Deployment Logs"""
        return self.request("GET", "/nexora-api/v1/deployments/{deployment_id}/logs".format(deployment_id=deployment_id), params=params)

    def get_deployment_nexora_api_v1_delivery_deployments_deployment_id_get(self, deployment_id: str) -> Any:
        """Get Deployment"""
        return self.request("GET", "/nexora-api/v1/delivery/deployments/{deployment_id}".format(deployment_id=deployment_id))

    def get_deployment_nexora_api_v1_deployments_deployment_id_get(self, deployment_id: str) -> Any:
        """Get Deployment"""
        return self.request("GET", "/nexora-api/v1/deployments/{deployment_id}".format(deployment_id=deployment_id))

    def get_deployment_readiness_nexora_api_v1_pilot_deployment_readiness_get(self) -> Any:
        """Get Deployment Readiness"""
        return self.request("GET", "/nexora-api/v1/pilot/deployment-readiness")

    def get_deployment_risk_nexora_api_v1_deployment_risk_get(self, *, params: dict | None = None) -> Any:
        """Get Deployment Risk"""
        return self.request("GET", "/nexora-api/v1/deployment-risk", params=params)

    def get_deployment_run_nexora_api_v1_agents_deployment_runs_run_id_get(self, run_id: str) -> Any:
        """Get Deployment Run"""
        return self.request("GET", "/nexora-api/v1/agents/deployment/runs/{run_id}".format(run_id=run_id))

    def get_deployment_safety_analysis_nexora_api_v1_deployment_safety_analyses_analysis_id_get(self, analysis_id: str) -> Any:
        """Get Deployment Safety Analysis"""
        return self.request("GET", "/nexora-api/v1/deployment-safety/analyses/{analysis_id}".format(analysis_id=analysis_id))

    def get_diagnostics_nexora_api_v1_pilot_support_diagnostics_get(self) -> Any:
        """Get Diagnostics"""
        return self.request("GET", "/nexora-api/v1/pilot/support/diagnostics")

    def get_docker_agent_artifact_nexora_api_v1_agents_docker_agent_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Docker Agent Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/docker-agent/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_docker_agent_run_nexora_api_v1_agents_docker_agent_runs_run_id_get(self, run_id: str) -> Any:
        """Get Docker Agent Run"""
        return self.request("GET", "/nexora-api/v1/agents/docker-agent/runs/{run_id}".format(run_id=run_id))

    def get_docs_image_rendering_nexora_api_v1_docs_image_rendering_get(self) -> Any:
        """Get Docs Image Rendering"""
        return self.request("GET", "/nexora-api/v1/docs/image-rendering")

    def get_docs_readiness_nexora_api_v1_docs_readiness_get(self) -> Any:
        """Get Docs Readiness"""
        return self.request("GET", "/nexora-api/v1/docs/readiness")

    def get_docs_screenshot_audit_nexora_api_v1_docs_screenshot_audit_get(self) -> Any:
        """Get Docs Screenshot Audit"""
        return self.request("GET", "/nexora-api/v1/docs/screenshot-audit")

    def get_docs_verification_readiness_nexora_api_v1_docs_verification_readiness_get(self) -> Any:
        """Get Docs Verification Readiness"""
        return self.request("GET", "/nexora-api/v1/docs/verification-readiness")

    def get_docs_visual_readiness_nexora_api_v1_docs_visual_readiness_get(self) -> Any:
        """Get Docs Visual Readiness"""
        return self.request("GET", "/nexora-api/v1/docs/visual-readiness")

    def get_evidence_nexora_api_v1_customer_pilot_operation_operation_id_evidence_get(self, operation_id: str) -> Any:
        """Get Evidence"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation/{operation_id}/evidence".format(operation_id=operation_id))

    def get_evidence_nexora_api_v1_onboarding_integrations_sessions_session_id_evidence_get(self, session_id: str) -> Any:
        """Get Evidence"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/evidence".format(session_id=session_id))

    def get_execution_nexora_api_v1_platform_executions_run_id_get(self, run_id: str) -> Any:
        """Get Execution"""
        return self.request("GET", "/nexora-api/v1/platform/executions/{run_id}".format(run_id=run_id))

    def get_execution_plan_nexora_api_v1_workflows_workflow_id_execution_plan_get(self, workflow_id: str) -> Any:
        """Get Execution Plan"""
        return self.request("GET", "/nexora-api/v1/workflows/{workflow_id}/execution-plan".format(workflow_id=workflow_id))

    def get_execution_status_nexora_api_v1_customer_pilot_operation_operation_id_execution_status_get(self, operation_id: str) -> Any:
        """Get Execution Status"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation/{operation_id}/execution-status".format(operation_id=operation_id))

    def get_execution_status_nexora_api_v1_pilot_execution_status_get(self) -> Any:
        """Get Execution Status"""
        return self.request("GET", "/nexora-api/v1/pilot/execution/status")

    def get_forecast_nexora_api_v1_capacity_forecasts_forecast_id_get(self, forecast_id: str) -> Any:
        """Get Forecast"""
        return self.request("GET", "/nexora-api/v1/capacity/forecasts/{forecast_id}".format(forecast_id=forecast_id))

    def get_frontend_architect_artifact_nexora_api_v1_agents_frontend_architect_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Frontend Architect Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-architect/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_frontend_architect_run_nexora_api_v1_agents_frontend_architect_runs_run_id_get(self, run_id: str) -> Any:
        """Get Frontend Architect Run"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-architect/runs/{run_id}".format(run_id=run_id))

    def get_frontend_code_review_artifact_nexora_api_v1_agents_frontend_code_review_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Frontend Code Review Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-code-review/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_frontend_code_review_run_nexora_api_v1_agents_frontend_code_review_runs_run_id_get(self, run_id: str) -> Any:
        """Get Frontend Code Review Run"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-code-review/runs/{run_id}".format(run_id=run_id))

    def get_frontend_execution_artifact_nexora_api_v1_agents_frontend_execution_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Frontend Execution Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-execution/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_frontend_execution_run_nexora_api_v1_agents_frontend_execution_runs_run_id_get(self, run_id: str) -> Any:
        """Get Frontend Execution Run"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-execution/runs/{run_id}".format(run_id=run_id))

    def get_frontend_v1_artifact_nexora_api_v1_agents_frontend_v1_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Frontend V1 Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v1/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_frontend_v1_run_nexora_api_v1_agents_frontend_v1_runs_run_id_get(self, run_id: str) -> Any:
        """Get Frontend V1 Run"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v1/runs/{run_id}".format(run_id=run_id))

    def get_frontend_v2_artifact_nexora_api_v1_agents_frontend_v2_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Frontend V2 Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v2/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_frontend_v2_run_nexora_api_v1_agents_frontend_v2_runs_run_id_get(self, run_id: str) -> Any:
        """Get Frontend V2 Run"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v2/runs/{run_id}".format(run_id=run_id))

    def get_frontend_v3_artifact_nexora_api_v1_agents_frontend_v3_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Frontend V3 Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v3/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_frontend_v3_run_nexora_api_v1_agents_frontend_v3_runs_run_id_get(self, run_id: str) -> Any:
        """Get Frontend V3 Run"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v3/runs/{run_id}".format(run_id=run_id))

    def get_fullstack_assembly_artifact_nexora_api_v1_agents_fullstack_assembly_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Fullstack Assembly Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/fullstack-assembly/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_fullstack_assembly_run_nexora_api_v1_agents_fullstack_assembly_runs_run_id_get(self, run_id: str) -> Any:
        """Get Fullstack Assembly Run"""
        return self.request("GET", "/nexora-api/v1/agents/fullstack-assembly/runs/{run_id}".format(run_id=run_id))

    def get_gallery_nexora_api_v1_demo_assets_gallery_get(self, *, params: dict | None = None) -> Any:
        """Get Gallery"""
        return self.request("GET", "/nexora-api/v1/demo-assets/gallery", params=params)

    def get_human_guide_nexora_api_v1_customer_success_human_guides_key_get(self, key: str) -> Any:
        """Get Human Guide"""
        return self.request("GET", "/nexora-api/v1/customer-success/human-guides/{key}".format(key=key))

    def get_impact_analysis_nexora_api_v1_impact_analysis_run_id_get(self, run_id: str) -> Any:
        """Get Impact Analysis"""
        return self.request("GET", "/nexora-api/v1/impact-analysis/{run_id}".format(run_id=run_id))

    def get_incident_actions_nexora_api_v1_incidents_investigation_id_actions_get(self, investigation_id: str) -> Any:
        """Get Incident Actions"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/actions".format(investigation_id=investigation_id))

    def get_incident_changes_nexora_api_v1_incidents_investigation_id_changes_get(self, investigation_id: str) -> Any:
        """Get Incident Changes"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/changes".format(investigation_id=investigation_id))

    def get_incident_command_center_nexora_api_v1_incidents_investigation_id_command_center_get(self, investigation_id: str) -> Any:
        """Get Incident Command Center"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/command-center".format(investigation_id=investigation_id))

    def get_incident_nexora_api_v1_incidents_investigation_id_get(self, investigation_id: str) -> Any:
        """Get Incident"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}".format(investigation_id=investigation_id))

    def get_incident_recommendations_nexora_api_v1_incidents_investigation_id_recommendations_get(self, investigation_id: str) -> Any:
        """Get Incident Recommendations"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/recommendations".format(investigation_id=investigation_id))

    def get_incident_timeline_nexora_api_v1_incidents_investigation_id_timeline_get(self, investigation_id: str) -> Any:
        """Get Incident Timeline"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/timeline".format(investigation_id=investigation_id))

    def get_infrastructure_architect_artifact_nexora_api_v1_agents_infrastructure_architect_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Infrastructure Architect Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/infrastructure-architect/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_infrastructure_architect_run_nexora_api_v1_agents_infrastructure_architect_runs_run_id_get(self, run_id: str) -> Any:
        """Get Infrastructure Architect Run"""
        return self.request("GET", "/nexora-api/v1/agents/infrastructure-architect/runs/{run_id}".format(run_id=run_id))

    def get_integration_test_artifact_nexora_api_v1_agents_integration_tests_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Integration Test Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/integration-tests/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_integration_test_run_nexora_api_v1_agents_integration_tests_runs_run_id_get(self, run_id: str) -> Any:
        """Get Integration Test Run"""
        return self.request("GET", "/nexora-api/v1/agents/integration-tests/runs/{run_id}".format(run_id=run_id))

    def get_integration_visual_nexora_api_v1_customer_success_integration_visuals_key_get(self, key: str) -> Any:
        """Get Integration Visual"""
        return self.request("GET", "/nexora-api/v1/customer-success/integration-visuals/{key}".format(key=key))

    def get_job_nexora_api_v1_jobs_job_id_get(self, job_id: str) -> Any:
        """Get Job"""
        return self.request("GET", "/nexora-api/v1/jobs/{job_id}".format(job_id=job_id))

    def get_journey_nexora_api_v1_customer_success_journeys_key_get(self, key: str) -> Any:
        """Get Journey"""
        return self.request("GET", "/nexora-api/v1/customer-success/journeys/{key}".format(key=key))

    def get_kubernetes_artifact_nexora_api_v1_agents_kubernetes_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Kubernetes Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/kubernetes/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_kubernetes_run_nexora_api_v1_agents_kubernetes_runs_run_id_get(self, run_id: str) -> Any:
        """Get Kubernetes Run"""
        return self.request("GET", "/nexora-api/v1/agents/kubernetes/runs/{run_id}".format(run_id=run_id))

    def get_launch_readiness_nexora_api_v1_pilot_launch_readiness_get(self) -> Any:
        """Get Launch Readiness"""
        return self.request("GET", "/nexora-api/v1/pilot/launch-readiness")

    def get_learning_path_nexora_api_v1_customer_success_learning_paths_key_get(self, key: str, *, params: dict | None = None) -> Any:
        """Get Learning Path"""
        return self.request("GET", "/nexora-api/v1/customer-success/learning-paths/{key}".format(key=key), params=params)

    def get_least_privilege_guide_nexora_api_v1_onboarding_integrations_sessions_session_id_least_privilege_guide_get(self, session_id: str) -> Any:
        """Get Least Privilege Guide"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/least-privilege-guide".format(session_id=session_id))

    def get_live_operation_nexora_api_v1_pilot_live_operations_operation_id_get(self, operation_id: str) -> Any:
        """Get Live Operation"""
        return self.request("GET", "/nexora-api/v1/pilot/live-operations/{operation_id}".format(operation_id=operation_id))

    def get_maintenance_nexora_api_v1_ops_maintenance_get(self) -> Any:
        """Get Maintenance"""
        return self.request("GET", "/nexora-api/v1/ops/maintenance")

    def get_module_nexora_api_v1_customer_success_modules_key_get(self, key: str) -> Any:
        """Get Module"""
        return self.request("GET", "/nexora-api/v1/customer-success/modules/{key}".format(key=key))

    def get_navigation_nexora_api_v1_docs_navigation_get(self) -> Any:
        """Get Navigation"""
        return self.request("GET", "/nexora-api/v1/docs/navigation")

    def get_notification_preferences_nexora_api_v1_customer_pilot_notification_preferences_get(self) -> Any:
        """Get Notification Preferences"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/notification-preferences")

    def get_observability_artifact_nexora_api_v1_agents_observability_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Observability Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/observability/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_observability_run_nexora_api_v1_agents_observability_runs_run_id_get(self, run_id: str) -> Any:
        """Get Observability Run"""
        return self.request("GET", "/nexora-api/v1/agents/observability/runs/{run_id}".format(run_id=run_id))

    def get_onboarding_nexora_api_v1_onboarding_session_id_get(self, session_id: str) -> Any:
        """Get Onboarding"""
        return self.request("GET", "/nexora-api/v1/onboarding/{session_id}".format(session_id=session_id))

    def get_operation_nexora_api_v1_customer_pilot_operation_operation_id_get(self, operation_id: str) -> Any:
        """Get Operation"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation/{operation_id}".format(operation_id=operation_id))

    def get_operations_readiness_nexora_api_v1_pilot_operations_readiness_get(self) -> Any:
        """Get Operations Readiness"""
        return self.request("GET", "/nexora-api/v1/pilot/operations-readiness")

    def get_operator_handoff_nexora_api_v1_pilot_live_operations_operation_id_operator_handoff_get(self, operation_id: str) -> Any:
        """Get Operator Handoff"""
        return self.request("GET", "/nexora-api/v1/pilot/live-operations/{operation_id}/operator-handoff".format(operation_id=operation_id))

    def get_organization_nexora_api_v1_organizations_organization_id_get(self, organization_id: str) -> Any:
        """Get Organization"""
        return self.request("GET", "/nexora-api/v1/organizations/{organization_id}".format(organization_id=organization_id))

    def get_overview_nexora_api_v1_customer_pilot_overview_get(self) -> Any:
        """Get Overview"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/overview")

    def get_performance_test_artifact_nexora_api_v1_agents_performance_tests_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Performance Test Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/performance-tests/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_performance_test_run_nexora_api_v1_agents_performance_tests_runs_run_id_get(self, run_id: str) -> Any:
        """Get Performance Test Run"""
        return self.request("GET", "/nexora-api/v1/agents/performance-tests/runs/{run_id}".format(run_id=run_id))

    def get_pilot_dashboard_nexora_api_v1_pilot_dashboard_get(self) -> Any:
        """Get Pilot Dashboard"""
        return self.request("GET", "/nexora-api/v1/pilot/dashboard")

    def get_pilot_readiness_nexora_api_v1_pilot_readiness_get(self) -> Any:
        """Get Pilot Readiness"""
        return self.request("GET", "/nexora-api/v1/pilot/readiness")

    def get_playbook_nexora_api_v1_customer_success_playbooks_key_get(self, key: str) -> Any:
        """Get Playbook"""
        return self.request("GET", "/nexora-api/v1/customer-success/playbooks/{key}".format(key=key))

    def get_playbook_nexora_api_v1_test_playbooks_playbook_id_get(self, playbook_id: str) -> Any:
        """Get Playbook"""
        return self.request("GET", "/nexora-api/v1/test-playbooks/{playbook_id}".format(playbook_id=playbook_id))

    def get_portal_nexora_api_v1_customer_success_portal_get(self) -> Any:
        """Get Portal"""
        return self.request("GET", "/nexora-api/v1/customer-success/portal")

    def get_portal_nexora_api_v1_docs_portal_get(self) -> Any:
        """Get Portal"""
        return self.request("GET", "/nexora-api/v1/docs/portal")

    def get_postmortem_nexora_api_v1_postmortems_postmortem_id_get(self, postmortem_id: str) -> Any:
        """Get Postmortem"""
        return self.request("GET", "/nexora-api/v1/postmortems/{postmortem_id}".format(postmortem_id=postmortem_id))

    def get_preferences_nexora_api_v1_product_preferences_get(self) -> Any:
        """Get Preferences"""
        return self.request("GET", "/nexora-api/v1/product/preferences")

    def get_project_nexora_api_v1_projects_project_id_get(self, project_id: str) -> Any:
        """Get Project"""
        return self.request("GET", "/nexora-api/v1/projects/{project_id}".format(project_id=project_id))

    def get_prompt_nexora_api_v1_ai_prompts_key_get(self, key: str) -> Any:
        """Get Prompt"""
        return self.request("GET", "/nexora-api/v1/ai/prompts/{key}".format(key=key))

    def get_qa_approval_artifact_nexora_api_v1_agents_qa_approvals_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Qa Approval Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/qa-approvals/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_qa_approval_run_nexora_api_v1_agents_qa_approvals_runs_run_id_get(self, run_id: str) -> Any:
        """Get Qa Approval Run"""
        return self.request("GET", "/nexora-api/v1/agents/qa-approvals/runs/{run_id}".format(run_id=run_id))

    def get_qa_architect_artifact_nexora_api_v1_agents_qa_architect_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Qa Architect Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/qa-architect/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_qa_architect_run_nexora_api_v1_agents_qa_architect_runs_run_id_get(self, run_id: str) -> Any:
        """Get Qa Architect Run"""
        return self.request("GET", "/nexora-api/v1/agents/qa-architect/runs/{run_id}".format(run_id=run_id))

    def get_quality_nexora_api_v1_customer_success_quality_get(self) -> Any:
        """Get Quality"""
        return self.request("GET", "/nexora-api/v1/customer-success/quality")

    def get_rbac_report_nexora_api_v1_onboarding_integrations_sessions_session_id_rbac_report_get(self, session_id: str) -> Any:
        """Get Rbac Report"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/rbac-report".format(session_id=session_id))

    def get_readiness_nexora_api_v1_customer_pilot_readiness_get(self) -> Any:
        """Get Readiness"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/readiness")

    def get_readiness_nexora_api_v1_customer_success_readiness_get(self) -> Any:
        """Get Readiness"""
        return self.request("GET", "/nexora-api/v1/customer-success/readiness")

    def get_readiness_nexora_api_v1_onboarding_integrations_readiness_get(self) -> Any:
        """Get Readiness"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/readiness")

    def get_recommendation_nexora_api_v1_operator_recommendations_recommendation_id_get(self, recommendation_id: str) -> Any:
        """Get Recommendation"""
        return self.request("GET", "/nexora-api/v1/operator/recommendations/{recommendation_id}".format(recommendation_id=recommendation_id))

    def get_regeneration_nexora_api_v1_regeneration_run_id_get(self, run_id: str) -> Any:
        """Get Regeneration"""
        return self.request("GET", "/nexora-api/v1/regeneration/{run_id}".format(run_id=run_id))

    def get_release_channel_nexora_api_v1_ga_release_channel_get(self) -> Any:
        """Get Release Channel"""
        return self.request("GET", "/nexora-api/v1/ga/release/channel")

    def get_release_evidence_nexora_api_v1_delivery_release_reliability_reliability_id_evidence_get(self, reliability_id: str) -> Any:
        """Get Release Evidence"""
        return self.request("GET", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/evidence".format(reliability_id=reliability_id))

    def get_release_reliability_nexora_api_v1_delivery_release_reliability_reliability_id_get(self, reliability_id: str) -> Any:
        """Get Release Reliability"""
        return self.request("GET", "/nexora-api/v1/delivery/release-reliability/{reliability_id}".format(reliability_id=reliability_id))

    def get_remediation_action_approvals_nexora_api_v1_remediation_actions_action_id_approvals_get(self, action_id: str) -> Any:
        """Get Remediation Action Approvals"""
        return self.request("GET", "/nexora-api/v1/remediation-actions/{action_id}/approvals".format(action_id=action_id))

    def get_remediation_action_nexora_api_v1_remediation_actions_action_id_get(self, action_id: str) -> Any:
        """Get Remediation Action"""
        return self.request("GET", "/nexora-api/v1/remediation-actions/{action_id}".format(action_id=action_id))

    def get_remediation_execution_nexora_api_v1_security_remediation_proposal_id_execution_get(self, proposal_id: str) -> Any:
        """Get Remediation Execution"""
        return self.request("GET", "/nexora-api/v1/security/remediation/{proposal_id}/execution".format(proposal_id=proposal_id))

    def get_report_nexora_api_v1_executive_reports_report_id_get(self, report_id: str) -> Any:
        """Get Report"""
        return self.request("GET", "/nexora-api/v1/executive-reports/{report_id}".format(report_id=report_id))

    def get_repository_nexora_api_v1_delivery_repositories_repo_id_get(self, repo_id: str) -> Any:
        """Get Repository"""
        return self.request("GET", "/nexora-api/v1/delivery/repositories/{repo_id}".format(repo_id=repo_id))

    def get_requirement_nexora_api_v1_requirements_requirement_id_get(self, requirement_id: str) -> Any:
        """Get Requirement"""
        return self.request("GET", "/nexora-api/v1/requirements/{requirement_id}".format(requirement_id=requirement_id))

    def get_routing_nexora_api_v1_ai_routing_get(self) -> Any:
        """Get Routing"""
        return self.request("GET", "/nexora-api/v1/ai/routing")

    def get_run_nexora_api_v1_test_playbooks_runs_run_id_get(self, run_id: str) -> Any:
        """Get Run"""
        return self.request("GET", "/nexora-api/v1/test-playbooks/runs/{run_id}".format(run_id=run_id))

    def get_runbook_nexora_api_v1_runbooks_runbook_id_get(self, runbook_id: str) -> Any:
        """Get Runbook"""
        return self.request("GET", "/nexora-api/v1/runbooks/{runbook_id}".format(runbook_id=runbook_id))

    def get_sales_mode_nexora_api_v1_demo_sales_mode_get(self) -> Any:
        """Get Sales Mode"""
        return self.request("GET", "/nexora-api/v1/demo/sales-mode")

    def get_scenario_nexora_api_v1_demo_scenarios_scenario_id_get(self, scenario_id: str) -> Any:
        """Get Scenario"""
        return self.request("GET", "/nexora-api/v1/demo-scenarios/{scenario_id}".format(scenario_id=scenario_id))

    def get_schedule_nexora_api_v1_oncall_schedules_schedule_id_get(self, schedule_id: str) -> Any:
        """Get Schedule"""
        return self.request("GET", "/nexora-api/v1/oncall/schedules/{schedule_id}".format(schedule_id=schedule_id))

    def get_scorecard_nexora_api_v1_pilot_scorecard_get(self) -> Any:
        """Get Scorecard"""
        return self.request("GET", "/nexora-api/v1/pilot/scorecard")

    def get_screenshot_coverage_nexora_api_v1_customer_success_screenshot_coverage_get(self) -> Any:
        """Get Screenshot Coverage"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-coverage")

    def get_screenshot_manifest_nexora_api_v1_demo_walkthroughs_screenshots_get(self) -> Any:
        """Get Screenshot Manifest"""
        return self.request("GET", "/nexora-api/v1/demo-walkthroughs/screenshots")

    def get_screenshot_nexora_api_v1_customer_success_screenshots_screenshot_id_get(self, screenshot_id: str) -> Any:
        """Get Screenshot"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshots/{screenshot_id}".format(screenshot_id=screenshot_id))

    def get_screenshots_nexora_api_v1_customer_success_screenshots_get(self, *, params: dict | None = None) -> Any:
        """Get Screenshots"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshots", params=params)

    def get_security_policy_nexora_api_v1_security_policy_get(self) -> Any:
        """Get Security Policy"""
        return self.request("GET", "/nexora-api/v1/security-policy")

    def get_security_test_artifact_nexora_api_v1_agents_security_tests_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Security Test Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/security-tests/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_security_test_run_nexora_api_v1_agents_security_tests_runs_run_id_get(self, run_id: str) -> Any:
        """Get Security Test Run"""
        return self.request("GET", "/nexora-api/v1/agents/security-tests/runs/{run_id}".format(run_id=run_id))

    def get_service_account_nexora_api_v1_service_accounts_sa_id_get(self, sa_id: str) -> Any:
        """Get Service Account"""
        return self.request("GET", "/nexora-api/v1/service-accounts/{sa_id}".format(sa_id=sa_id))

    def get_service_nexora_api_v1_services_service_id_get(self, service_id: str) -> Any:
        """Get Service"""
        return self.request("GET", "/nexora-api/v1/services/{service_id}".format(service_id=service_id))

    def get_session_nexora_api_v1_onboarding_integrations_sessions_session_id_get(self, session_id: str) -> Any:
        """Get Session"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}".format(session_id=session_id))

    def get_sla_nexora_api_v1_security_sla_get(self) -> Any:
        """Get Sla"""
        return self.request("GET", "/nexora-api/v1/security/sla")

    def get_snapshot_nexora_api_v1_architecture_snapshot_id_get(self, snapshot_id: str) -> Any:
        """Get Snapshot"""
        return self.request("GET", "/nexora-api/v1/architecture/{snapshot_id}".format(snapshot_id=snapshot_id))

    def get_sre_approval_artifact_nexora_api_v1_agents_sre_approval_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Sre Approval Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/sre-approval/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_sre_approval_run_nexora_api_v1_agents_sre_approval_runs_run_id_get(self, run_id: str) -> Any:
        """Get Sre Approval Run"""
        return self.request("GET", "/nexora-api/v1/agents/sre-approval/runs/{run_id}".format(run_id=run_id))

    def get_subscription_nexora_api_v1_billing_subscription_get(self) -> Any:
        """Get Subscription"""
        return self.request("GET", "/nexora-api/v1/billing/subscription")

    def get_success_nexora_api_v1_customer_success_success_center_key_get(self, key: str) -> Any:
        """Get Success"""
        return self.request("GET", "/nexora-api/v1/customer-success/success-center/{key}".format(key=key))

    def get_summary_nexora_api_v1_reliability_dashboard_summary_get(self, *, params: dict | None = None) -> Any:
        """Get Summary"""
        return self.request("GET", "/nexora-api/v1/reliability-dashboard/summary", params=params)

    def get_team_nexora_api_v1_teams_team_id_get(self, team_id: str) -> Any:
        """Get Team"""
        return self.request("GET", "/nexora-api/v1/teams/{team_id}".format(team_id=team_id))

    def get_team_template_nexora_api_v1_team_templates_slug_get(self, slug: str) -> Any:
        """Get Team Template"""
        return self.request("GET", "/nexora-api/v1/team-templates/{slug}".format(slug=slug))

    def get_timeline_nexora_api_v1_customer_pilot_timeline_get(self, *, params: dict | None = None) -> Any:
        """Get Timeline"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/timeline", params=params)

    def get_tour_nexora_api_v1_customer_success_tours_key_get(self, key: str) -> Any:
        """Get Tour"""
        return self.request("GET", "/nexora-api/v1/customer-success/tours/{key}".format(key=key))

    def get_tour_nexora_api_v1_product_tours_tour_id_get(self, tour_id: str) -> Any:
        """Get Tour"""
        return self.request("GET", "/nexora-api/v1/product-tours/{tour_id}".format(tour_id=tour_id))

    def get_uiux_artifact_nexora_api_v1_agents_uiux_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Uiux Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/uiux/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_uiux_run_nexora_api_v1_agents_uiux_runs_run_id_get(self, run_id: str) -> Any:
        """Get Uiux Run"""
        return self.request("GET", "/nexora-api/v1/agents/uiux/runs/{run_id}".format(run_id=run_id))

    def get_unit_test_artifact_nexora_api_v1_agents_unit_tests_artifacts_artifact_id_get(self, artifact_id: str) -> Any:
        """Get Unit Test Artifact"""
        return self.request("GET", "/nexora-api/v1/agents/unit-tests/artifacts/{artifact_id}".format(artifact_id=artifact_id))

    def get_unit_test_run_nexora_api_v1_agents_unit_tests_runs_run_id_get(self, run_id: str) -> Any:
        """Get Unit Test Run"""
        return self.request("GET", "/nexora-api/v1/agents/unit-tests/runs/{run_id}".format(run_id=run_id))

    def get_verification_nexora_api_v1_customer_pilot_operation_operation_id_verification_get(self, operation_id: str) -> Any:
        """Get Verification"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/operation/{operation_id}/verification".format(operation_id=operation_id))

    def get_video_nexora_api_v1_customer_success_videos_video_id_get(self, video_id: str) -> Any:
        """Get Video"""
        return self.request("GET", "/nexora-api/v1/customer-success/videos/{video_id}".format(video_id=video_id))

    def get_walkthrough_nexora_api_v1_demo_walkthroughs_get(self, *, params: dict | None = None) -> Any:
        """Get Walkthrough"""
        return self.request("GET", "/nexora-api/v1/demo-walkthroughs", params=params)

    def get_war_room_nexora_api_v1_war_rooms_war_room_id_get(self, war_room_id: str) -> Any:
        """Get War Room"""
        return self.request("GET", "/nexora-api/v1/war-rooms/{war_room_id}".format(war_room_id=war_room_id))

    def get_workflow_approval_nexora_api_v1_workflow_approvals_approval_id_get(self, approval_id: str) -> Any:
        """Get Workflow Approval"""
        return self.request("GET", "/nexora-api/v1/workflow-approvals/{approval_id}".format(approval_id=approval_id))

    def get_workflow_execution_nexora_api_v1_workflow_executions_execution_id_get(self, execution_id: str) -> Any:
        """Get Workflow Execution"""
        return self.request("GET", "/nexora-api/v1/workflow-executions/{execution_id}".format(execution_id=execution_id))

    def get_workflow_execution_status_nexora_api_v1_workflow_executions_execution_id_status_get(self, execution_id: str) -> Any:
        """Get Workflow Execution Status"""
        return self.request("GET", "/nexora-api/v1/workflow-executions/{execution_id}/status".format(execution_id=execution_id))

    def get_workflow_nexora_api_v1_workflows_workflow_id_get(self, workflow_id: str) -> Any:
        """Get Workflow"""
        return self.request("GET", "/nexora-api/v1/workflows/{workflow_id}".format(workflow_id=workflow_id))

    def get_workflow_schedule_nexora_api_v1_ai_team_workflow_schedules_schedule_id_get(self, schedule_id: str) -> Any:
        """Get Workflow Schedule"""
        return self.request("GET", "/nexora-api/v1/ai-team-workflow-schedules/{schedule_id}".format(schedule_id=schedule_id))

    def get_workflow_template_nexora_api_v1_workflow_templates_slug_get(self, slug: str) -> Any:
        """Get Workflow Template"""
        return self.request("GET", "/nexora-api/v1/workflow-templates/{slug}".format(slug=slug))

    def get_workspace_nexora_api_v1_workspaces_workspace_id_get(self, workspace_id: str) -> Any:
        """Get Workspace"""
        return self.request("GET", "/nexora-api/v1/workspaces/{workspace_id}".format(workspace_id=workspace_id))

    def global_search_nexora_api_v1_platform_search_get(self, *, params: dict | None = None) -> Any:
        """Global Search"""
        return self.request("GET", "/nexora-api/v1/platform/search", params=params)

    def grant_exception_nexora_api_v1_security_exceptions_post(self, *, json: Any = None) -> Any:
        """Grant Exception"""
        return self.request("POST", "/nexora-api/v1/security/exceptions", json=json)

    def graph_analytics_nexora_api_v1_platform_graph_analytics_get(self) -> Any:
        """Graph Analytics"""
        return self.request("GET", "/nexora-api/v1/platform/graph/analytics")

    def handover_pdf_nexora_api_v1_ops_workspace_handover_handover_id_export_pdf_get(self, handover_id: str) -> Any:
        """Handover Pdf"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/handover/{handover_id}/export/pdf".format(handover_id=handover_id))

    def health_center_nexora_api_v1_ga_health_get(self) -> Any:
        """Health Center"""
        return self.request("GET", "/nexora-api/v1/ga/health")

    def health_nexora_api_health_get(self) -> Any:
        """Health"""
        return self.request("GET", "/nexora-api/health")

    def health_overview_nexora_api_v1_services_health_get(self) -> Any:
        """Health Overview"""
        return self.request("GET", "/nexora-api/v1/services/health")

    def history_nexora_api_v1_operator_history_get(self) -> Any:
        """History"""
        return self.request("GET", "/nexora-api/v1/operator/history")

    def human_guides_quality_nexora_api_v1_customer_success_human_guides_quality_get(self) -> Any:
        """Human Guides Quality"""
        return self.request("GET", "/nexora-api/v1/customer-success/human-guides-quality")

    def iac_security_nexora_api_v1_security_iac_get(self) -> Any:
        """Iac Security"""
        return self.request("GET", "/nexora-api/v1/security/iac")

    def identity_security_nexora_api_v1_security_identity_get(self) -> Any:
        """Identity Security"""
        return self.request("GET", "/nexora-api/v1/security/identity")

    def import_config_nexora_api_v1_ops_config_import_post(self, *, json: Any = None) -> Any:
        """Import Config"""
        return self.request("POST", "/nexora-api/v1/ops/config/import", json=json)

    def import_saml_metadata_nexora_api_v1_auth_sso_connections_connection_id_saml_import_metadata_post(self, connection_id: str, *, json: Any = None) -> Any:
        """Import Saml Metadata"""
        return self.request("POST", "/nexora-api/v1/auth/sso/connections/{connection_id}/saml/import-metadata".format(connection_id=connection_id), json=json)

    def import_sbom_nexora_api_v1_security_sbom_import_post(self, *, json: Any = None) -> Any:
        """Import Sbom"""
        return self.request("POST", "/nexora-api/v1/security/sbom/import", json=json)

    def inbox_unread_count_nexora_api_v1_product_inbox_unread_count_get(self) -> Any:
        """Inbox Unread Count"""
        return self.request("GET", "/nexora-api/v1/product/inbox/unread-count")

    def incident_analytics_nexora_api_v1_incidents_analytics_get(self) -> Any:
        """Incident Analytics"""
        return self.request("GET", "/nexora-api/v1/incidents/analytics")

    def incident_blast_radius_nexora_api_v1_incidents_incident_id_blast_radius_get(self, incident_id: str) -> Any:
        """Incident Blast Radius"""
        return self.request("GET", "/nexora-api/v1/incidents/{incident_id}/blast-radius".format(incident_id=incident_id))

    def ingest_metrics_nexora_api_v1_capacity_metrics_post(self, *, json: Any = None) -> Any:
        """Ingest Metrics"""
        return self.request("POST", "/nexora-api/v1/capacity/metrics", json=json)

    def ingest_webhook_nexora_api_v1_monitoring_ingest_post(self, *, json: Any = None) -> Any:
        """Ingest Webhook"""
        return self.request("POST", "/nexora-api/v1/monitoring/ingest", json=json)

    def install_plugin_nexora_api_v1_platform_plugins_install_post(self, *, json: Any = None) -> Any:
        """Install Plugin"""
        return self.request("POST", "/nexora-api/v1/platform/plugins/install", json=json)

    def integration_dashboard_nexora_api_v1_integrations_dashboard_get(self) -> Any:
        """Integration Dashboard"""
        return self.request("GET", "/nexora-api/v1/integrations/dashboard")

    def integration_health_board_nexora_api_v1_integrations_connections_health_board_get(self) -> Any:
        """Integration Health Board"""
        return self.request("GET", "/nexora-api/v1/integrations/connections/health-board")

    def integration_visuals_nexora_api_v1_customer_success_integration_visuals_get(self) -> Any:
        """Integration Visuals"""
        return self.request("GET", "/nexora-api/v1/customer-success/integration-visuals")

    def investigate_incident_nexora_api_v1_incidents_investigate_post(self, *, json: Any = None) -> Any:
        """Investigate Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/investigate", json=json)

    def issue_confirmation_token_nexora_api_v1_pilot_live_operations_operation_id_confirmation_token_post(self, operation_id: str) -> Any:
        """Issue Confirmation Token"""
        return self.request("POST", "/nexora-api/v1/pilot/live-operations/{operation_id}/confirmation-token".format(operation_id=operation_id))

    def issue_license_nexora_api_v1_billing_admin_licenses_post(self, *, json: Any = None) -> Any:
        """Issue License"""
        return self.request("POST", "/nexora-api/v1/billing/admin/licenses", json=json)

    def issue_service_account_key_nexora_api_v1_service_accounts_sa_id_keys_post(self, sa_id: str, *, json: Any = None) -> Any:
        """Issue Service Account Key"""
        return self.request("POST", "/nexora-api/v1/service-accounts/{sa_id}/keys".format(sa_id=sa_id), json=json)

    def issue_support_token_nexora_api_v1_ga_support_token_post(self, *, json: Any = None) -> Any:
        """Issue Support Token"""
        return self.request("POST", "/nexora-api/v1/ga/support/token", json=json)

    def issue_support_token_nexora_api_v1_pilot_support_token_post(self) -> Any:
        """Issue Support Token"""
        return self.request("POST", "/nexora-api/v1/pilot/support/token")

    def journey_diagrams_nexora_api_v1_customer_success_journey_diagrams_get(self) -> Any:
        """Journey Diagrams"""
        return self.request("GET", "/nexora-api/v1/customer-success/journey-diagrams")

    def journey_export_nexora_api_v1_customer_success_journeys_key_export_get(self, key: str, *, params: dict | None = None) -> Any:
        """Journey Export"""
        return self.request("GET", "/nexora-api/v1/customer-success/journeys/{key}/export".format(key=key), params=params)

    def journey_manual_nexora_api_v1_customer_success_journeys_key_manual_get(self, key: str) -> Any:
        """Journey Manual"""
        return self.request("GET", "/nexora-api/v1/customer-success/journeys/{key}/manual".format(key=key))

    def journey_manuals_nexora_api_v1_customer_success_journey_manuals_get(self) -> Any:
        """Journey Manuals"""
        return self.request("GET", "/nexora-api/v1/customer-success/journey-manuals")

    def journey_verification_nexora_api_v1_customer_success_journey_verification_get(self) -> Any:
        """Journey Verification"""
        return self.request("GET", "/nexora-api/v1/customer-success/journey-verification")

    def journey_walkthroughs_nexora_api_v1_customer_success_journey_walkthroughs_get(self) -> Any:
        """Journey Walkthroughs"""
        return self.request("GET", "/nexora-api/v1/customer-success/journey-walkthroughs")

    def k8s_capabilities_nexora_api_v1_control_plane_clusters_cluster_id_k8s_capabilities_get(self, cluster_id: str) -> Any:
        """K8S Capabilities"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/capabilities".format(cluster_id=cluster_id))

    def k8s_overview_nexora_api_v1_control_plane_clusters_cluster_id_k8s_overview_get(self, cluster_id: str) -> Any:
        """K8S Overview"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/overview".format(cluster_id=cluster_id))

    def k8s_read_nexora_api_v1_control_plane_clusters_cluster_id_k8s_read_post(self, cluster_id: str, *, json: Any = None) -> Any:
        """K8S Read"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/read".format(cluster_id=cluster_id), json=json)

    def kubernetes_security_nexora_api_v1_security_kubernetes_get(self) -> Any:
        """Kubernetes Security"""
        return self.request("GET", "/nexora-api/v1/security/kubernetes")

    def latest_compliance_nexora_api_v1_platform_engineering_compliance_latest_get(self) -> Any:
        """Latest Compliance"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/compliance/latest")

    def latest_daily_briefing_nexora_api_v1_ops_workspace_briefing_daily_latest_get(self) -> Any:
        """Latest Daily Briefing"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/briefing/daily/latest")

    def latest_executive_briefing_nexora_api_v1_operator_executive_latest_get(self) -> Any:
        """Latest Executive Briefing"""
        return self.request("GET", "/nexora-api/v1/operator/executive/latest")

    def latest_handover_nexora_api_v1_ops_workspace_handover_latest_get(self) -> Any:
        """Latest Handover"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/handover/latest")

    def learning_nexora_api_v1_operator_learning_get(self) -> Any:
        """Learning"""
        return self.request("GET", "/nexora-api/v1/operator/learning")

    def lifecycle_nexora_api_v1_customer_success_lifecycle_get(self) -> Any:
        """Lifecycle"""
        return self.request("GET", "/nexora-api/v1/customer-success/lifecycle")

    def lifecycle_report_nexora_api_v1_customer_success_lifecycle_report_get(self) -> Any:
        """Lifecycle Report"""
        return self.request("GET", "/nexora-api/v1/customer-success/lifecycle-report")

    def list_activity_nexora_api_v1_platform_activity_get(self, *, params: dict | None = None) -> Any:
        """List Activity"""
        return self.request("GET", "/nexora-api/v1/platform/activity", params=params)

    def list_agent_audit_nexora_api_v1_ai_agents_agent_id_audit_get(self, agent_id: str) -> Any:
        """List Agent Audit"""
        return self.request("GET", "/nexora-api/v1/ai-agents/{agent_id}/audit".format(agent_id=agent_id))

    def list_agent_runs_nexora_api_v1_agents_runs_get(self, *, params: dict | None = None) -> Any:
        """List Agent Runs"""
        return self.request("GET", "/nexora-api/v1/agents/runs", params=params)

    def list_ai_agent_templates_nexora_api_v1_ai_agent_templates_get(self, *, params: dict | None = None) -> Any:
        """List Ai Agent Templates"""
        return self.request("GET", "/nexora-api/v1/ai-agent-templates", params=params)

    def list_ai_agents_nexora_api_v1_ai_agents_get(self, *, params: dict | None = None) -> Any:
        """List Ai Agents"""
        return self.request("GET", "/nexora-api/v1/ai-agents", params=params)

    def list_ai_team_agent_memory_nexora_api_v1_ai_team_agents_agent_id_memory_get(self, agent_id: str, *, params: dict | None = None) -> Any:
        """List Ai Team Agent Memory"""
        return self.request("GET", "/nexora-api/v1/ai-team-agents/{agent_id}/memory".format(agent_id=agent_id), params=params)

    def list_ai_team_agent_runs_nexora_api_v1_ai_team_agents_agent_id_runs_get(self, agent_id: str, *, params: dict | None = None) -> Any:
        """List Ai Team Agent Runs"""
        return self.request("GET", "/nexora-api/v1/ai-team-agents/{agent_id}/runs".format(agent_id=agent_id), params=params)

    def list_ai_team_agent_tools_nexora_api_v1_ai_team_agents_agent_id_tools_get(self, agent_id: str) -> Any:
        """List Ai Team Agent Tools"""
        return self.request("GET", "/nexora-api/v1/ai-team-agents/{agent_id}/tools".format(agent_id=agent_id))

    def list_ai_team_agents_nexora_api_v1_ai_team_agents_get(self, *, params: dict | None = None) -> Any:
        """List Ai Team Agents"""
        return self.request("GET", "/nexora-api/v1/ai-team-agents", params=params)

    def list_ai_team_documents_nexora_api_v1_ai_teams_team_id_documents_get(self, team_id: str, *, params: dict | None = None) -> Any:
        """List Ai Team Documents"""
        return self.request("GET", "/nexora-api/v1/ai-teams/{team_id}/documents".format(team_id=team_id), params=params)

    def list_ai_team_runs_nexora_api_v1_ai_teams_team_id_runs_get(self, team_id: str, *, params: dict | None = None) -> Any:
        """List Ai Team Runs"""
        return self.request("GET", "/nexora-api/v1/ai-teams/{team_id}/runs".format(team_id=team_id), params=params)

    def list_ai_team_workflow_runs_nexora_api_v1_ai_team_workflows_workflow_id_runs_get(self, workflow_id: str, *, params: dict | None = None) -> Any:
        """List Ai Team Workflow Runs"""
        return self.request("GET", "/nexora-api/v1/ai-team-workflows/{workflow_id}/runs".format(workflow_id=workflow_id), params=params)

    def list_ai_team_workflows_nexora_api_v1_ai_team_workflows_get(self, *, params: dict | None = None) -> Any:
        """List Ai Team Workflows"""
        return self.request("GET", "/nexora-api/v1/ai-team-workflows", params=params)

    def list_ai_teams_nexora_api_v1_ai_teams_get(self, *, params: dict | None = None) -> Any:
        """List Ai Teams"""
        return self.request("GET", "/nexora-api/v1/ai-teams", params=params)

    def list_ai_tool_runs_nexora_api_v1_ai_tools_tool_id_runs_get(self, tool_id: str, *, params: dict | None = None) -> Any:
        """List Ai Tool Runs"""
        return self.request("GET", "/nexora-api/v1/ai-tools/{tool_id}/runs".format(tool_id=tool_id), params=params)

    def list_ai_tools_nexora_api_v1_ai_tools_get(self, *, params: dict | None = None) -> Any:
        """List Ai Tools"""
        return self.request("GET", "/nexora-api/v1/ai-tools", params=params)

    def list_alerts_nexora_api_v1_monitoring_alerts_get(self, *, params: dict | None = None) -> Any:
        """List Alerts"""
        return self.request("GET", "/nexora-api/v1/monitoring/alerts", params=params)

    def list_all_runs_nexora_api_v1_demo_scenarios_runs_get(self) -> Any:
        """List All Runs"""
        return self.request("GET", "/nexora-api/v1/demo-scenarios/runs")

    def list_analyses_nexora_api_v1_cost_optimization_analyses_get(self, *, params: dict | None = None) -> Any:
        """List Analyses"""
        return self.request("GET", "/nexora-api/v1/cost-optimization/analyses", params=params)

    def list_annotations_nexora_api_v1_customer_success_annotations_get(self, *, params: dict | None = None) -> Any:
        """List Annotations"""
        return self.request("GET", "/nexora-api/v1/customer-success/annotations", params=params)

    def list_application_versions_nexora_api_v1_application_versions_get(self, *, params: dict | None = None) -> Any:
        """List Application Versions"""
        return self.request("GET", "/nexora-api/v1/application-versions", params=params)

    def list_approval_runs_for_requirement_nexora_api_v1_agents_approval_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Approval Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/approval/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_architecture_nexora_api_v1_customer_success_architecture_get(self) -> Any:
        """List Architecture"""
        return self.request("GET", "/nexora-api/v1/customer-success/architecture")

    def list_articles_nexora_api_v1_docs_articles_get(self, *, params: dict | None = None) -> Any:
        """List Articles"""
        return self.request("GET", "/nexora-api/v1/docs/articles", params=params)

    def list_artifacts_nexora_api_v1_delivery_artifacts_get(self) -> Any:
        """List Artifacts"""
        return self.request("GET", "/nexora-api/v1/delivery/artifacts")

    def list_assessments_nexora_api_v1_reliability_get(self) -> Any:
        """List Assessments"""
        return self.request("GET", "/nexora-api/v1/reliability")

    def list_assets_nexora_api_v1_demo_assets_get(self, *, params: dict | None = None) -> Any:
        """List Assets"""
        return self.request("GET", "/nexora-api/v1/demo-assets", params=params)

    def list_backend_architect_runs_for_requirement_nexora_api_v1_agents_backend_architect_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Backend Architect Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/backend-architect/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_backend_code_review_runs_for_requirement_nexora_api_v1_agents_backend_code_review_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Backend Code Review Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/backend-code-review/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_backend_execution_runs_for_requirement_nexora_api_v1_agents_backend_execution_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Backend Execution Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/backend-execution/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_backend_v1_runs_for_requirement_nexora_api_v1_agents_backend_v1_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Backend V1 Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v1/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_backend_v2_runs_for_requirement_nexora_api_v1_agents_backend_v2_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Backend V2 Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v2/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_backend_v3_runs_for_requirement_nexora_api_v1_agents_backend_v3_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Backend V3 Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/backend-v3/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_backups_nexora_api_v1_ga_backups_get(self) -> Any:
        """List Backups"""
        return self.request("GET", "/nexora-api/v1/ga/backups")

    def list_business_analyst_runs_for_requirement_nexora_api_v1_agents_business_analyst_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Business Analyst Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/business-analyst/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_captures_nexora_api_v1_customer_success_captures_get(self, *, params: dict | None = None) -> Any:
        """List Captures"""
        return self.request("GET", "/nexora-api/v1/customer-success/captures", params=params)

    def list_catalog_nexora_api_v1_platform_engineering_catalog_get(self) -> Any:
        """List Catalog"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/catalog")

    def list_categories_nexora_api_v1_docs_categories_get(self) -> Any:
        """List Categories"""
        return self.request("GET", "/nexora-api/v1/docs/categories")

    def list_change_failures_nexora_api_v1_change_failure_prediction_get(self, *, params: dict | None = None) -> Any:
        """List Change Failures"""
        return self.request("GET", "/nexora-api/v1/change-failure-prediction", params=params)

    def list_change_requests_nexora_api_v1_change_requests_get(self, *, params: dict | None = None) -> Any:
        """List Change Requests"""
        return self.request("GET", "/nexora-api/v1/change-requests", params=params)

    def list_cicd_runs_for_requirement_nexora_api_v1_agents_cicd_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Cicd Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/cicd/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_cloud_accounts_nexora_api_v1_control_plane_cloud_accounts_get(self) -> Any:
        """List Cloud Accounts"""
        return self.request("GET", "/nexora-api/v1/control-plane/cloud-accounts")

    def list_cluster_resources_nexora_api_v1_control_plane_clusters_cluster_id_resources_get(self, cluster_id: str, *, params: dict | None = None) -> Any:
        """List Cluster Resources"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/resources".format(cluster_id=cluster_id), params=params)

    def list_clusters_nexora_api_v1_control_plane_clusters_get(self) -> Any:
        """List Clusters"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters")

    def list_comments_nexora_api_v1_product_collaboration_resource_type_resource_id_comments_get(self, resource_type: str, resource_id: str) -> Any:
        """List Comments"""
        return self.request("GET", "/nexora-api/v1/product/collaboration/{resource_type}/{resource_id}/comments".format(resource_type=resource_type, resource_id=resource_id))

    def list_communication_templates_nexora_api_v1_incidents_communications_templates_get(self) -> Any:
        """List Communication Templates"""
        return self.request("GET", "/nexora-api/v1/incidents/communications/templates")

    def list_communication_templates_nexora_api_v1_pilot_communications_templates_get(self) -> Any:
        """List Communication Templates"""
        return self.request("GET", "/nexora-api/v1/pilot/communications/templates")

    def list_communications_nexora_api_v1_customer_pilot_communications_get(self) -> Any:
        """List Communications"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/communications")

    def list_communications_nexora_api_v1_incidents_communications_get(self, *, params: dict | None = None) -> Any:
        """List Communications"""
        return self.request("GET", "/nexora-api/v1/incidents/communications", params=params)

    def list_connections_nexora_api_v1_auth_sso_connections_get(self) -> Any:
        """List Connections"""
        return self.request("GET", "/nexora-api/v1/auth/sso/connections")

    def list_connections_nexora_api_v1_integrations_connections_get(self) -> Any:
        """List Connections"""
        return self.request("GET", "/nexora-api/v1/integrations/connections")

    def list_conversations_nexora_api_v1_copilot_conversations_get(self) -> Any:
        """List Conversations"""
        return self.request("GET", "/nexora-api/v1/copilot/conversations")

    def list_correlations_nexora_api_v1_observability_correlation_get(self) -> Any:
        """List Correlations"""
        return self.request("GET", "/nexora-api/v1/observability/correlation")

    def list_credentials_nexora_api_v1_credentials_get(self) -> Any:
        """List Credentials"""
        return self.request("GET", "/nexora-api/v1/credentials")

    def list_dashboards_nexora_api_v1_product_dashboards_get(self) -> Any:
        """List Dashboards"""
        return self.request("GET", "/nexora-api/v1/product/dashboards")

    def list_dead_letter_nexora_api_v1_jobs_dead_letter_get(self, *, params: dict | None = None) -> Any:
        """List Dead Letter"""
        return self.request("GET", "/nexora-api/v1/jobs/dead-letter", params=params)

    def list_dead_letters_nexora_api_v1_monitoring_dead_letters_get(self, *, params: dict | None = None) -> Any:
        """List Dead Letters"""
        return self.request("GET", "/nexora-api/v1/monitoring/dead-letters", params=params)

    def list_demo_organizations_nexora_api_v1_demo_organizations_get(self) -> Any:
        """List Demo Organizations"""
        return self.request("GET", "/nexora-api/v1/demo-organizations")

    def list_dependencies_nexora_api_v1_service_dependencies_get(self) -> Any:
        """List Dependencies"""
        return self.request("GET", "/nexora-api/v1/service-dependencies")

    def list_deployment_runs_for_requirement_nexora_api_v1_agents_deployment_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Deployment Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/deployment/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_deployment_safety_analyses_nexora_api_v1_deployment_safety_analyses_get(self) -> Any:
        """List Deployment Safety Analyses"""
        return self.request("GET", "/nexora-api/v1/deployment-safety/analyses")

    def list_deployments_nexora_api_v1_delivery_deployments_get(self, *, params: dict | None = None) -> Any:
        """List Deployments"""
        return self.request("GET", "/nexora-api/v1/delivery/deployments", params=params)

    def list_deployments_nexora_api_v1_deployments_get(self, *, params: dict | None = None) -> Any:
        """List Deployments"""
        return self.request("GET", "/nexora-api/v1/deployments", params=params)

    def list_diagnostics_nexora_api_v1_control_plane_clusters_cluster_id_k8s_diagnostics_get(self, cluster_id: str) -> Any:
        """List Diagnostics"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/diagnostics".format(cluster_id=cluster_id))

    def list_docker_agent_runs_for_requirement_nexora_api_v1_agents_docker_agent_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Docker Agent Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/docker-agent/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_drift_nexora_api_v1_platform_engineering_drift_get(self) -> Any:
        """List Drift"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/drift")

    def list_environments_nexora_api_v1_delivery_environments_get(self) -> Any:
        """List Environments"""
        return self.request("GET", "/nexora-api/v1/delivery/environments")

    def list_environments_nexora_api_v1_platform_engineering_environments_get(self) -> Any:
        """List Environments"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/environments")

    def list_evaluations_nexora_api_v1_ai_evaluations_get(self, *, params: dict | None = None) -> Any:
        """List Evaluations"""
        return self.request("GET", "/nexora-api/v1/ai/evaluations", params=params)

    def list_events_nexora_api_v1_platform_events_get(self, *, params: dict | None = None) -> Any:
        """List Events"""
        return self.request("GET", "/nexora-api/v1/platform/events", params=params)

    def list_exceptions_nexora_api_v1_security_exceptions_get(self) -> Any:
        """List Exceptions"""
        return self.request("GET", "/nexora-api/v1/security/exceptions")

    def list_findings_nexora_api_v1_security_findings_get(self, *, params: dict | None = None) -> Any:
        """List Findings"""
        return self.request("GET", "/nexora-api/v1/security/findings", params=params)

    def list_forecasts_nexora_api_v1_capacity_forecasts_get(self, *, params: dict | None = None) -> Any:
        """List Forecasts"""
        return self.request("GET", "/nexora-api/v1/capacity/forecasts", params=params)

    def list_freeze_windows_nexora_api_v1_delivery_freeze_windows_get(self) -> Any:
        """List Freeze Windows"""
        return self.request("GET", "/nexora-api/v1/delivery/freeze-windows")

    def list_frontend_architect_runs_for_requirement_nexora_api_v1_agents_frontend_architect_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Frontend Architect Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-architect/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_frontend_code_review_runs_for_requirement_nexora_api_v1_agents_frontend_code_review_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Frontend Code Review Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-code-review/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_frontend_execution_runs_for_requirement_nexora_api_v1_agents_frontend_execution_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Frontend Execution Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-execution/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_frontend_v1_runs_for_requirement_nexora_api_v1_agents_frontend_v1_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Frontend V1 Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v1/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_frontend_v2_runs_for_requirement_nexora_api_v1_agents_frontend_v2_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Frontend V2 Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v2/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_frontend_v3_runs_for_requirement_nexora_api_v1_agents_frontend_v3_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Frontend V3 Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/frontend-v3/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_fullstack_assembly_runs_for_requirement_nexora_api_v1_agents_fullstack_assembly_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Fullstack Assembly Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/fullstack-assembly/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_gitops_nexora_api_v1_control_plane_clusters_cluster_id_gitops_get(self, cluster_id: str) -> Any:
        """List Gitops"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/gitops".format(cluster_id=cluster_id))

    def list_gitops_nexora_api_v1_delivery_gitops_get(self) -> Any:
        """List Gitops"""
        return self.request("GET", "/nexora-api/v1/delivery/gitops")

    def list_goals_nexora_api_v1_operator_goals_get(self) -> Any:
        """List Goals"""
        return self.request("GET", "/nexora-api/v1/operator/goals")

    def list_golden_templates_nexora_api_v1_platform_engineering_golden_templates_get(self) -> Any:
        """List Golden Templates"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/golden-templates")

    def list_groups_nexora_api_v1_scim_v2_groups_get(self) -> Any:
        """List Groups"""
        return self.request("GET", "/nexora-api/v1/scim/v2/Groups")

    def list_helm_nexora_api_v1_control_plane_clusters_cluster_id_helm_get(self, cluster_id: str) -> Any:
        """List Helm"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/helm".format(cluster_id=cluster_id))

    def list_human_guides_nexora_api_v1_customer_success_human_guides_get(self) -> Any:
        """List Human Guides"""
        return self.request("GET", "/nexora-api/v1/customer-success/human-guides")

    def list_inbox_nexora_api_v1_product_inbox_get(self, *, params: dict | None = None) -> Any:
        """List Inbox"""
        return self.request("GET", "/nexora-api/v1/product/inbox", params=params)

    def list_incident_comments_nexora_api_v1_incidents_investigation_id_comments_get(self, investigation_id: str) -> Any:
        """List Incident Comments"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/comments".format(investigation_id=investigation_id))

    def list_incident_events_nexora_api_v1_incidents_investigation_id_events_get(self, investigation_id: str) -> Any:
        """List Incident Events"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/events".format(investigation_id=investigation_id))

    def list_incident_tasks_nexora_api_v1_incidents_investigation_id_tasks_get(self, investigation_id: str) -> Any:
        """List Incident Tasks"""
        return self.request("GET", "/nexora-api/v1/incidents/{investigation_id}/tasks".format(investigation_id=investigation_id))

    def list_incidents_nexora_api_v1_incidents_get(self, *, params: dict | None = None) -> Any:
        """List Incidents"""
        return self.request("GET", "/nexora-api/v1/incidents", params=params)

    def list_infrastructure_architect_runs_for_requirement_nexora_api_v1_agents_infrastructure_architect_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Infrastructure Architect Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/infrastructure-architect/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_installed_plugins_nexora_api_v1_platform_plugins_get(self) -> Any:
        """List Installed Plugins"""
        return self.request("GET", "/nexora-api/v1/platform/plugins")

    def list_integration_providers_nexora_api_v1_integrations_providers_get(self) -> Any:
        """List Integration Providers"""
        return self.request("GET", "/nexora-api/v1/integrations/providers")

    def list_integration_test_runs_for_requirement_nexora_api_v1_agents_integration_tests_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Integration Test Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/integration-tests/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_integrations_nexora_api_v1_integrations_get(self) -> Any:
        """List Integrations"""
        return self.request("GET", "/nexora-api/v1/integrations")

    def list_integrations_nexora_api_v1_observability_integrations_get(self) -> Any:
        """List Integrations"""
        return self.request("GET", "/nexora-api/v1/observability/integrations")

    def list_investigations_nexora_api_v1_security_investigations_get(self) -> Any:
        """List Investigations"""
        return self.request("GET", "/nexora-api/v1/security/investigations")

    def list_invoices_nexora_api_v1_billing_invoices_get(self, *, params: dict | None = None) -> Any:
        """List Invoices"""
        return self.request("GET", "/nexora-api/v1/billing/invoices", params=params)

    def list_jobs_nexora_api_v1_jobs_get(self, *, params: dict | None = None) -> Any:
        """List Jobs"""
        return self.request("GET", "/nexora-api/v1/jobs", params=params)

    def list_journeys_nexora_api_v1_customer_success_journeys_get(self) -> Any:
        """List Journeys"""
        return self.request("GET", "/nexora-api/v1/customer-success/journeys")

    def list_kubernetes_runs_for_requirement_nexora_api_v1_agents_kubernetes_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Kubernetes Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/kubernetes/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_learning_paths_nexora_api_v1_customer_success_learning_paths_get(self, *, params: dict | None = None) -> Any:
        """List Learning Paths"""
        return self.request("GET", "/nexora-api/v1/customer-success/learning-paths", params=params)

    def list_linked_incidents_nexora_api_v1_delivery_linked_incidents_get(self, *, params: dict | None = None) -> Any:
        """List Linked Incidents"""
        return self.request("GET", "/nexora-api/v1/delivery/linked-incidents", params=params)

    def list_live_operations_nexora_api_v1_pilot_live_operations_get(self) -> Any:
        """List Live Operations"""
        return self.request("GET", "/nexora-api/v1/pilot/live-operations")

    def list_logs_nexora_api_v1_audit_logs_get(self, *, params: dict | None = None) -> Any:
        """List Logs"""
        return self.request("GET", "/nexora-api/v1/audit/logs", params=params)

    def list_major_incidents_nexora_api_v1_incidents_major_get(self) -> Any:
        """List Major Incidents"""
        return self.request("GET", "/nexora-api/v1/incidents/major")

    def list_mcp_servers_nexora_api_v1_ai_mcp_servers_get(self) -> Any:
        """List Mcp Servers"""
        return self.request("GET", "/nexora-api/v1/ai/mcp/servers")

    def list_memory_nexora_api_v1_ai_memory_get(self, *, params: dict | None = None) -> Any:
        """List Memory"""
        return self.request("GET", "/nexora-api/v1/ai/memory", params=params)

    def list_modules_nexora_api_v1_customer_success_modules_get(self) -> Any:
        """List Modules"""
        return self.request("GET", "/nexora-api/v1/customer-success/modules")

    def list_namespaces_nexora_api_v1_control_plane_clusters_cluster_id_k8s_namespaces_get(self, cluster_id: str) -> Any:
        """List Namespaces"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/namespaces".format(cluster_id=cluster_id))

    def list_networking_nexora_api_v1_control_plane_clusters_cluster_id_k8s_networking_net_kind_get(self, cluster_id: str, net_kind: str, *, params: dict | None = None) -> Any:
        """List Networking"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/networking/{net_kind}".format(cluster_id=cluster_id, net_kind=net_kind), params=params)

    def list_nodes_nexora_api_v1_control_plane_clusters_cluster_id_k8s_nodes_get(self, cluster_id: str) -> Any:
        """List Nodes"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/nodes".format(cluster_id=cluster_id))

    def list_notifications_nexora_api_v1_customer_pilot_notifications_get(self) -> Any:
        """List Notifications"""
        return self.request("GET", "/nexora-api/v1/customer-pilot/notifications")

    def list_notifications_nexora_api_v1_platform_notifications_get(self, *, params: dict | None = None) -> Any:
        """List Notifications"""
        return self.request("GET", "/nexora-api/v1/platform/notifications", params=params)

    def list_observability_runs_for_requirement_nexora_api_v1_agents_observability_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Observability Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/observability/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_onboarding_paths_nexora_api_v1_pilot_onboarding_paths_get(self) -> Any:
        """List Onboarding Paths"""
        return self.request("GET", "/nexora-api/v1/pilot/onboarding-paths")

    def list_operation_catalog_nexora_api_v1_pilot_operations_catalog_get(self) -> Any:
        """List Operation Catalog"""
        return self.request("GET", "/nexora-api/v1/pilot/operations/catalog")

    def list_operations_nexora_api_v1_control_plane_operations_get(self) -> Any:
        """List Operations"""
        return self.request("GET", "/nexora-api/v1/control-plane/operations")

    def list_operations_nexora_api_v1_delivery_operations_get(self) -> Any:
        """List Operations"""
        return self.request("GET", "/nexora-api/v1/delivery/operations")

    def list_org_keys_nexora_api_v1_api_keys_organization_get(self) -> Any:
        """List Org Keys"""
        return self.request("GET", "/nexora-api/v1/api-keys/organization")

    def list_organization_invitations_nexora_api_v1_organizations_organization_id_invitations_get(self, organization_id: str, *, params: dict | None = None) -> Any:
        """List Organization Invitations"""
        return self.request("GET", "/nexora-api/v1/organizations/{organization_id}/invitations".format(organization_id=organization_id), params=params)

    def list_organization_members_nexora_api_v1_organizations_organization_id_members_get(self, organization_id: str, *, params: dict | None = None) -> Any:
        """List Organization Members"""
        return self.request("GET", "/nexora-api/v1/organizations/{organization_id}/members".format(organization_id=organization_id), params=params)

    def list_organizations_nexora_api_v1_organizations_get(self, *, params: dict | None = None) -> Any:
        """List Organizations"""
        return self.request("GET", "/nexora-api/v1/organizations", params=params)

    def list_performance_test_runs_for_requirement_nexora_api_v1_agents_performance_tests_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Performance Test Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/performance-tests/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_personal_keys_nexora_api_v1_api_keys_personal_get(self) -> Any:
        """List Personal Keys"""
        return self.request("GET", "/nexora-api/v1/api-keys/personal")

    def list_pipeline_runs_nexora_api_v1_delivery_pipeline_runs_get(self) -> Any:
        """List Pipeline Runs"""
        return self.request("GET", "/nexora-api/v1/delivery/pipeline-runs")

    def list_pipelines_nexora_api_v1_delivery_pipelines_get(self) -> Any:
        """List Pipelines"""
        return self.request("GET", "/nexora-api/v1/delivery/pipelines")

    def list_plans_nexora_api_v1_billing_plans_get(self) -> Any:
        """List Plans"""
        return self.request("GET", "/nexora-api/v1/billing/plans")

    def list_playbooks_nexora_api_v1_customer_success_playbooks_get(self) -> Any:
        """List Playbooks"""
        return self.request("GET", "/nexora-api/v1/customer-success/playbooks")

    def list_playbooks_nexora_api_v1_test_playbooks_get(self, *, params: dict | None = None) -> Any:
        """List Playbooks"""
        return self.request("GET", "/nexora-api/v1/test-playbooks", params=params)

    def list_pods_nexora_api_v1_control_plane_clusters_cluster_id_k8s_pods_get(self, cluster_id: str, *, params: dict | None = None) -> Any:
        """List Pods"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/pods".format(cluster_id=cluster_id), params=params)

    def list_policies_nexora_api_v1_control_plane_clusters_cluster_id_policies_get(self, cluster_id: str) -> Any:
        """List Policies"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/policies".format(cluster_id=cluster_id))

    def list_policies_nexora_api_v1_oncall_escalation_policies_get(self) -> Any:
        """List Policies"""
        return self.request("GET", "/nexora-api/v1/oncall/escalation-policies")

    def list_policies_nexora_api_v1_operator_policies_get(self) -> Any:
        """List Policies"""
        return self.request("GET", "/nexora-api/v1/operator/policies")

    def list_postmortems_nexora_api_v1_postmortems_get(self, *, params: dict | None = None) -> Any:
        """List Postmortems"""
        return self.request("GET", "/nexora-api/v1/postmortems", params=params)

    def list_projects_nexora_api_v1_projects_get(self, *, params: dict | None = None) -> Any:
        """List Projects"""
        return self.request("GET", "/nexora-api/v1/projects", params=params)

    def list_promotion_policies_nexora_api_v1_delivery_promotion_policies_get(self) -> Any:
        """List Promotion Policies"""
        return self.request("GET", "/nexora-api/v1/delivery/promotion-policies")

    def list_prompt_versions_nexora_api_v1_ai_prompts_key_versions_get(self, key: str) -> Any:
        """List Prompt Versions"""
        return self.request("GET", "/nexora-api/v1/ai/prompts/{key}/versions".format(key=key))

    def list_proposals_nexora_api_v1_operator_proposals_get(self) -> Any:
        """List Proposals"""
        return self.request("GET", "/nexora-api/v1/operator/proposals")

    def list_provider_catalog_nexora_api_v1_security_providers_get(self) -> Any:
        """List Provider Catalog"""
        return self.request("GET", "/nexora-api/v1/security/providers")

    def list_provider_configs_nexora_api_v1_security_providers_config_get(self) -> Any:
        """List Provider Configs"""
        return self.request("GET", "/nexora-api/v1/security/providers/config")

    def list_providers_nexora_api_v1_ai_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/ai/providers")

    def list_providers_nexora_api_v1_auth_sso_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/auth/sso/providers")

    def list_providers_nexora_api_v1_control_plane_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/control-plane/providers")

    def list_providers_nexora_api_v1_delivery_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/delivery/providers")

    def list_providers_nexora_api_v1_observability_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/observability/providers")

    def list_providers_nexora_api_v1_onboarding_integrations_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/providers")

    def list_providers_nexora_api_v1_platform_engineering_providers_get(self) -> Any:
        """List Providers"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/providers")

    def list_provisions_nexora_api_v1_platform_engineering_provisions_get(self) -> Any:
        """List Provisions"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/provisions")

    def list_qa_approval_runs_for_requirement_nexora_api_v1_agents_qa_approvals_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Qa Approval Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/qa-approvals/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_qa_architect_runs_for_requirement_nexora_api_v1_agents_qa_architect_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Qa Architect Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/qa-architect/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_rca_hypotheses_nexora_api_v1_sre_rca_incident_id_hypotheses_get(self, incident_id: str) -> Any:
        """List Rca Hypotheses"""
        return self.request("GET", "/nexora-api/v1/sre/rca/{incident_id}/hypotheses".format(incident_id=incident_id))

    def list_readiness_connections_nexora_api_v1_integrations_connections_readiness_get(self, *, params: dict | None = None) -> Any:
        """List Readiness Connections"""
        return self.request("GET", "/nexora-api/v1/integrations/connections/readiness", params=params)

    def list_recommendations_nexora_api_v1_operator_recommendations_get(self) -> Any:
        """List Recommendations"""
        return self.request("GET", "/nexora-api/v1/operator/recommendations")

    def list_recommendations_nexora_api_v1_sre_recommendations_resource_type_resource_id_get(self, resource_type: str, resource_id: str) -> Any:
        """List Recommendations"""
        return self.request("GET", "/nexora-api/v1/sre/recommendations/{resource_type}/{resource_id}".format(resource_type=resource_type, resource_id=resource_id))

    def list_release_reliability_nexora_api_v1_delivery_release_reliability_get(self, *, params: dict | None = None) -> Any:
        """List Release Reliability"""
        return self.request("GET", "/nexora-api/v1/delivery/release-reliability", params=params)

    def list_releases_nexora_api_v1_delivery_releases_get(self) -> Any:
        """List Releases"""
        return self.request("GET", "/nexora-api/v1/delivery/releases")

    def list_releases_nexora_api_v1_releases_get(self, *, params: dict | None = None) -> Any:
        """List Releases"""
        return self.request("GET", "/nexora-api/v1/releases", params=params)

    def list_remediations_nexora_api_v1_security_remediation_get(self) -> Any:
        """List Remediations"""
        return self.request("GET", "/nexora-api/v1/security/remediation")

    def list_report_schedules_nexora_api_v1_product_reports_schedules_get(self) -> Any:
        """List Report Schedules"""
        return self.request("GET", "/nexora-api/v1/product/reports/schedules")

    def list_reports_nexora_api_v1_executive_reports_get(self, *, params: dict | None = None) -> Any:
        """List Reports"""
        return self.request("GET", "/nexora-api/v1/executive-reports", params=params)

    def list_repositories_nexora_api_v1_delivery_repositories_get(self) -> Any:
        """List Repositories"""
        return self.request("GET", "/nexora-api/v1/delivery/repositories")

    def list_repositories_nexora_api_v1_platform_engineering_repositories_get(self) -> Any:
        """List Repositories"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/repositories")

    def list_requirements_nexora_api_v1_requirements_get(self, *, params: dict | None = None) -> Any:
        """List Requirements"""
        return self.request("GET", "/nexora-api/v1/requirements", params=params)

    def list_run_approvals_nexora_api_v1_workflow_runs_run_id_approvals_get(self, run_id: str) -> Any:
        """List Run Approvals"""
        return self.request("GET", "/nexora-api/v1/workflow-runs/{run_id}/approvals".format(run_id=run_id))

    def list_runbooks_nexora_api_v1_runbooks_get(self, *, params: dict | None = None) -> Any:
        """List Runbooks"""
        return self.request("GET", "/nexora-api/v1/runbooks", params=params)

    def list_runs_nexora_api_v1_platform_engineering_runs_get(self, *, params: dict | None = None) -> Any:
        """List Runs"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/runs", params=params)

    def list_saved_searches_nexora_api_v1_observability_logs_saved_searches_get(self) -> Any:
        """List Saved Searches"""
        return self.request("GET", "/nexora-api/v1/observability/logs/saved-searches")

    def list_saved_views_nexora_api_v1_product_views_get(self, *, params: dict | None = None) -> Any:
        """List Saved Views"""
        return self.request("GET", "/nexora-api/v1/product/views", params=params)

    def list_sbom_components_nexora_api_v1_security_sbom_components_get(self, *, params: dict | None = None) -> Any:
        """List Sbom Components"""
        return self.request("GET", "/nexora-api/v1/security/sbom/components", params=params)

    def list_scan_runs_nexora_api_v1_security_scan_runs_get(self, *, params: dict | None = None) -> Any:
        """List Scan Runs"""
        return self.request("GET", "/nexora-api/v1/security/scan-runs", params=params)

    def list_scans_nexora_api_v1_security_scans_get(self) -> Any:
        """List Scans"""
        return self.request("GET", "/nexora-api/v1/security/scans")

    def list_scenario_runs_nexora_api_v1_demo_scenarios_scenario_id_runs_get(self, scenario_id: str) -> Any:
        """List Scenario Runs"""
        return self.request("GET", "/nexora-api/v1/demo-scenarios/{scenario_id}/runs".format(scenario_id=scenario_id))

    def list_scenarios_nexora_api_v1_demo_scenarios_get(self) -> Any:
        """List Scenarios"""
        return self.request("GET", "/nexora-api/v1/demo-scenarios")

    def list_schedules_nexora_api_v1_oncall_schedules_get(self) -> Any:
        """List Schedules"""
        return self.request("GET", "/nexora-api/v1/oncall/schedules")

    def list_scim_tokens_nexora_api_v1_scim_v2_admin_tokens_get(self, *, params: dict | None = None) -> Any:
        """List Scim Tokens"""
        return self.request("GET", "/nexora-api/v1/scim/v2/admin/tokens", params=params)

    def list_scopes_nexora_api_v1_identity_scopes_get(self) -> Any:
        """List Scopes"""
        return self.request("GET", "/nexora-api/v1/identity/scopes")

    def list_secrets_nexora_api_v1_platform_engineering_secrets_get(self) -> Any:
        """List Secrets"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/secrets")

    def list_security_scans_nexora_api_v1_delivery_security_scans_get(self) -> Any:
        """List Security Scans"""
        return self.request("GET", "/nexora-api/v1/delivery/security/scans")

    def list_security_test_runs_for_requirement_nexora_api_v1_agents_security_tests_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Security Test Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/security-tests/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_service_account_keys_nexora_api_v1_service_accounts_sa_id_keys_get(self, sa_id: str) -> Any:
        """List Service Account Keys"""
        return self.request("GET", "/nexora-api/v1/service-accounts/{sa_id}/keys".format(sa_id=sa_id))

    def list_service_accounts_nexora_api_v1_service_accounts_get(self) -> Any:
        """List Service Accounts"""
        return self.request("GET", "/nexora-api/v1/service-accounts")

    def list_service_owners_nexora_api_v1_oncall_service_owners_get(self) -> Any:
        """List Service Owners"""
        return self.request("GET", "/nexora-api/v1/oncall/service-owners")

    def list_services_nexora_api_v1_services_get(self) -> Any:
        """List Services"""
        return self.request("GET", "/nexora-api/v1/services")

    def list_sessions_nexora_api_v1_auth_sessions_get(self) -> Any:
        """List Sessions"""
        return self.request("GET", "/nexora-api/v1/auth/sessions")

    def list_sessions_nexora_api_v1_onboarding_integrations_sessions_get(self) -> Any:
        """List Sessions"""
        return self.request("GET", "/nexora-api/v1/onboarding/integrations/sessions")

    def list_sessions_nexora_api_v1_sessions_get(self) -> Any:
        """List Sessions"""
        return self.request("GET", "/nexora-api/v1/sessions")

    def list_simulations_nexora_api_v1_operator_simulations_get(self) -> Any:
        """List Simulations"""
        return self.request("GET", "/nexora-api/v1/operator/simulations")

    def list_slos_nexora_api_v1_services_service_id_slos_get(self, service_id: str) -> Any:
        """List Slos"""
        return self.request("GET", "/nexora-api/v1/services/{service_id}/slos".format(service_id=service_id))

    def list_snapshots_nexora_api_v1_architecture_get(self) -> Any:
        """List Snapshots"""
        return self.request("GET", "/nexora-api/v1/architecture")

    def list_source_connections_nexora_api_v1_delivery_source_connections_get(self) -> Any:
        """List Source Connections"""
        return self.request("GET", "/nexora-api/v1/delivery/source-connections")

    def list_sre_approval_runs_for_requirement_nexora_api_v1_agents_sre_approval_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Sre Approval Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/sre-approval/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_stacks_nexora_api_v1_platform_engineering_stacks_get(self) -> Any:
        """List Stacks"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/stacks")

    def list_status_pages_nexora_api_v1_incidents_status_pages_get(self) -> Any:
        """List Status Pages"""
        return self.request("GET", "/nexora-api/v1/incidents/status-pages")

    def list_storage_nexora_api_v1_control_plane_clusters_cluster_id_k8s_storage_storage_kind_get(self, cluster_id: str, storage_kind: str, *, params: dict | None = None) -> Any:
        """List Storage"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/storage/{storage_kind}".format(cluster_id=cluster_id, storage_kind=storage_kind), params=params)

    def list_success_nexora_api_v1_customer_success_success_center_get(self) -> Any:
        """List Success"""
        return self.request("GET", "/nexora-api/v1/customer-success/success-center")

    def list_team_audit_events_nexora_api_v1_teams_team_id_audit_get(self, team_id: str) -> Any:
        """List Team Audit Events"""
        return self.request("GET", "/nexora-api/v1/teams/{team_id}/audit".format(team_id=team_id))

    def list_team_templates_nexora_api_v1_team_templates_get(self, *, params: dict | None = None) -> Any:
        """List Team Templates"""
        return self.request("GET", "/nexora-api/v1/team-templates", params=params)

    def list_teams_nexora_api_v1_teams_get(self, *, params: dict | None = None) -> Any:
        """List Teams"""
        return self.request("GET", "/nexora-api/v1/teams", params=params)

    def list_templates_nexora_api_v1_demo_organizations_templates_get(self) -> Any:
        """List Templates"""
        return self.request("GET", "/nexora-api/v1/demo-organizations/templates")

    def list_templates_nexora_api_v1_platform_engineering_templates_get(self) -> Any:
        """List Templates"""
        return self.request("GET", "/nexora-api/v1/platform-engineering/templates")

    def list_tools_nexora_api_v1_ai_tools_get(self) -> Any:
        """List Tools"""
        return self.request("GET", "/nexora-api/v1/ai/tools")

    def list_tour_guides_nexora_api_v1_customer_success_tour_guides_get(self) -> Any:
        """List Tour Guides"""
        return self.request("GET", "/nexora-api/v1/customer-success/tour-guides")

    def list_tours_nexora_api_v1_customer_success_tours_get(self, *, params: dict | None = None) -> Any:
        """List Tours"""
        return self.request("GET", "/nexora-api/v1/customer-success/tours", params=params)

    def list_tours_nexora_api_v1_product_tours_get(self, *, params: dict | None = None) -> Any:
        """List Tours"""
        return self.request("GET", "/nexora-api/v1/product-tours", params=params)

    def list_uiux_runs_for_requirement_nexora_api_v1_agents_uiux_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Uiux Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/uiux/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_unit_test_runs_for_requirement_nexora_api_v1_agents_unit_tests_requirement_id_get(self, requirement_id: str, *, params: dict | None = None) -> Any:
        """List Unit Test Runs For Requirement"""
        return self.request("GET", "/nexora-api/v1/agents/unit-tests/{requirement_id}".format(requirement_id=requirement_id), params=params)

    def list_users_nexora_api_v1_scim_v2_users_get(self) -> Any:
        """List Users"""
        return self.request("GET", "/nexora-api/v1/scim/v2/Users")

    def list_variables_nexora_api_v1_org_config_variables_get(self, *, params: dict | None = None) -> Any:
        """List Variables"""
        return self.request("GET", "/nexora-api/v1/org-config/variables", params=params)

    def list_verifications_nexora_api_v1_customer_success_verifications_get(self, *, params: dict | None = None) -> Any:
        """List Verifications"""
        return self.request("GET", "/nexora-api/v1/customer-success/verifications", params=params)

    def list_war_rooms_nexora_api_v1_war_rooms_get(self) -> Any:
        """List War Rooms"""
        return self.request("GET", "/nexora-api/v1/war-rooms")

    def list_webhooks_nexora_api_v1_billing_webhooks_get(self) -> Any:
        """List Webhooks"""
        return self.request("GET", "/nexora-api/v1/billing/webhooks")

    def list_workflow_approvals_nexora_api_v1_workflow_approvals_get(self, *, params: dict | None = None) -> Any:
        """List Workflow Approvals"""
        return self.request("GET", "/nexora-api/v1/workflow-approvals", params=params)

    def list_workflow_audit_nexora_api_v1_workflows_workflow_id_audit_get(self, workflow_id: str) -> Any:
        """List Workflow Audit"""
        return self.request("GET", "/nexora-api/v1/workflows/{workflow_id}/audit".format(workflow_id=workflow_id))

    def list_workflow_execution_audit_nexora_api_v1_workflow_executions_execution_id_audit_get(self, execution_id: str) -> Any:
        """List Workflow Execution Audit"""
        return self.request("GET", "/nexora-api/v1/workflow-executions/{execution_id}/audit".format(execution_id=execution_id))

    def list_workflow_executions_nexora_api_v1_workflow_executions_get(self, *, params: dict | None = None) -> Any:
        """List Workflow Executions"""
        return self.request("GET", "/nexora-api/v1/workflow-executions", params=params)

    def list_workflow_schedules_nexora_api_v1_ai_team_workflow_schedules_get(self, *, params: dict | None = None) -> Any:
        """List Workflow Schedules"""
        return self.request("GET", "/nexora-api/v1/ai-team-workflow-schedules", params=params)

    def list_workflow_templates_nexora_api_v1_workflow_templates_get(self, *, params: dict | None = None) -> Any:
        """List Workflow Templates"""
        return self.request("GET", "/nexora-api/v1/workflow-templates", params=params)

    def list_workflows_nexora_api_v1_workflows_get(self, *, params: dict | None = None) -> Any:
        """List Workflows"""
        return self.request("GET", "/nexora-api/v1/workflows", params=params)

    def list_workloads_nexora_api_v1_control_plane_clusters_cluster_id_k8s_workloads_workload_kind_get(self, cluster_id: str, workload_kind: str, *, params: dict | None = None) -> Any:
        """List Workloads"""
        return self.request("GET", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/workloads/{workload_kind}".format(cluster_id=cluster_id, workload_kind=workload_kind), params=params)

    def list_workspaces_nexora_api_v1_workspaces_get(self, *, params: dict | None = None) -> Any:
        """List Workspaces"""
        return self.request("GET", "/nexora-api/v1/workspaces", params=params)

    def livez_livez_get(self) -> Any:
        """Livez"""
        return self.request("GET", "/livez")

    def login_nexora_api_v1_auth_login_post(self, *, json: Any = None) -> Any:
        """Login"""
        return self.request("POST", "/nexora-api/v1/auth/login", json=json)

    def logout_all_nexora_api_v1_sessions_logout_all_post(self) -> Any:
        """Logout All"""
        return self.request("POST", "/nexora-api/v1/sessions/logout-all")

    def logout_nexora_api_v1_auth_logout_post(self) -> Any:
        """Logout"""
        return self.request("POST", "/nexora-api/v1/auth/logout")

    def maintenance_center_nexora_api_v1_ops_workspace_maintenance_get(self) -> Any:
        """Maintenance Center"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/maintenance")

    def mark_all_inbox_read_nexora_api_v1_product_inbox_read_all_post(self) -> Any:
        """Mark All Inbox Read"""
        return self.request("POST", "/nexora-api/v1/product/inbox/read-all")

    def mark_inbox_read_nexora_api_v1_product_inbox_note_id_read_post(self, note_id: str) -> Any:
        """Mark Inbox Read"""
        return self.request("POST", "/nexora-api/v1/product/inbox/{note_id}/read".format(note_id=note_id))

    def mark_notification_read_nexora_api_v1_customer_pilot_notifications_notification_id_read_post(self, notification_id: str) -> Any:
        """Mark Notification Read"""
        return self.request("POST", "/nexora-api/v1/customer-pilot/notifications/{notification_id}/read".format(notification_id=notification_id))

    def marketplace_discover_nexora_api_v1_ga_marketplace_get(self) -> Any:
        """Marketplace Discover"""
        return self.request("GET", "/nexora-api/v1/ga/marketplace")

    def marketplace_install_nexora_api_v1_ga_marketplace_slug_install_post(self, slug: str) -> Any:
        """Marketplace Install"""
        return self.request("POST", "/nexora-api/v1/ga/marketplace/{slug}/install".format(slug=slug))

    def marketplace_upgrade_nexora_api_v1_ga_marketplace_slug_upgrade_post(self, slug: str) -> Any:
        """Marketplace Upgrade"""
        return self.request("POST", "/nexora-api/v1/ga/marketplace/{slug}/upgrade".format(slug=slug))

    def mcp_manifest_nexora_api_v1_ai_mcp_manifest_get(self) -> Any:
        """Mcp Manifest"""
        return self.request("GET", "/nexora-api/v1/ai/mcp/manifest")

    def me_nexora_api_v1_auth_me_get(self) -> Any:
        """Me"""
        return self.request("GET", "/nexora-api/v1/auth/me")

    def mfa_status_nexora_api_v1_auth_mfa_status_get(self) -> Any:
        """Mfa Status"""
        return self.request("GET", "/nexora-api/v1/auth/mfa/status")

    def migration_preview_nexora_api_v1_ga_upgrade_migration_preview_get(self) -> Any:
        """Migration Preview"""
        return self.request("GET", "/nexora-api/v1/ga/upgrade/migration-preview")

    def mtta_nexora_api_v1_oncall_mtta_get(self) -> Any:
        """Mtta"""
        return self.request("GET", "/nexora-api/v1/oncall/mtta")

    def my_activity_nexora_api_v1_platform_activity_me_get(self, *, params: dict | None = None) -> Any:
        """My Activity"""
        return self.request("GET", "/nexora-api/v1/platform/activity/me", params=params)

    def my_license_nexora_api_v1_billing_license_get(self) -> Any:
        """My License"""
        return self.request("GET", "/nexora-api/v1/billing/license")

    def my_work_nexora_api_v1_ops_workspace_my_work_get(self) -> Any:
        """My Work"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/my-work")

    def navigation_health_nexora_api_v1_customer_success_navigation_health_get(self) -> Any:
        """Navigation Health"""
        return self.request("GET", "/nexora-api/v1/customer-success/navigation-health")

    def navigation_maps_nexora_api_v1_customer_success_navigation_maps_get(self) -> Any:
        """Navigation Maps"""
        return self.request("GET", "/nexora-api/v1/customer-success/navigation-maps")

    def oncall_dashboard_nexora_api_v1_incidents_oncall_get(self) -> Any:
        """Oncall Dashboard"""
        return self.request("GET", "/nexora-api/v1/incidents/oncall")

    def operational_kpis_nexora_api_v1_ops_workspace_kpis_get(self, *, params: dict | None = None) -> Any:
        """Operational Kpis"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/kpis", params=params)

    def operations_calendar_nexora_api_v1_ops_workspace_calendar_get(self) -> Any:
        """Operations Calendar"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/calendar")

    def operations_queue_nexora_api_v1_ops_workspace_queue_get(self) -> Any:
        """Operations Queue"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/queue")

    def ops_center_nexora_api_v1_sre_ops_center_get(self) -> Any:
        """Ops Center"""
        return self.request("GET", "/nexora-api/v1/sre/ops-center")

    def ops_diagnostics_nexora_api_v1_ops_diagnostics_get(self) -> Any:
        """Ops Diagnostics"""
        return self.request("GET", "/nexora-api/v1/ops/diagnostics")

    def org_usage_report_nexora_api_v1_billing_admin_orgs_org_id_usage_report_get(self, org_id: str) -> Any:
        """Org Usage Report"""
        return self.request("GET", "/nexora-api/v1/billing/admin/orgs/{org_id}/usage-report".format(org_id=org_id))

    def override_remediation_action_nexora_api_v1_remediation_actions_action_id_override_post(self, action_id: str, *, json: Any = None) -> Any:
        """Override Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/override".format(action_id=action_id), json=json)

    def overview_nexora_api_v1_security_overview_get(self) -> Any:
        """Overview"""
        return self.request("GET", "/nexora-api/v1/security/overview")

    def patch_group_nexora_api_v1_scim_v2_groups_scim_id_patch(self, scim_id: str) -> Any:
        """Patch Group"""
        return self.request("PATCH", "/nexora-api/v1/scim/v2/Groups/{scim_id}".format(scim_id=scim_id))

    def patch_user_nexora_api_v1_scim_v2_users_scim_id_patch(self, scim_id: str) -> Any:
        """Patch User"""
        return self.request("PATCH", "/nexora-api/v1/scim/v2/Users/{scim_id}".format(scim_id=scim_id))

    def pause_remediation_action_nexora_api_v1_remediation_actions_action_id_pause_post(self, action_id: str, *, json: Any = None) -> Any:
        """Pause Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/pause".format(action_id=action_id), json=json)

    def pause_rollout_nexora_api_v1_delivery_release_reliability_reliability_id_pause_post(self, reliability_id: str) -> Any:
        """Pause Rollout"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/pause".format(reliability_id=reliability_id))

    def personas_nexora_api_v1_sales_personas_get(self) -> Any:
        """Personas"""
        return self.request("GET", "/nexora-api/v1/sales/personas")

    def pin_inbox_nexora_api_v1_product_inbox_note_id_pin_post(self, note_id: str, *, params: dict | None = None) -> Any:
        """Pin Inbox"""
        return self.request("POST", "/nexora-api/v1/product/inbox/{note_id}/pin".format(note_id=note_id), params=params)

    def playbook_export_nexora_api_v1_customer_success_playbooks_key_export_get(self, key: str, *, params: dict | None = None) -> Any:
        """Playbook Export"""
        return self.request("GET", "/nexora-api/v1/customer-success/playbooks/{key}/export".format(key=key), params=params)

    def playbook_manual_nexora_api_v1_customer_success_playbooks_key_manual_get(self, key: str) -> Any:
        """Playbook Manual"""
        return self.request("GET", "/nexora-api/v1/customer-success/playbooks/{key}/manual".format(key=key))

    def playbook_manuals_nexora_api_v1_customer_success_playbook_manuals_get(self) -> Any:
        """Playbook Manuals"""
        return self.request("GET", "/nexora-api/v1/customer-success/playbook-manuals")

    def playground_models_nexora_api_v1_ai_playground_models_post(self, *, json: Any = None) -> Any:
        """Playground Models"""
        return self.request("POST", "/nexora-api/v1/ai/playground/models", json=json)

    def playground_prompt_nexora_api_v1_ai_playground_prompt_post(self, *, json: Any = None) -> Any:
        """Playground Prompt"""
        return self.request("POST", "/nexora-api/v1/ai/playground/prompt", json=json)

    def playground_providers_nexora_api_v1_ai_playground_providers_post(self, *, json: Any = None) -> Any:
        """Playground Providers"""
        return self.request("POST", "/nexora-api/v1/ai/playground/providers", json=json)

    def playground_temperatures_nexora_api_v1_ai_playground_temperatures_post(self, *, json: Any = None) -> Any:
        """Playground Temperatures"""
        return self.request("POST", "/nexora-api/v1/ai/playground/temperatures", json=json)

    def plugin_capabilities_nexora_api_v1_platform_plugins_capabilities_get(self) -> Any:
        """Plugin Capabilities"""
        return self.request("GET", "/nexora-api/v1/platform/plugins/capabilities")

    def plugin_catalog_nexora_api_v1_platform_plugins_catalog_get(self) -> Any:
        """Plugin Catalog"""
        return self.request("GET", "/nexora-api/v1/platform/plugins/catalog")

    def plugin_lifecycle_nexora_api_v1_platform_plugins_slug_action_post(self, slug: str, action: str) -> Any:
        """Plugin Lifecycle"""
        return self.request("POST", "/nexora-api/v1/platform/plugins/{slug}/{action}".format(slug=slug, action=action))

    def poll_nexora_api_v1_monitoring_poll_post(self, *, json: Any = None) -> Any:
        """Poll"""
        return self.request("POST", "/nexora-api/v1/monitoring/poll", json=json)

    def postmortem_dashboard_nexora_api_v1_incidents_postmortems_get(self) -> Any:
        """Postmortem Dashboard"""
        return self.request("GET", "/nexora-api/v1/incidents/postmortems")

    def preview_invitation_nexora_api_v1_invitations_preview_token_get(self, token: str) -> Any:
        """Preview Invitation"""
        return self.request("GET", "/nexora-api/v1/invitations/preview/{token}".format(token=token))

    def pricing_nexora_api_v1_sales_pricing_get(self) -> Any:
        """Pricing"""
        return self.request("GET", "/nexora-api/v1/sales/pricing")

    def product_videos_nexora_api_v1_sales_product_videos_get(self, *, params: dict | None = None) -> Any:
        """Product Videos"""
        return self.request("GET", "/nexora-api/v1/sales/product-videos", params=params)

    def promote_rollout_nexora_api_v1_delivery_release_reliability_reliability_id_promote_post(self, reliability_id: str) -> Any:
        """Promote Rollout"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/promote".format(reliability_id=reliability_id))

    def promotion_queue_nexora_api_v1_delivery_promotion_queue_get(self) -> Any:
        """Promotion Queue"""
        return self.request("GET", "/nexora-api/v1/delivery/promotion-queue")

    def proposal_nexora_api_v1_sales_proposal_post(self, *, json: Any = None) -> Any:
        """Proposal"""
        return self.request("POST", "/nexora-api/v1/sales/proposal", json=json)

    def propose_action_nexora_api_v1_operator_recommendations_recommendation_id_propose_post(self, recommendation_id: str) -> Any:
        """Propose Action"""
        return self.request("POST", "/nexora-api/v1/operator/recommendations/{recommendation_id}/propose".format(recommendation_id=recommendation_id))

    def propose_k8s_operation_nexora_api_v1_control_plane_clusters_cluster_id_k8s_operations_post(self, cluster_id: str, *, json: Any = None) -> Any:
        """Propose K8S Operation"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters/{cluster_id}/k8s/operations".format(cluster_id=cluster_id), json=json)

    def propose_live_operation_nexora_api_v1_pilot_live_operations_post(self, *, json: Any = None) -> Any:
        """Propose Live Operation"""
        return self.request("POST", "/nexora-api/v1/pilot/live-operations", json=json)

    def propose_operation_nexora_api_v1_control_plane_operations_post(self, *, json: Any = None) -> Any:
        """Propose Operation"""
        return self.request("POST", "/nexora-api/v1/control-plane/operations", json=json)

    def propose_operation_nexora_api_v1_delivery_operations_post(self, *, json: Any = None) -> Any:
        """Propose Operation"""
        return self.request("POST", "/nexora-api/v1/delivery/operations", json=json)

    def propose_remediation_nexora_api_v1_security_remediation_post(self, *, json: Any = None) -> Any:
        """Propose Remediation"""
        return self.request("POST", "/nexora-api/v1/security/remediation", json=json)

    def propose_rollout_nexora_api_v1_delivery_release_reliability_reliability_id_propose_rollout_post(self, reliability_id: str, *, json: Any = None) -> Any:
        """Propose Rollout"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/propose-rollout".format(reliability_id=reliability_id), json=json)

    def propose_run_nexora_api_v1_platform_engineering_stacks_stack_id_runs_post(self, stack_id: str, *, json: Any = None) -> Any:
        """Propose Run"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/stacks/{stack_id}/runs".format(stack_id=stack_id), json=json)

    def public_status_page_nexora_api_v1_incidents_status_pages_slug_public_get(self, slug: str) -> Any:
        """Public Status Page"""
        return self.request("GET", "/nexora-api/v1/incidents/status-pages/{slug}/public".format(slug=slug))

    def publish_event_nexora_api_v1_platform_events_post(self, *, json: Any = None) -> Any:
        """Publish Event"""
        return self.request("POST", "/nexora-api/v1/platform/events", json=json)

    def publish_status_incident_nexora_api_v1_incidents_status_pages_page_id_incidents_post(self, page_id: str, *, json: Any = None) -> Any:
        """Publish Status Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/status-pages/{page_id}/incidents".format(page_id=page_id), json=json)

    def query_metrics_nexora_api_v1_observability_metrics_query_post(self, *, json: Any = None) -> Any:
        """Query Metrics"""
        return self.request("POST", "/nexora-api/v1/observability/metrics/query", json=json)

    def readyz_readyz_get(self) -> Any:
        """Readyz"""
        return self.request("GET", "/readyz")

    def recall_memory_nexora_api_v1_ai_memory_recall_post(self, *, json: Any = None) -> Any:
        """Recall Memory"""
        return self.request("POST", "/nexora-api/v1/ai/memory/recall", json=json)

    def recently_added_videos_nexora_api_v1_customer_success_videos_recently_added_get(self, *, params: dict | None = None) -> Any:
        """Recently Added Videos"""
        return self.request("GET", "/nexora-api/v1/customer-success/videos/recently-added", params=params)

    def recompute_impact_analysis_nexora_api_v1_impact_analysis_post(self, *, json: Any = None) -> Any:
        """Recompute Impact Analysis"""
        return self.request("POST", "/nexora-api/v1/impact-analysis", json=json)

    def record_step_nexora_api_v1_product_tours_tour_id_step_post(self, tour_id: str, *, json: Any = None) -> Any:
        """Record Step"""
        return self.request("POST", "/nexora-api/v1/product-tours/{tour_id}/step".format(tour_id=tour_id), json=json)

    def recover_executions_nexora_api_v1_platform_executions_recover_post(self) -> Any:
        """Recover Executions"""
        return self.request("POST", "/nexora-api/v1/platform/executions/recover")

    def refresh_baseline_nexora_api_v1_pilot_baseline_refresh_post(self) -> Any:
        """Refresh Baseline"""
        return self.request("POST", "/nexora-api/v1/pilot/baseline/refresh")

    def refresh_nexora_api_v1_auth_refresh_post(self, *, json: Any = None) -> Any:
        """Refresh"""
        return self.request("POST", "/nexora-api/v1/auth/refresh", json=json)

    def regenerate_demo_organization_nexora_api_v1_demo_organizations_organization_id_regenerate_post(self, organization_id: str) -> Any:
        """Regenerate Demo Organization"""
        return self.request("POST", "/nexora-api/v1/demo-organizations/{organization_id}/regenerate".format(organization_id=organization_id))

    def regenerate_recovery_codes_nexora_api_v1_auth_mfa_recovery_codes_regenerate_post(self) -> Any:
        """Regenerate Recovery Codes"""
        return self.request("POST", "/nexora-api/v1/auth/mfa/recovery-codes/regenerate")

    def register_cloud_account_nexora_api_v1_control_plane_cloud_accounts_post(self, *, json: Any = None) -> Any:
        """Register Cloud Account"""
        return self.request("POST", "/nexora-api/v1/control-plane/cloud-accounts", json=json)

    def register_cluster_nexora_api_v1_control_plane_clusters_post(self, *, json: Any = None) -> Any:
        """Register Cluster"""
        return self.request("POST", "/nexora-api/v1/control-plane/clusters", json=json)

    def register_mcp_server_nexora_api_v1_ai_mcp_servers_post(self, *, json: Any = None) -> Any:
        """Register Mcp Server"""
        return self.request("POST", "/nexora-api/v1/ai/mcp/servers", json=json)

    def register_nexora_api_v1_auth_register_post(self, *, json: Any = None) -> Any:
        """Register"""
        return self.request("POST", "/nexora-api/v1/auth/register", json=json)

    def reindex_search_nexora_api_v1_platform_search_reindex_post(self) -> Any:
        """Reindex Search"""
        return self.request("POST", "/nexora-api/v1/platform/search/reindex")

    def reject_artifact_nexora_api_v1_approval_artifact_id_reject_post(self, artifact_id: str, *, json: Any = None) -> Any:
        """Reject Artifact"""
        return self.request("POST", "/nexora-api/v1/approval/{artifact_id}/reject".format(artifact_id=artifact_id), json=json)

    def reject_remediation_action_nexora_api_v1_remediation_actions_action_id_reject_post(self, action_id: str, *, json: Any = None) -> Any:
        """Reject Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/reject".format(action_id=action_id), json=json)

    def reject_workflow_approval_nexora_api_v1_workflow_approvals_approval_id_reject_post(self, approval_id: str, *, json: Any = None) -> Any:
        """Reject Workflow Approval"""
        return self.request("POST", "/nexora-api/v1/workflow-approvals/{approval_id}/reject".format(approval_id=approval_id), json=json)

    def release_analytics_nexora_api_v1_delivery_release_analytics_get(self) -> Any:
        """Release Analytics"""
        return self.request("GET", "/nexora-api/v1/delivery/release-analytics")

    def release_history_nexora_api_v1_delivery_release_reliability_reliability_id_history_get(self, reliability_id: str) -> Any:
        """Release History"""
        return self.request("GET", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/history".format(reliability_id=reliability_id))

    def release_report_nexora_api_v1_customer_success_release_report_get(self) -> Any:
        """Release Report"""
        return self.request("GET", "/nexora-api/v1/customer-success/release-report")

    def remove_organization_member_nexora_api_v1_organizations_organization_id_members_member_id_delete(self, organization_id: str, member_id: str) -> Any:
        """Remove Organization Member"""
        return self.request("DELETE", "/nexora-api/v1/organizations/{organization_id}/members/{member_id}".format(organization_id=organization_id, member_id=member_id))

    def render_prompt_nexora_api_v1_ai_prompts_key_render_post(self, key: str, *, json: Any = None) -> Any:
        """Render Prompt"""
        return self.request("POST", "/nexora-api/v1/ai/prompts/{key}/render".format(key=key), json=json)

    def render_screenshot_nexora_api_v1_customer_success_screenshot_render_get(self, *, params: dict | None = None) -> Any:
        """Render Screenshot"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-render", params=params)

    def repair_docs_image_rendering_nexora_api_v1_docs_image_rendering_repair_post(self) -> Any:
        """Repair Docs Image Rendering"""
        return self.request("POST", "/nexora-api/v1/docs/image-rendering/repair")

    def replace_group_nexora_api_v1_scim_v2_groups_scim_id_put(self, scim_id: str) -> Any:
        """Replace Group"""
        return self.request("PUT", "/nexora-api/v1/scim/v2/Groups/{scim_id}".format(scim_id=scim_id))

    def replace_user_nexora_api_v1_scim_v2_users_scim_id_put(self, scim_id: str) -> Any:
        """Replace User"""
        return self.request("PUT", "/nexora-api/v1/scim/v2/Users/{scim_id}".format(scim_id=scim_id))

    def replay_event_nexora_api_v1_platform_events_event_id_replay_post(self, event_id: str) -> Any:
        """Replay Event"""
        return self.request("POST", "/nexora-api/v1/platform/events/{event_id}/replay".format(event_id=event_id))

    def replay_events_nexora_api_v1_platform_events_replay_post(self, *, params: dict | None = None) -> Any:
        """Replay Events"""
        return self.request("POST", "/nexora-api/v1/platform/events/replay", params=params)

    def replay_scenario_nexora_api_v1_demo_scenarios_scenario_id_replay_post(self, scenario_id: str, *, json: Any = None) -> Any:
        """Replay Scenario"""
        return self.request("POST", "/nexora-api/v1/demo-scenarios/{scenario_id}/replay".format(scenario_id=scenario_id), json=json)

    def reproduction_package_nexora_api_v1_ga_support_reproduction_package_get(self) -> Any:
        """Reproduction Package"""
        return self.request("GET", "/nexora-api/v1/ga/support/reproduction-package")

    def request_catalog_nexora_api_v1_platform_engineering_catalog_requests_post(self, *, json: Any = None) -> Any:
        """Request Catalog"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/catalog/requests", json=json)

    def request_closeout_nexora_api_v1_customer_pilot_closeout_request_post(self, *, json: Any = None) -> Any:
        """Request Closeout"""
        return self.request("POST", "/nexora-api/v1/customer-pilot/closeout/request", json=json)

    def request_promotion_nexora_api_v1_delivery_release_reliability_reliability_id_request_promotion_post(self, reliability_id: str, *, params: dict | None = None) -> Any:
        """Request Promotion"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/request-promotion".format(reliability_id=reliability_id), params=params)

    def requeue_event_nexora_api_v1_platform_events_event_id_requeue_post(self, event_id: str) -> Any:
        """Requeue Event"""
        return self.request("POST", "/nexora-api/v1/platform/events/{event_id}/requeue".format(event_id=event_id))

    def requeue_notification_delivery_nexora_api_v1_pilot_communications_communication_id_deliveries_delivery_id_requeue_post(self, communication_id: str, delivery_id: str) -> Any:
        """Requeue Notification Delivery"""
        return self.request("POST", "/nexora-api/v1/pilot/communications/{communication_id}/deliveries/{delivery_id}/requeue".format(communication_id=communication_id, delivery_id=delivery_id))

    def resend_invitation_nexora_api_v1_invitations_invitation_id_resend_post(self, invitation_id: str) -> Any:
        """Resend Invitation"""
        return self.request("POST", "/nexora-api/v1/invitations/{invitation_id}/resend".format(invitation_id=invitation_id))

    def reset_demo_organization_nexora_api_v1_demo_organizations_organization_id_reset_post(self, organization_id: str) -> Any:
        """Reset Demo Organization"""
        return self.request("POST", "/nexora-api/v1/demo-organizations/{organization_id}/reset".format(organization_id=organization_id))

    def reset_scenario_nexora_api_v1_demo_scenarios_scenario_id_reset_post(self, scenario_id: str) -> Any:
        """Reset Scenario"""
        return self.request("POST", "/nexora-api/v1/demo-scenarios/{scenario_id}/reset".format(scenario_id=scenario_id))

    def resolve_config_nexora_api_v1_platform_config_get(self) -> Any:
        """Resolve Config"""
        return self.request("GET", "/nexora-api/v1/platform/config")

    def resolve_stage_agents_nexora_api_v1_ai_agents_stages_workflow_stage_id_resolution_get(self, workflow_stage_id: str) -> Any:
        """Resolve Stage Agents"""
        return self.request("GET", "/nexora-api/v1/ai-agents/stages/{workflow_stage_id}/resolution".format(workflow_stage_id=workflow_stage_id))

    def resource_timeline_nexora_api_v1_product_timeline_resource_type_resource_id_get(self, resource_type: str, resource_id: str, *, params: dict | None = None) -> Any:
        """Resource Timeline"""
        return self.request("GET", "/nexora-api/v1/product/timeline/{resource_type}/{resource_id}".format(resource_type=resource_type, resource_id=resource_id), params=params)

    def resource_types_nexora_api_v1_scim_v2_resource_types_get(self) -> Any:
        """Resource Types"""
        return self.request("GET", "/nexora-api/v1/scim/v2/ResourceTypes")

    def restore_backup_nexora_api_v1_ga_backups_backup_id_restore_post(self, backup_id: str) -> Any:
        """Restore Backup"""
        return self.request("POST", "/nexora-api/v1/ga/backups/{backup_id}/restore".format(backup_id=backup_id))

    def resume_agent_nexora_api_v1_ai_agents_run_id_resume_post(self, run_id: str) -> Any:
        """Resume Agent"""
        return self.request("POST", "/nexora-api/v1/ai/agents/{run_id}/resume".format(run_id=run_id))

    def resume_execution_nexora_api_v1_platform_executions_run_id_resume_post(self, run_id: str) -> Any:
        """Resume Execution"""
        return self.request("POST", "/nexora-api/v1/platform/executions/{run_id}/resume".format(run_id=run_id))

    def resume_org_nexora_api_v1_billing_admin_orgs_org_id_resume_post(self, org_id: str) -> Any:
        """Resume Org"""
        return self.request("POST", "/nexora-api/v1/billing/admin/orgs/{org_id}/resume".format(org_id=org_id))

    def resume_remediation_action_nexora_api_v1_remediation_actions_action_id_resume_post(self, action_id: str, *, json: Any = None) -> Any:
        """Resume Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/resume".format(action_id=action_id), json=json)

    def resume_rollout_nexora_api_v1_delivery_release_reliability_reliability_id_resume_post(self, reliability_id: str) -> Any:
        """Resume Rollout"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/resume".format(reliability_id=reliability_id))

    def retention_purge_nexora_api_v1_audit_retention_purge_post(self, *, params: dict | None = None) -> Any:
        """Retention Purge"""
        return self.request("POST", "/nexora-api/v1/audit/retention/purge", params=params)

    def retry_execution_nexora_api_v1_platform_executions_run_id_retry_post(self, run_id: str) -> Any:
        """Retry Execution"""
        return self.request("POST", "/nexora-api/v1/platform/executions/{run_id}/retry".format(run_id=run_id))

    def retry_job_nexora_api_v1_jobs_job_id_retry_post(self, job_id: str) -> Any:
        """Retry Job"""
        return self.request("POST", "/nexora-api/v1/jobs/{job_id}/retry".format(job_id=job_id))

    def retry_notification_nexora_api_v1_platform_notifications_message_id_retry_post(self, message_id: str) -> Any:
        """Retry Notification"""
        return self.request("POST", "/nexora-api/v1/platform/notifications/{message_id}/retry".format(message_id=message_id))

    def retry_remediation_action_nexora_api_v1_remediation_actions_action_id_retry_post(self, action_id: str, *, json: Any = None) -> Any:
        """Retry Remediation Action"""
        return self.request("POST", "/nexora-api/v1/remediation-actions/{action_id}/retry".format(action_id=action_id), json=json)

    def revoke_invitation_nexora_api_v1_invitations_invitation_id_delete(self, invitation_id: str) -> Any:
        """Revoke Invitation"""
        return self.request("DELETE", "/nexora-api/v1/invitations/{invitation_id}".format(invitation_id=invitation_id))

    def revoke_org_key_nexora_api_v1_api_keys_organization_key_id_delete(self, key_id: str) -> Any:
        """Revoke Org Key"""
        return self.request("DELETE", "/nexora-api/v1/api-keys/organization/{key_id}".format(key_id=key_id))

    def revoke_other_sessions_nexora_api_v1_auth_sessions_revoke_others_post(self) -> Any:
        """Revoke Other Sessions"""
        return self.request("POST", "/nexora-api/v1/auth/sessions/revoke-others")

    def revoke_personal_key_nexora_api_v1_api_keys_personal_key_id_delete(self, key_id: str) -> Any:
        """Revoke Personal Key"""
        return self.request("DELETE", "/nexora-api/v1/api-keys/personal/{key_id}".format(key_id=key_id))

    def revoke_scim_token_nexora_api_v1_scim_v2_admin_tokens_token_id_delete(self, token_id: str) -> Any:
        """Revoke Scim Token"""
        return self.request("DELETE", "/nexora-api/v1/scim/v2/admin/tokens/{token_id}".format(token_id=token_id))

    def revoke_service_account_key_nexora_api_v1_service_accounts_sa_id_keys_key_id_delete(self, sa_id: str, key_id: str) -> Any:
        """Revoke Service Account Key"""
        return self.request("DELETE", "/nexora-api/v1/service-accounts/{sa_id}/keys/{key_id}".format(sa_id=sa_id, key_id=key_id))

    def revoke_session_nexora_api_v1_auth_sessions_jti_delete(self, jti: str) -> Any:
        """Revoke Session"""
        return self.request("DELETE", "/nexora-api/v1/auth/sessions/{jti}".format(jti=jti))

    def revoke_session_nexora_api_v1_sessions_session_id_delete(self, session_id: str) -> Any:
        """Revoke Session"""
        return self.request("DELETE", "/nexora-api/v1/sessions/{session_id}".format(session_id=session_id))

    def rewritten_guide_nexora_api_v1_customer_success_rewritten_guides_key_get(self, key: str) -> Any:
        """Rewritten Guide"""
        return self.request("GET", "/nexora-api/v1/customer-success/rewritten-guides/{key}".format(key=key))

    def rewritten_guides_nexora_api_v1_customer_success_rewritten_guides_get(self) -> Any:
        """Rewritten Guides"""
        return self.request("GET", "/nexora-api/v1/customer-success/rewritten-guides")

    def rewritten_guides_quality_nexora_api_v1_customer_success_rewritten_guides_quality_get(self) -> Any:
        """Rewritten Guides Quality"""
        return self.request("GET", "/nexora-api/v1/customer-success/rewritten-guides/quality")

    def rollback_deployment_nexora_api_v1_deployments_deployment_id_rollback_post(self, deployment_id: str, *, json: Any = None) -> Any:
        """Rollback Deployment"""
        return self.request("POST", "/nexora-api/v1/deployments/{deployment_id}/rollback".format(deployment_id=deployment_id), json=json)

    def rollback_prompt_nexora_api_v1_ai_prompts_key_rollback_post(self, key: str, *, json: Any = None) -> Any:
        """Rollback Prompt"""
        return self.request("POST", "/nexora-api/v1/ai/prompts/{key}/rollback".format(key=key), json=json)

    def rollback_release_nexora_api_v1_delivery_release_reliability_reliability_id_rollback_post(self, reliability_id: str, *, params: dict | None = None) -> Any:
        """Rollback Release"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/rollback".format(reliability_id=reliability_id), params=params)

    def rotate_org_key_nexora_api_v1_api_keys_organization_key_id_rotate_post(self, key_id: str) -> Any:
        """Rotate Org Key"""
        return self.request("POST", "/nexora-api/v1/api-keys/organization/{key_id}/rotate".format(key_id=key_id))

    def rotate_personal_key_nexora_api_v1_api_keys_personal_key_id_rotate_post(self, key_id: str) -> Any:
        """Rotate Personal Key"""
        return self.request("POST", "/nexora-api/v1/api-keys/personal/{key_id}/rotate".format(key_id=key_id))

    def rotate_secret_nexora_api_v1_platform_engineering_secrets_ref_id_rotate_post(self, ref_id: str) -> Any:
        """Rotate Secret"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/secrets/{ref_id}/rotate".format(ref_id=ref_id))

    def run_agent_nexora_api_v1_ai_agents_run_id_run_post(self, run_id: str) -> Any:
        """Run Agent"""
        return self.request("POST", "/nexora-api/v1/ai/agents/{run_id}/run".format(run_id=run_id))

    def run_approval_workflow_agent_nexora_api_v1_agents_approval_run_post(self, *, json: Any = None) -> Any:
        """Run Approval Workflow Agent"""
        return self.request("POST", "/nexora-api/v1/agents/approval/run", json=json)

    def run_assessment_nexora_api_v1_pilot_assessment_run_post(self) -> Any:
        """Run Assessment"""
        return self.request("POST", "/nexora-api/v1/pilot/assessment/run")

    def run_backend_architect_agent_nexora_api_v1_agents_backend_architect_run_post(self, *, json: Any = None) -> Any:
        """Run Backend Architect Agent"""
        return self.request("POST", "/nexora-api/v1/agents/backend-architect/run", json=json)

    def run_backend_code_review_agent_nexora_api_v1_agents_backend_code_review_run_post(self, *, json: Any = None) -> Any:
        """Run Backend Code Review Agent"""
        return self.request("POST", "/nexora-api/v1/agents/backend-code-review/run", json=json)

    def run_backend_execution_agent_nexora_api_v1_agents_backend_execution_run_post(self, *, json: Any = None) -> Any:
        """Run Backend Execution Agent"""
        return self.request("POST", "/nexora-api/v1/agents/backend-execution/run", json=json)

    def run_backend_v1_agent_nexora_api_v1_agents_backend_v1_run_post(self, *, json: Any = None) -> Any:
        """Run Backend V1 Agent"""
        return self.request("POST", "/nexora-api/v1/agents/backend-v1/run", json=json)

    def run_backend_v2_agent_nexora_api_v1_agents_backend_v2_run_post(self, *, json: Any = None) -> Any:
        """Run Backend V2 Agent"""
        return self.request("POST", "/nexora-api/v1/agents/backend-v2/run", json=json)

    def run_backend_v3_agent_nexora_api_v1_agents_backend_v3_run_post(self, *, json: Any = None) -> Any:
        """Run Backend V3 Agent"""
        return self.request("POST", "/nexora-api/v1/agents/backend-v3/run", json=json)

    def run_business_analyst_agent_nexora_api_v1_agents_business_analyst_run_post(self, *, json: Any = None) -> Any:
        """Run Business Analyst Agent"""
        return self.request("POST", "/nexora-api/v1/agents/business-analyst/run", json=json)

    def run_cicd_agent_nexora_api_v1_agents_cicd_run_post(self, *, json: Any = None) -> Any:
        """Run Cicd Agent"""
        return self.request("POST", "/nexora-api/v1/agents/cicd/run", json=json)

    def run_compliance_nexora_api_v1_platform_engineering_compliance_scan_post(self) -> Any:
        """Run Compliance"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/compliance/scan")

    def run_deployment_agent_nexora_api_v1_agents_deployment_run_post(self, *, json: Any = None) -> Any:
        """Run Deployment Agent"""
        return self.request("POST", "/nexora-api/v1/agents/deployment/run", json=json)

    def run_docker_agent_nexora_api_v1_agents_docker_agent_run_post(self, *, json: Any = None) -> Any:
        """Run Docker Agent"""
        return self.request("POST", "/nexora-api/v1/agents/docker-agent/run", json=json)

    def run_due_report_schedules_nexora_api_v1_product_reports_schedules_run_due_post(self) -> Any:
        """Run Due Report Schedules"""
        return self.request("POST", "/nexora-api/v1/product/reports/schedules/run-due")

    def run_escalation_nexora_api_v1_incidents_escalation_run_post(self) -> Any:
        """Run Escalation"""
        return self.request("POST", "/nexora-api/v1/incidents/escalation/run")

    def run_escalations_nexora_api_v1_oncall_escalations_run_post(self) -> Any:
        """Run Escalations"""
        return self.request("POST", "/nexora-api/v1/oncall/escalations/run")

    def run_frontend_architect_agent_nexora_api_v1_agents_frontend_architect_run_post(self, *, json: Any = None) -> Any:
        """Run Frontend Architect Agent"""
        return self.request("POST", "/nexora-api/v1/agents/frontend-architect/run", json=json)

    def run_frontend_code_review_agent_nexora_api_v1_agents_frontend_code_review_run_post(self, *, json: Any = None) -> Any:
        """Run Frontend Code Review Agent"""
        return self.request("POST", "/nexora-api/v1/agents/frontend-code-review/run", json=json)

    def run_frontend_execution_agent_nexora_api_v1_agents_frontend_execution_run_post(self, *, json: Any = None) -> Any:
        """Run Frontend Execution Agent"""
        return self.request("POST", "/nexora-api/v1/agents/frontend-execution/run", json=json)

    def run_frontend_v1_agent_nexora_api_v1_agents_frontend_v1_run_post(self, *, json: Any = None) -> Any:
        """Run Frontend V1 Agent"""
        return self.request("POST", "/nexora-api/v1/agents/frontend-v1/run", json=json)

    def run_frontend_v2_agent_nexora_api_v1_agents_frontend_v2_run_post(self, *, json: Any = None) -> Any:
        """Run Frontend V2 Agent"""
        return self.request("POST", "/nexora-api/v1/agents/frontend-v2/run", json=json)

    def run_frontend_v3_agent_nexora_api_v1_agents_frontend_v3_run_post(self, *, json: Any = None) -> Any:
        """Run Frontend V3 Agent"""
        return self.request("POST", "/nexora-api/v1/agents/frontend-v3/run", json=json)

    def run_fullstack_assembly_agent_nexora_api_v1_agents_fullstack_assembly_run_post(self, *, json: Any = None) -> Any:
        """Run Fullstack Assembly Agent"""
        return self.request("POST", "/nexora-api/v1/agents/fullstack-assembly/run", json=json)

    def run_infrastructure_architect_agent_nexora_api_v1_agents_infrastructure_architect_run_post(self, *, json: Any = None) -> Any:
        """Run Infrastructure Architect Agent"""
        return self.request("POST", "/nexora-api/v1/agents/infrastructure-architect/run", json=json)

    def run_install_readiness_nexora_api_v1_ga_install_readiness_post(self, *, json: Any = None) -> Any:
        """Run Install Readiness"""
        return self.request("POST", "/nexora-api/v1/ga/install/readiness", json=json)

    def run_integration_test_agent_nexora_api_v1_agents_integration_tests_run_post(self, *, json: Any = None) -> Any:
        """Run Integration Test Agent"""
        return self.request("POST", "/nexora-api/v1/agents/integration-tests/run", json=json)

    def run_kubernetes_agent_nexora_api_v1_agents_kubernetes_run_post(self, *, json: Any = None) -> Any:
        """Run Kubernetes Agent"""
        return self.request("POST", "/nexora-api/v1/agents/kubernetes/run", json=json)

    def run_observability_agent_nexora_api_v1_agents_observability_run_post(self, *, json: Any = None) -> Any:
        """Run Observability Agent"""
        return self.request("POST", "/nexora-api/v1/agents/observability/run", json=json)

    def run_performance_test_agent_nexora_api_v1_agents_performance_tests_run_post(self, *, json: Any = None) -> Any:
        """Run Performance Test Agent"""
        return self.request("POST", "/nexora-api/v1/agents/performance-tests/run", json=json)

    def run_predictions_nexora_api_v1_sre_predictions_run_post(self, *, params: dict | None = None) -> Any:
        """Run Predictions"""
        return self.request("POST", "/nexora-api/v1/sre/predictions/run", params=params)

    def run_product_owner_agent_nexora_api_v1_agents_product_owner_run_post(self, *, json: Any = None) -> Any:
        """Run Product Owner Agent"""
        return self.request("POST", "/nexora-api/v1/agents/product-owner/run", json=json)

    def run_qa_approval_agent_nexora_api_v1_agents_qa_approvals_run_post(self, *, json: Any = None) -> Any:
        """Run Qa Approval Agent"""
        return self.request("POST", "/nexora-api/v1/agents/qa-approvals/run", json=json)

    def run_qa_architect_agent_nexora_api_v1_agents_qa_architect_run_post(self, *, json: Any = None) -> Any:
        """Run Qa Architect Agent"""
        return self.request("POST", "/nexora-api/v1/agents/qa-architect/run", json=json)

    def run_scan_nexora_api_v1_security_scans_post(self, *, json: Any = None) -> Any:
        """Run Scan"""
        return self.request("POST", "/nexora-api/v1/security/scans", json=json)

    def run_scenario_nexora_api_v1_demo_scenarios_scenario_id_run_post(self, scenario_id: str) -> Any:
        """Run Scenario"""
        return self.request("POST", "/nexora-api/v1/demo-scenarios/{scenario_id}/run".format(scenario_id=scenario_id))

    def run_security_scan_nexora_api_v1_delivery_security_scans_post(self, *, json: Any = None) -> Any:
        """Run Security Scan"""
        return self.request("POST", "/nexora-api/v1/delivery/security/scans", json=json)

    def run_security_test_agent_nexora_api_v1_agents_security_tests_run_post(self, *, json: Any = None) -> Any:
        """Run Security Test Agent"""
        return self.request("POST", "/nexora-api/v1/agents/security-tests/run", json=json)

    def run_sre_approval_agent_nexora_api_v1_agents_sre_approval_run_post(self, *, json: Any = None) -> Any:
        """Run Sre Approval Agent"""
        return self.request("POST", "/nexora-api/v1/agents/sre-approval/run", json=json)

    def run_uiux_designer_agent_nexora_api_v1_agents_uiux_run_post(self, *, json: Any = None) -> Any:
        """Run Uiux Designer Agent"""
        return self.request("POST", "/nexora-api/v1/agents/uiux/run", json=json)

    def run_unit_test_generator_agent_nexora_api_v1_agents_unit_tests_run_post(self, *, json: Any = None) -> Any:
        """Run Unit Test Generator Agent"""
        return self.request("POST", "/nexora-api/v1/agents/unit-tests/run", json=json)

    def run_verification_nexora_api_v1_customer_success_verify_post(self) -> Any:
        """Run Verification"""
        return self.request("POST", "/nexora-api/v1/customer-success/verify")

    def run_workflow_schedule_now_nexora_api_v1_ai_team_workflow_schedules_schedule_id_run_now_post(self, schedule_id: str) -> Any:
        """Run Workflow Schedule Now"""
        return self.request("POST", "/nexora-api/v1/ai-team-workflow-schedules/{schedule_id}/run-now".format(schedule_id=schedule_id))

    def savings_nexora_api_v1_operator_savings_get(self) -> Any:
        """Savings"""
        return self.request("GET", "/nexora-api/v1/operator/savings")

    def sbom_inventory_nexora_api_v1_security_sbom_get(self) -> Any:
        """Sbom Inventory"""
        return self.request("GET", "/nexora-api/v1/security/sbom")

    def scan_drift_nexora_api_v1_platform_engineering_drift_scan_post(self) -> Any:
        """Scan Drift"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/drift/scan")

    def scenario_launcher_nexora_api_v1_sales_scenario_launcher_get(self) -> Any:
        """Scenario Launcher"""
        return self.request("GET", "/nexora-api/v1/sales/scenario-launcher")

    def schemas_nexora_api_v1_scim_v2_schemas_get(self) -> Any:
        """Schemas"""
        return self.request("GET", "/nexora-api/v1/scim/v2/Schemas")

    def scim_get_group_nexora_api_v1_scim_v2_groups_scim_id_get(self, scim_id: str) -> Any:
        """Scim Get Group"""
        return self.request("GET", "/nexora-api/v1/scim/v2/Groups/{scim_id}".format(scim_id=scim_id))

    def scim_get_user_nexora_api_v1_scim_v2_users_scim_id_get(self, scim_id: str) -> Any:
        """Scim Get User"""
        return self.request("GET", "/nexora-api/v1/scim/v2/Users/{scim_id}".format(scim_id=scim_id))

    def screenshot_assets_nexora_api_v1_customer_success_screenshot_assets_get(self) -> Any:
        """Screenshot Assets"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-assets")

    def screenshot_reality_ensure_nexora_api_v1_customer_success_screenshot_reality_ensure_post(self) -> Any:
        """Screenshot Reality Ensure"""
        return self.request("POST", "/nexora-api/v1/customer-success/screenshot-reality/ensure")

    def screenshot_reality_nexora_api_v1_customer_success_screenshot_reality_get(self) -> Any:
        """Screenshot Reality"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-reality")

    def screenshot_release_gate_nexora_api_v1_customer_success_screenshot_reality_release_gate_get(self) -> Any:
        """Screenshot Release Gate"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-reality/release-gate")

    def screenshot_validation_guide_nexora_api_v1_customer_success_screenshot_validation_guides_guide_id_get(self, guide_id: str) -> Any:
        """Screenshot Validation Guide"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-validation/guides/{guide_id}".format(guide_id=guide_id))

    def screenshot_validation_nexora_api_v1_customer_success_screenshot_validation_get(self) -> Any:
        """Screenshot Validation"""
        return self.request("GET", "/nexora-api/v1/customer-success/screenshot-validation")

    def search_analytics_nexora_api_v1_platform_search_analytics_get(self, *, params: dict | None = None) -> Any:
        """Search Analytics"""
        return self.request("GET", "/nexora-api/v1/platform/search/analytics", params=params)

    def search_autocomplete_nexora_api_v1_platform_search_autocomplete_get(self, *, params: dict | None = None) -> Any:
        """Search Autocomplete"""
        return self.request("GET", "/nexora-api/v1/platform/search/autocomplete", params=params)

    def search_logs_nexora_api_v1_observability_logs_search_post(self, *, json: Any = None) -> Any:
        """Search Logs"""
        return self.request("POST", "/nexora-api/v1/observability/logs/search", json=json)

    def search_traces_nexora_api_v1_observability_traces_search_post(self, *, json: Any = None) -> Any:
        """Search Traces"""
        return self.request("POST", "/nexora-api/v1/observability/traces/search", json=json)

    def seed_library_nexora_api_v1_test_playbooks_seed_library_post(self) -> Any:
        """Seed Library"""
        return self.request("POST", "/nexora-api/v1/test-playbooks/seed-library")

    def seed_scenarios_nexora_api_v1_demo_scenarios_seed_post(self) -> Any:
        """Seed Scenarios"""
        return self.request("POST", "/nexora-api/v1/demo-scenarios/seed")

    def send_communication_nexora_api_v1_pilot_communications_communication_id_send_post(self, communication_id: str) -> Any:
        """Send Communication"""
        return self.request("POST", "/nexora-api/v1/pilot/communications/{communication_id}/send".format(communication_id=communication_id))

    def send_notification_nexora_api_v1_platform_notifications_post(self, *, json: Any = None) -> Any:
        """Send Notification"""
        return self.request("POST", "/nexora-api/v1/platform/notifications", json=json)

    def service_dependencies_nexora_api_v1_services_service_id_dependencies_get(self, service_id: str) -> Any:
        """Service Dependencies"""
        return self.request("GET", "/nexora-api/v1/services/{service_id}/dependencies".format(service_id=service_id))

    def service_health_nexora_api_v1_services_service_id_health_get(self, service_id: str) -> Any:
        """Service Health"""
        return self.request("GET", "/nexora-api/v1/services/{service_id}/health".format(service_id=service_id))

    def service_map_nexora_api_v1_observability_service_map_get(self) -> Any:
        """Service Map"""
        return self.request("GET", "/nexora-api/v1/observability/service-map")

    def service_provider_config_nexora_api_v1_scim_v2_service_provider_config_get(self) -> Any:
        """Service Provider Config"""
        return self.request("GET", "/nexora-api/v1/scim/v2/ServiceProviderConfig")

    def set_config_nexora_api_v1_platform_config_put(self, *, json: Any = None) -> Any:
        """Set Config"""
        return self.request("PUT", "/nexora-api/v1/platform/config", json=json)

    def set_kill_switch_nexora_api_v1_ops_kill_switch_name_post(self, name: str, *, params: dict | None = None) -> Any:
        """Set Kill Switch"""
        return self.request("POST", "/nexora-api/v1/ops/kill-switch/{name}".format(name=name), params=params)

    def set_kill_switch_nexora_api_v1_pilot_safety_kill_switch_post(self, *, json: Any = None) -> Any:
        """Set Kill Switch"""
        return self.request("POST", "/nexora-api/v1/pilot/safety/kill-switch", json=json)

    def set_maintenance_nexora_api_v1_ops_maintenance_post(self, *, params: dict | None = None) -> Any:
        """Set Maintenance"""
        return self.request("POST", "/nexora-api/v1/ops/maintenance", params=params)

    def set_preference_nexora_api_v1_product_preferences_put(self, *, json: Any = None) -> Any:
        """Set Preference"""
        return self.request("PUT", "/nexora-api/v1/product/preferences", json=json)

    def set_quota_override_nexora_api_v1_billing_admin_orgs_org_id_quota_overrides_post(self, org_id: str, *, json: Any = None) -> Any:
        """Set Quota Override"""
        return self.request("POST", "/nexora-api/v1/billing/admin/orgs/{org_id}/quota-overrides".format(org_id=org_id), json=json)

    def set_release_channel_nexora_api_v1_ga_release_channel_put(self, *, json: Any = None) -> Any:
        """Set Release Channel"""
        return self.request("PUT", "/nexora-api/v1/ga/release/channel", json=json)

    def set_rollout_nexora_api_v1_ops_rollout_feature_post(self, feature: str, *, params: dict | None = None) -> Any:
        """Set Rollout"""
        return self.request("POST", "/nexora-api/v1/ops/rollout/{feature}".format(feature=feature), params=params)

    def set_state_nexora_api_v1_oncall_incidents_incident_id_state_post(self, incident_id: str, *, json: Any = None) -> Any:
        """Set State"""
        return self.request("POST", "/nexora-api/v1/oncall/incidents/{incident_id}/state".format(incident_id=incident_id), json=json)

    def simulate_recommendation_nexora_api_v1_operator_recommendations_recommendation_id_simulate_post(self, recommendation_id: str) -> Any:
        """Simulate Recommendation"""
        return self.request("POST", "/nexora-api/v1/operator/recommendations/{recommendation_id}/simulate".format(recommendation_id=recommendation_id))

    def slo_center_nexora_api_v1_ops_workspace_slo_get(self) -> Any:
        """Slo Center"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/slo")

    def slo_dashboard_nexora_api_v1_observability_slo_get(self) -> Any:
        """Slo Dashboard"""
        return self.request("GET", "/nexora-api/v1/observability/slo")

    def snooze_connection_expiry_nexora_api_v1_integrations_connections_connection_id_snooze_expiry_post(self, connection_id: str, *, json: Any = None) -> Any:
        """Snooze Connection Expiry"""
        return self.request("POST", "/nexora-api/v1/integrations/connections/{connection_id}/snooze-expiry".format(connection_id=connection_id), json=json)

    def snooze_inbox_nexora_api_v1_product_inbox_note_id_snooze_post(self, note_id: str, *, params: dict | None = None) -> Any:
        """Snooze Inbox"""
        return self.request("POST", "/nexora-api/v1/product/inbox/{note_id}/snooze".format(note_id=note_id), params=params)

    def sso_login_nexora_api_v1_auth_sso_slug_login_get(self, slug: str) -> Any:
        """Sso Login"""
        return self.request("GET", "/nexora-api/v1/auth/sso/{slug}/login".format(slug=slug))

    def sso_oidc_callback_nexora_api_v1_auth_sso_slug_callback_get(self, slug: str, *, params: dict | None = None) -> Any:
        """Sso Oidc Callback"""
        return self.request("GET", "/nexora-api/v1/auth/sso/{slug}/callback".format(slug=slug), params=params)

    def sso_saml_acs_nexora_api_v1_auth_sso_slug_acs_post(self, slug: str, *, json: Any = None) -> Any:
        """Sso Saml Acs"""
        return self.request("POST", "/nexora-api/v1/auth/sso/{slug}/acs".format(slug=slug), json=json)

    def sso_saml_metadata_nexora_api_v1_auth_sso_slug_metadata_get(self, slug: str) -> Any:
        """Sso Saml Metadata"""
        return self.request("GET", "/nexora-api/v1/auth/sso/{slug}/metadata".format(slug=slug))

    def staged_rollout_nexora_api_v1_ga_release_rollout_feature_post(self, feature: str, *, params: dict | None = None) -> Any:
        """Staged Rollout"""
        return self.request("POST", "/nexora-api/v1/ga/release/rollout/{feature}".format(feature=feature), params=params)

    def start_agent_nexora_api_v1_ai_agents_post(self, *, json: Any = None) -> Any:
        """Start Agent"""
        return self.request("POST", "/nexora-api/v1/ai/agents", json=json)

    def start_commander_nexora_api_v1_sre_commander_start_post(self, *, json: Any = None) -> Any:
        """Start Commander"""
        return self.request("POST", "/nexora-api/v1/sre/commander/start", json=json)

    def start_major_incident_nexora_api_v1_incidents_major_post(self, *, json: Any = None) -> Any:
        """Start Major Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/major", json=json)

    def start_onboarding_nexora_api_v1_onboarding_start_post(self, *, json: Any = None) -> Any:
        """Start Onboarding"""
        return self.request("POST", "/nexora-api/v1/onboarding/start", json=json)

    def start_onboarding_path_nexora_api_v1_pilot_onboarding_paths_path_id_start_post(self, path_id: str) -> Any:
        """Start Onboarding Path"""
        return self.request("POST", "/nexora-api/v1/pilot/onboarding-paths/{path_id}/start".format(path_id=path_id))

    def start_provision_nexora_api_v1_platform_engineering_provisions_post(self, *, json: Any = None) -> Any:
        """Start Provision"""
        return self.request("POST", "/nexora-api/v1/platform-engineering/provisions", json=json)

    def start_tour_nexora_api_v1_product_tours_start_post(self, *, json: Any = None) -> Any:
        """Start Tour"""
        return self.request("POST", "/nexora-api/v1/product-tours/start", json=json)

    def startupz_startupz_get(self) -> Any:
        """Startupz"""
        return self.request("GET", "/startupz")

    def store_credentials_nexora_api_v1_onboarding_integrations_sessions_session_id_credentials_post(self, session_id: str, *, json: Any = None) -> Any:
        """Store Credentials"""
        return self.request("POST", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/credentials".format(session_id=session_id), json=json)

    def stream_nexora_api_v1_ai_stream_post(self, *, json: Any = None) -> Any:
        """Stream"""
        return self.request("POST", "/nexora-api/v1/ai/stream", json=json)

    def stripe_webhook_nexora_api_v1_billing_webhooks_stripe_post(self) -> Any:
        """Stripe Webhook"""
        return self.request("POST", "/nexora-api/v1/billing/webhooks/stripe")

    def submit_change_request_nexora_api_v1_change_requests_run_id_submit_post(self, run_id: str) -> Any:
        """Submit Change Request"""
        return self.request("POST", "/nexora-api/v1/change-requests/{run_id}/submit".format(run_id=run_id))

    def submit_execution_nexora_api_v1_platform_executions_post(self, *, json: Any = None) -> Any:
        """Submit Execution"""
        return self.request("POST", "/nexora-api/v1/platform/executions", json=json)

    def submit_requirement_nexora_api_v1_requirements_post(self, *, json: Any = None) -> Any:
        """Submit Requirement"""
        return self.request("POST", "/nexora-api/v1/requirements", json=json)

    def success_playbook_nexora_api_v1_customer_success_success_playbooks_key_get(self, key: str) -> Any:
        """Success Playbook"""
        return self.request("GET", "/nexora-api/v1/customer-success/success-playbooks/{key}".format(key=key))

    def success_playbooks_nexora_api_v1_customer_success_success_playbooks_get(self) -> Any:
        """Success Playbooks"""
        return self.request("GET", "/nexora-api/v1/customer-success/success-playbooks")

    def suggested_questions_nexora_api_v1_copilot_suggested_questions_get(self) -> Any:
        """Suggested Questions"""
        return self.request("GET", "/nexora-api/v1/copilot/suggested-questions")

    def support_bundle_nexora_api_v1_ops_support_bundle_get(self) -> Any:
        """Support Bundle"""
        return self.request("GET", "/nexora-api/v1/ops/support-bundle")

    def suspend_org_nexora_api_v1_billing_admin_orgs_org_id_suspend_post(self, org_id: str, *, json: Any = None) -> Any:
        """Suspend Org"""
        return self.request("POST", "/nexora-api/v1/billing/admin/orgs/{org_id}/suspend".format(org_id=org_id), json=json)

    def switch_organization_nexora_api_v1_organizations_organization_id_switch_post(self, organization_id: str) -> Any:
        """Switch Organization"""
        return self.request("POST", "/nexora-api/v1/organizations/{organization_id}/switch".format(organization_id=organization_id))

    def sync_artifacts_nexora_api_v1_delivery_artifacts_sync_post(self, *, params: dict | None = None) -> Any:
        """Sync Artifacts"""
        return self.request("POST", "/nexora-api/v1/delivery/artifacts/sync", params=params)

    def sync_cloud_account_nexora_api_v1_control_plane_cloud_accounts_account_id_sync_post(self, account_id: str) -> Any:
        """Sync Cloud Account"""
        return self.request("POST", "/nexora-api/v1/control-plane/cloud-accounts/{account_id}/sync".format(account_id=account_id))

    def sync_discovery_nexora_api_v1_discovery_sync_post(self, *, json: Any = None) -> Any:
        """Sync Discovery"""
        return self.request("POST", "/nexora-api/v1/discovery/sync", json=json)

    def sync_gitops_nexora_api_v1_delivery_gitops_sync_post(self, *, params: dict | None = None) -> Any:
        """Sync Gitops"""
        return self.request("POST", "/nexora-api/v1/delivery/gitops/sync", params=params)

    def sync_integration_connection_nexora_api_v1_integrations_connections_connection_id_sync_post(self, connection_id: str) -> Any:
        """Sync Integration Connection"""
        return self.request("POST", "/nexora-api/v1/integrations/connections/{connection_id}/sync".format(connection_id=connection_id))

    def sync_mcp_server_nexora_api_v1_ai_mcp_servers_server_id_sync_post(self, server_id: str) -> Any:
        """Sync Mcp Server"""
        return self.request("POST", "/nexora-api/v1/ai/mcp/servers/{server_id}/sync".format(server_id=server_id))

    def sync_pipeline_runs_nexora_api_v1_delivery_pipelines_pipeline_id_runs_sync_post(self, pipeline_id: str) -> Any:
        """Sync Pipeline Runs"""
        return self.request("POST", "/nexora-api/v1/delivery/pipelines/{pipeline_id}/runs/sync".format(pipeline_id=pipeline_id))

    def sync_pipelines_nexora_api_v1_delivery_repositories_repository_id_pipelines_sync_post(self, repository_id: str) -> Any:
        """Sync Pipelines"""
        return self.request("POST", "/nexora-api/v1/delivery/repositories/{repository_id}/pipelines/sync".format(repository_id=repository_id))

    def sync_repositories_nexora_api_v1_delivery_source_connections_connection_id_sync_post(self, connection_id: str) -> Any:
        """Sync Repositories"""
        return self.request("POST", "/nexora-api/v1/delivery/source-connections/{connection_id}/sync".format(connection_id=connection_id))

    def test_integration_notification_nexora_api_v1_integrations_notifications_test_post(self, *, json: Any = None) -> Any:
        """Test Integration Notification"""
        return self.request("POST", "/nexora-api/v1/integrations/notifications/test", json=json)

    def toggle_favorite_nexora_api_v1_product_preferences_favorites_post(self, *, json: Any = None) -> Any:
        """Toggle Favorite"""
        return self.request("POST", "/nexora-api/v1/product/preferences/favorites", json=json)

    def top_metrics_nexora_api_v1_observability_metrics_top_get(self) -> Any:
        """Top Metrics"""
        return self.request("GET", "/nexora-api/v1/observability/metrics/top")

    def tour_state_nexora_api_v1_customer_success_tours_key_state_post(self, key: str, *, json: Any = None) -> Any:
        """Tour State"""
        return self.request("POST", "/nexora-api/v1/customer-success/tours/{key}/state".format(key=key), json=json)

    def tours_for_module_nexora_api_v1_customer_success_tours_by_module_module_get(self, module: str) -> Any:
        """Tours For Module"""
        return self.request("GET", "/nexora-api/v1/customer-success/tours/by-module/{module}".format(module=module))

    def track_analytics_nexora_api_v1_product_analytics_track_post(self, *, json: Any = None) -> Any:
        """Track Analytics"""
        return self.request("POST", "/nexora-api/v1/product/analytics/track", json=json)

    def track_recent_nexora_api_v1_product_preferences_recent_post(self, *, json: Any = None) -> Any:
        """Track Recent"""
        return self.request("POST", "/nexora-api/v1/product/preferences/recent", json=json)

    def transition_finding_nexora_api_v1_security_findings_finding_id_transition_post(self, finding_id: str, *, json: Any = None) -> Any:
        """Transition Finding"""
        return self.request("POST", "/nexora-api/v1/security/findings/{finding_id}/transition".format(finding_id=finding_id), json=json)

    def transition_incident_nexora_api_v1_incidents_investigation_id_transition_post(self, investigation_id: str, *, json: Any = None) -> Any:
        """Transition Incident"""
        return self.request("POST", "/nexora-api/v1/incidents/{investigation_id}/transition".format(investigation_id=investigation_id), json=json)

    def ttv_dashboard_nexora_api_v1_customer_success_time_to_value_get(self, *, params: dict | None = None) -> Any:
        """Ttv Dashboard"""
        return self.request("GET", "/nexora-api/v1/customer-success/time-to-value", params=params)

    def ttv_experience_nexora_api_v1_customer_success_time_to_value_experiences_key_get(self, key: str, *, params: dict | None = None) -> Any:
        """Ttv Experience"""
        return self.request("GET", "/nexora-api/v1/customer-success/time-to-value/experiences/{key}".format(key=key), params=params)

    def ttv_experience_progress_nexora_api_v1_customer_success_time_to_value_experiences_key_progress_post(self, key: str, *, json: Any = None) -> Any:
        """Ttv Experience Progress"""
        return self.request("POST", "/nexora-api/v1/customer-success/time-to-value/experiences/{key}/progress".format(key=key), json=json)

    def ttv_experiences_nexora_api_v1_customer_success_time_to_value_experiences_get(self, *, params: dict | None = None) -> Any:
        """Ttv Experiences"""
        return self.request("GET", "/nexora-api/v1/customer-success/time-to-value/experiences", params=params)

    def ttv_progress_nexora_api_v1_customer_success_time_to_value_progress_post(self, *, json: Any = None) -> Any:
        """Ttv Progress"""
        return self.request("POST", "/nexora-api/v1/customer-success/time-to-value/progress", json=json)

    def unassign_agent_nexora_api_v1_ai_agents_agent_id_assignments_assignment_id_delete(self, agent_id: str, assignment_id: str) -> Any:
        """Unassign Agent"""
        return self.request("DELETE", "/nexora-api/v1/ai-agents/{agent_id}/assignments/{assignment_id}".format(agent_id=agent_id, assignment_id=assignment_id))

    def unassign_ai_team_agent_tool_nexora_api_v1_ai_team_agents_agent_id_tools_tool_id_delete(self, agent_id: str, tool_id: str) -> Any:
        """Unassign Ai Team Agent Tool"""
        return self.request("DELETE", "/nexora-api/v1/ai-team-agents/{agent_id}/tools/{tool_id}".format(agent_id=agent_id, tool_id=tool_id))

    def unassign_team_nexora_api_v1_stages_stage_id_teams_team_id_delete(self, stage_id: str, team_id: str) -> Any:
        """Unassign Team"""
        return self.request("DELETE", "/nexora-api/v1/stages/{stage_id}/teams/{team_id}".format(stage_id=stage_id, team_id=team_id))

    def unified_inventory_nexora_api_v1_control_plane_inventory_get(self) -> Any:
        """Unified Inventory"""
        return self.request("GET", "/nexora-api/v1/control-plane/inventory")

    def unified_search_nexora_api_v1_ops_workspace_search_get(self, *, params: dict | None = None) -> Any:
        """Unified Search"""
        return self.request("GET", "/nexora-api/v1/ops-workspace/search", params=params)

    def uninstall_plugin_nexora_api_v1_platform_plugins_slug_delete(self, slug: str) -> Any:
        """Uninstall Plugin"""
        return self.request("DELETE", "/nexora-api/v1/platform/plugins/{slug}".format(slug=slug))

    def update_agent_input_nexora_api_v1_ai_agent_inputs_input_id_put(self, input_id: str, *, json: Any = None) -> Any:
        """Update Agent Input"""
        return self.request("PUT", "/nexora-api/v1/ai-agent-inputs/{input_id}".format(input_id=input_id), json=json)

    def update_agent_output_nexora_api_v1_ai_agent_outputs_output_id_put(self, output_id: str, *, json: Any = None) -> Any:
        """Update Agent Output"""
        return self.request("PUT", "/nexora-api/v1/ai-agent-outputs/{output_id}".format(output_id=output_id), json=json)

    def update_agent_responsibility_nexora_api_v1_ai_agent_responsibilities_responsibility_id_put(self, responsibility_id: str, *, json: Any = None) -> Any:
        """Update Agent Responsibility"""
        return self.request("PUT", "/nexora-api/v1/ai-agent-responsibilities/{responsibility_id}".format(responsibility_id=responsibility_id), json=json)

    def update_ai_agent_nexora_api_v1_ai_agents_agent_id_put(self, agent_id: str, *, json: Any = None) -> Any:
        """Update Ai Agent"""
        return self.request("PUT", "/nexora-api/v1/ai-agents/{agent_id}".format(agent_id=agent_id), json=json)

    def update_ai_team_agent_memory_nexora_api_v1_ai_team_agents_memory_memory_id_put(self, memory_id: str, *, json: Any = None) -> Any:
        """Update Ai Team Agent Memory"""
        return self.request("PUT", "/nexora-api/v1/ai-team-agents/memory/{memory_id}".format(memory_id=memory_id), json=json)

    def update_ai_team_agent_nexora_api_v1_ai_team_agents_agent_id_put(self, agent_id: str, *, json: Any = None) -> Any:
        """Update Ai Team Agent"""
        return self.request("PUT", "/nexora-api/v1/ai-team-agents/{agent_id}".format(agent_id=agent_id), json=json)

    def update_ai_team_nexora_api_v1_ai_teams_team_id_put(self, team_id: str, *, json: Any = None) -> Any:
        """Update Ai Team"""
        return self.request("PUT", "/nexora-api/v1/ai-teams/{team_id}".format(team_id=team_id), json=json)

    def update_ai_team_workflow_nexora_api_v1_ai_team_workflows_workflow_id_put(self, workflow_id: str, *, json: Any = None) -> Any:
        """Update Ai Team Workflow"""
        return self.request("PUT", "/nexora-api/v1/ai-team-workflows/{workflow_id}".format(workflow_id=workflow_id), json=json)

    def update_ai_tool_nexora_api_v1_ai_tools_tool_id_put(self, tool_id: str, *, json: Any = None) -> Any:
        """Update Ai Tool"""
        return self.request("PUT", "/nexora-api/v1/ai-tools/{tool_id}".format(tool_id=tool_id), json=json)

    def update_article_nexora_api_v1_docs_articles_article_id_put(self, article_id: str, *, json: Any = None) -> Any:
        """Update Article"""
        return self.request("PUT", "/nexora-api/v1/docs/articles/{article_id}".format(article_id=article_id), json=json)

    def update_connection_credentials_nexora_api_v1_integrations_connections_connection_id_credentials_put(self, connection_id: str, *, json: Any = None) -> Any:
        """Update Connection Credentials"""
        return self.request("PUT", "/nexora-api/v1/integrations/connections/{connection_id}/credentials".format(connection_id=connection_id), json=json)

    def update_connection_nexora_api_v1_auth_sso_connections_connection_id_patch(self, connection_id: str, *, json: Any = None) -> Any:
        """Update Connection"""
        return self.request("PATCH", "/nexora-api/v1/auth/sso/connections/{connection_id}".format(connection_id=connection_id), json=json)

    def update_contacts_nexora_api_v1_pilot_contacts_post(self, *, json: Any = None) -> Any:
        """Update Contacts"""
        return self.request("POST", "/nexora-api/v1/pilot/contacts", json=json)

    def update_credential_nexora_api_v1_credentials_credential_id_put(self, credential_id: str, *, json: Any = None) -> Any:
        """Update Credential"""
        return self.request("PUT", "/nexora-api/v1/credentials/{credential_id}".format(credential_id=credential_id), json=json)

    def update_dashboard_widgets_nexora_api_v1_product_dashboards_dash_id_widgets_put(self, dash_id: str, *, json: Any = None) -> Any:
        """Update Dashboard Widgets"""
        return self.request("PUT", "/nexora-api/v1/product/dashboards/{dash_id}/widgets".format(dash_id=dash_id), json=json)

    def update_environment_nexora_api_v1_onboarding_integrations_sessions_session_id_environment_put(self, session_id: str, *, json: Any = None) -> Any:
        """Update Environment"""
        return self.request("PUT", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/environment".format(session_id=session_id), json=json)

    def update_incident_task_nexora_api_v1_incidents_investigation_id_tasks_task_id_patch(self, investigation_id: str, task_id: str, *, json: Any = None) -> Any:
        """Update Incident Task"""
        return self.request("PATCH", "/nexora-api/v1/incidents/{investigation_id}/tasks/{task_id}".format(investigation_id=investigation_id, task_id=task_id), json=json)

    def update_notification_preferences_nexora_api_v1_customer_pilot_notification_preferences_put(self, *, json: Any = None) -> Any:
        """Update Notification Preferences"""
        return self.request("PUT", "/nexora-api/v1/customer-pilot/notification-preferences", json=json)

    def update_onboarding_step_nexora_api_v1_onboarding_session_id_step_post(self, session_id: str, *, json: Any = None) -> Any:
        """Update Onboarding Step"""
        return self.request("POST", "/nexora-api/v1/onboarding/{session_id}/step".format(session_id=session_id), json=json)

    def update_organization_nexora_api_v1_organizations_organization_id_put(self, organization_id: str, *, json: Any = None) -> Any:
        """Update Organization"""
        return self.request("PUT", "/nexora-api/v1/organizations/{organization_id}".format(organization_id=organization_id), json=json)

    def update_plan_nexora_api_v1_billing_admin_plans_plan_id_patch(self, plan_id: str, *, json: Any = None) -> Any:
        """Update Plan"""
        return self.request("PATCH", "/nexora-api/v1/billing/admin/plans/{plan_id}".format(plan_id=plan_id), json=json)

    def update_playbook_nexora_api_v1_test_playbooks_playbook_id_put(self, playbook_id: str, *, json: Any = None) -> Any:
        """Update Playbook"""
        return self.request("PUT", "/nexora-api/v1/test-playbooks/{playbook_id}".format(playbook_id=playbook_id), json=json)

    def update_postmortem_nexora_api_v1_postmortems_postmortem_id_patch(self, postmortem_id: str, *, json: Any = None) -> Any:
        """Update Postmortem"""
        return self.request("PATCH", "/nexora-api/v1/postmortems/{postmortem_id}".format(postmortem_id=postmortem_id), json=json)

    def update_project_nexora_api_v1_projects_project_id_patch(self, project_id: str, *, json: Any = None) -> Any:
        """Update Project"""
        return self.request("PATCH", "/nexora-api/v1/projects/{project_id}".format(project_id=project_id), json=json)

    def update_requirement_nexora_api_v1_requirements_requirement_id_patch(self, requirement_id: str, *, json: Any = None) -> Any:
        """Update Requirement"""
        return self.request("PATCH", "/nexora-api/v1/requirements/{requirement_id}".format(requirement_id=requirement_id), json=json)

    def update_responsibility_nexora_api_v1_responsibilities_responsibility_id_put(self, responsibility_id: str, *, json: Any = None) -> Any:
        """Update Responsibility"""
        return self.request("PUT", "/nexora-api/v1/responsibilities/{responsibility_id}".format(responsibility_id=responsibility_id), json=json)

    def update_routing_nexora_api_v1_ai_routing_put(self, *, json: Any = None) -> Any:
        """Update Routing"""
        return self.request("PUT", "/nexora-api/v1/ai/routing", json=json)

    def update_runbook_nexora_api_v1_runbooks_runbook_id_put(self, runbook_id: str, *, json: Any = None) -> Any:
        """Update Runbook"""
        return self.request("PUT", "/nexora-api/v1/runbooks/{runbook_id}".format(runbook_id=runbook_id), json=json)

    def update_security_policy_nexora_api_v1_security_policy_put(self, *, json: Any = None) -> Any:
        """Update Security Policy"""
        return self.request("PUT", "/nexora-api/v1/security-policy", json=json)

    def update_service_account_nexora_api_v1_service_accounts_sa_id_patch(self, sa_id: str, *, json: Any = None) -> Any:
        """Update Service Account"""
        return self.request("PATCH", "/nexora-api/v1/service-accounts/{sa_id}".format(sa_id=sa_id), json=json)

    def update_service_nexora_api_v1_services_service_id_patch(self, service_id: str, *, json: Any = None) -> Any:
        """Update Service"""
        return self.request("PATCH", "/nexora-api/v1/services/{service_id}".format(service_id=service_id), json=json)

    def update_service_owner_nexora_api_v1_oncall_service_owners_owner_id_patch(self, owner_id: str, *, json: Any = None) -> Any:
        """Update Service Owner"""
        return self.request("PATCH", "/nexora-api/v1/oncall/service-owners/{owner_id}".format(owner_id=owner_id), json=json)

    def update_stage_nexora_api_v1_stages_stage_id_put(self, stage_id: str, *, json: Any = None) -> Any:
        """Update Stage"""
        return self.request("PUT", "/nexora-api/v1/stages/{stage_id}".format(stage_id=stage_id), json=json)

    def update_team_nexora_api_v1_teams_team_id_put(self, team_id: str, *, json: Any = None) -> Any:
        """Update Team"""
        return self.request("PUT", "/nexora-api/v1/teams/{team_id}".format(team_id=team_id), json=json)

    def update_variable_nexora_api_v1_org_config_variables_variable_id_put(self, variable_id: str, *, json: Any = None) -> Any:
        """Update Variable"""
        return self.request("PUT", "/nexora-api/v1/org-config/variables/{variable_id}".format(variable_id=variable_id), json=json)

    def update_workflow_nexora_api_v1_workflows_workflow_id_put(self, workflow_id: str, *, json: Any = None) -> Any:
        """Update Workflow"""
        return self.request("PUT", "/nexora-api/v1/workflows/{workflow_id}".format(workflow_id=workflow_id), json=json)

    def update_workflow_schedule_nexora_api_v1_ai_team_workflow_schedules_schedule_id_put(self, schedule_id: str, *, json: Any = None) -> Any:
        """Update Workflow Schedule"""
        return self.request("PUT", "/nexora-api/v1/ai-team-workflow-schedules/{schedule_id}".format(schedule_id=schedule_id), json=json)

    def update_workspace_nexora_api_v1_workspaces_workspace_id_patch(self, workspace_id: str, *, json: Any = None) -> Any:
        """Update Workspace"""
        return self.request("PATCH", "/nexora-api/v1/workspaces/{workspace_id}".format(workspace_id=workspace_id), json=json)

    def upgrade_post_verify_nexora_api_v1_ga_upgrade_post_verify_get(self) -> Any:
        """Upgrade Post Verify"""
        return self.request("GET", "/nexora-api/v1/ga/upgrade/post-verify")

    def upgrade_pre_check_nexora_api_v1_ga_upgrade_pre_check_get(self) -> Any:
        """Upgrade Pre Check"""
        return self.request("GET", "/nexora-api/v1/ga/upgrade/pre-check")

    def upload_ai_team_document_nexora_api_v1_ai_teams_team_id_documents_post(self, team_id: str, *, json: Any = None) -> Any:
        """Upload Ai Team Document"""
        return self.request("POST", "/nexora-api/v1/ai-teams/{team_id}/documents".format(team_id=team_id), json=json)

    def upsert_notification_template_nexora_api_v1_platform_notifications_templates_post(self, *, json: Any = None) -> Any:
        """Upsert Notification Template"""
        return self.request("POST", "/nexora-api/v1/platform/notifications/templates", json=json)

    def usage_dashboard_nexora_api_v1_billing_usage_get(self) -> Any:
        """Usage Dashboard"""
        return self.request("GET", "/nexora-api/v1/billing/usage")

    def validate_connection_nexora_api_v1_integrations_connections_connection_id_validate_post(self, connection_id: str) -> Any:
        """Validate Connection"""
        return self.request("POST", "/nexora-api/v1/integrations/connections/{connection_id}/validate".format(connection_id=connection_id))

    def validate_credential_for_deploy_nexora_api_v1_credentials_credential_id_validate_post(self, credential_id: str) -> Any:
        """Validate Credential For Deploy"""
        return self.request("POST", "/nexora-api/v1/credentials/{credential_id}/validate".format(credential_id=credential_id))

    def validate_license_nexora_api_v1_billing_licenses_validate_post(self, *, json: Any = None) -> Any:
        """Validate License"""
        return self.request("POST", "/nexora-api/v1/billing/licenses/validate", json=json)

    def validate_provider_nexora_api_v1_security_providers_provider_id_validate_post(self, provider_id: str) -> Any:
        """Validate Provider"""
        return self.request("POST", "/nexora-api/v1/security/providers/{provider_id}/validate".format(provider_id=provider_id))

    def validate_session_nexora_api_v1_onboarding_integrations_sessions_session_id_validate_post(self, session_id: str) -> Any:
        """Validate Session"""
        return self.request("POST", "/nexora-api/v1/onboarding/integrations/sessions/{session_id}/validate".format(session_id=session_id))

    def value_proposition_nexora_api_v1_sales_value_proposition_post(self, *, json: Any = None) -> Any:
        """Value Proposition"""
        return self.request("POST", "/nexora-api/v1/sales/value-proposition", json=json)

    def verification_audit_nexora_api_v1_customer_success_verification_audit_get(self) -> Any:
        """Verification Audit"""
        return self.request("GET", "/nexora-api/v1/customer-success/verification-audit")

    def verification_dashboard_nexora_api_v1_customer_success_verification_dashboard_get(self) -> Any:
        """Verification Dashboard"""
        return self.request("GET", "/nexora-api/v1/customer-success/verification-dashboard")

    def verification_summary_nexora_api_v1_customer_success_verification_summary_get(self) -> Any:
        """Verification Summary"""
        return self.request("GET", "/nexora-api/v1/customer-success/verification-summary")

    def verify_ai_tool_connection_nexora_api_v1_ai_tools_tool_id_verify_post(self, tool_id: str) -> Any:
        """Verify Ai Tool Connection"""
        return self.request("POST", "/nexora-api/v1/ai-tools/{tool_id}/verify".format(tool_id=tool_id))

    def verify_backup_nexora_api_v1_ga_backups_backup_id_verify_post(self, backup_id: str) -> Any:
        """Verify Backup"""
        return self.request("POST", "/nexora-api/v1/ga/backups/{backup_id}/verify".format(backup_id=backup_id))

    def verify_credential_nexora_api_v1_credentials_credential_id_verify_post(self, credential_id: str) -> Any:
        """Verify Credential"""
        return self.request("POST", "/nexora-api/v1/credentials/{credential_id}/verify".format(credential_id=credential_id))

    def verify_integration_nexora_api_v1_integrations_verify_post(self, *, json: Any = None) -> Any:
        """Verify Integration"""
        return self.request("POST", "/nexora-api/v1/integrations/verify", json=json)

    def verify_live_operation_nexora_api_v1_pilot_live_operations_operation_id_verify_post(self, operation_id: str, *, json: Any = None) -> Any:
        """Verify Live Operation"""
        return self.request("POST", "/nexora-api/v1/pilot/live-operations/{operation_id}/verify".format(operation_id=operation_id), json=json)

    def verify_nexora_api_v1_audit_verify_get(self) -> Any:
        """Verify"""
        return self.request("GET", "/nexora-api/v1/audit/verify")

    def verify_release_nexora_api_v1_delivery_release_reliability_reliability_id_verify_post(self, reliability_id: str) -> Any:
        """Verify Release"""
        return self.request("POST", "/nexora-api/v1/delivery/release-reliability/{reliability_id}/verify".format(reliability_id=reliability_id))

    def video_library_nexora_api_v1_customer_success_videos_get(self, *, params: dict | None = None) -> Any:
        """Video Library"""
        return self.request("GET", "/nexora-api/v1/customer-success/videos", params=params)

    def videos_for_module_nexora_api_v1_customer_success_videos_by_module_module_get(self, module: str) -> Any:
        """Videos For Module"""
        return self.request("GET", "/nexora-api/v1/customer-success/videos/by-module/{module}".format(module=module))

    def visual_coverage_nexora_api_v1_customer_success_visual_coverage_get(self) -> Any:
        """Visual Coverage"""
        return self.request("GET", "/nexora-api/v1/customer-success/visual-coverage")

    def visual_readiness_nexora_api_v1_customer_success_visual_readiness_get(self) -> Any:
        """Visual Readiness"""
        return self.request("GET", "/nexora-api/v1/customer-success/visual-readiness")

    def vulnerabilities_nexora_api_v1_security_vulnerabilities_get(self) -> Any:
        """Vulnerabilities"""
        return self.request("GET", "/nexora-api/v1/security/vulnerabilities")

    def whoami_nexora_api_v1_identity_whoami_get(self) -> Any:
        """Whoami"""
        return self.request("GET", "/nexora-api/v1/identity/whoami")

    def write_memory_nexora_api_v1_ai_memory_post(self, *, json: Any = None) -> Any:
        """Write Memory"""
        return self.request("POST", "/nexora-api/v1/ai/memory", json=json)
