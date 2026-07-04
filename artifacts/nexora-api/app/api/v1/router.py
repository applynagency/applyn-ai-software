from fastapi import APIRouter

from app.api.v1.agents import router as agent_router
from app.api.v1.ai_agent_components import router as ai_agent_component_router
from app.api.v1.ai_agent_templates import router as ai_agent_template_router
from app.api.v1.ai_agents import router as ai_agent_router
from app.api.v1.ai_platform import router as ai_platform_router
from app.api.v1.ai_team_agents import router as ai_team_agent_router
from app.api.v1.ai_team_workflow_schedules import router as ai_team_workflow_schedule_router
from app.api.v1.ai_team_workflows import router as ai_team_workflow_router
from app.api.v1.ai_teams import router as ai_team_router
from app.api.v1.ai_tools import router as ai_tools_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.approval_decisions import router as approval_decisions_router
from app.api.v1.approval_workflow import router as approval_workflow_router
from app.api.v1.architecture import router as architecture_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.backend_architect import router as backend_architect_router
from app.api.v1.backend_code_review import router as backend_code_review_router
from app.api.v1.backend_execution import router as backend_execution_router
from app.api.v1.backend_v1 import router as backend_v1_router
from app.api.v1.backend_v2 import router as backend_v2_router
from app.api.v1.backend_v3 import router as backend_v3_router
from app.api.v1.billing import router as billing_router
from app.api.v1.business_analyst import router as business_analyst_router
from app.api.v1.capacity import router as capacity_router
from app.api.v1.change_failure import router as change_failure_router
from app.api.v1.cicd import router as cicd_router
from app.api.v1.cost_optimization import router as cost_optimization_router
from app.api.v1.credentials import router as credentials_router
from app.api.v1.customer_success import router as customer_success_router
from app.api.v1.demo_asset import router as demo_asset_router
from app.api.v1.demo_organization import router as demo_organization_router
from app.api.v1.demo_sales_mode import router as demo_sales_mode_router
from app.api.v1.demo_scenarios import router as demo_scenarios_router
from app.api.v1.demo_walkthroughs import router as demo_walkthroughs_router
from app.api.v1.deployment_agent import router as deployment_agent_router
from app.api.v1.deployment_risk import router as deployment_risk_router
from app.api.v1.deployment_safety import router as deployment_safety_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.docker_agent import router as docker_agent_router
from app.api.v1.docs_readiness import router as docs_readiness_router
from app.api.v1.documentation import router as documentation_router
from app.api.v1.documentation_generator import router as documentation_generator_router
from app.api.v1.executive_report import router as executive_report_router
from app.api.v1.frontend_architect import router as frontend_architect_router
from app.api.v1.frontend_code_review import router as frontend_code_review_router
from app.api.v1.frontend_execution import router as frontend_execution_router
from app.api.v1.frontend_v1 import router as frontend_v1_router
from app.api.v1.frontend_v2 import router as frontend_v2_router
from app.api.v1.frontend_v3 import router as frontend_v3_router
from app.api.v1.fullstack_assembly import router as fullstack_assembly_router
from app.api.v1.grounded_copilot import router as grounded_copilot_router
from app.api.v1.identity import router as identity_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.infrastructure_architect import router as infrastructure_architect_router
from app.api.v1.integration import router as integration_router
from app.api.v1.integration_onboarding import router as integration_onboarding_router
from app.api.v1.integration_tests import router as integration_tests_router
from app.api.v1.invitations import router as invitation_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.kubernetes import router as kubernetes_router
from app.api.v1.lifecycle import router as lifecycle_router
from app.api.v1.mfa import router as mfa_router
from app.api.v1.monitoring import router as monitoring_router
from app.api.v1.observability import router as observability_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.oncall import router as oncall_router
from app.api.v1.org_config import router as org_config_router
from app.api.v1.organizations import router as organization_router
from app.api.v1.performance_tests import router as performance_tests_router
from app.api.v1.platform import router as platform_router
from app.api.v1.postmortem import router as postmortem_router
from app.api.v1.product_tour import router as product_tour_router
from app.api.v1.projects import router as project_router
from app.api.v1.qa_approvals import router as qa_approvals_router
from app.api.v1.qa_architect import router as qa_architect_router
from app.api.v1.reliability_dashboard import router as reliability_dashboard_router
from app.api.v1.reliability_maturity import router as reliability_maturity_router
from app.api.v1.remediation_actions import router as remediation_actions_router
from app.api.v1.requirements import router as requirement_router
from app.api.v1.responsibilities import router as responsibility_router
from app.api.v1.roi import router as roi_router
from app.api.v1.runbook import router as runbook_router
from app.api.v1.sales_enablement import router as sales_enablement_router
from app.api.v1.scim import router as scim_router
from app.api.v1.security_policy import router as security_policy_router
from app.api.v1.security_tests import router as security_tests_router
from app.api.v1.service_accounts import router as service_accounts_router
from app.api.v1.service_dependency import router as service_dependency_router
from app.api.v1.service_health import router as service_health_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.sre_approval import router as sre_approval_router
from app.api.v1.sso import router as sso_router
from app.api.v1.stages import router as stage_router
from app.api.v1.team_templates import router as team_template_router
from app.api.v1.teams import router as team_router
from app.api.v1.test_playbook import router as test_playbook_router
from app.api.v1.uiux import router as uiux_router
from app.api.v1.unit_tests import router as unit_tests_router
from app.api.v1.war_room import router as war_room_router
from app.api.v1.war_room_collab import router as war_room_collab_router
from app.api.v1.workflow_approvals import router as workflow_approval_router
from app.api.v1.workflow_executions import router as workflow_execution_router
from app.api.v1.workflow_templates import router as workflow_template_router
from app.api.v1.workflows import router as workflow_router
from app.api.v1.workspaces import router as workspace_router
from app.core.config import settings

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth_router)
api_router.include_router(sso_router)
api_router.include_router(scim_router)
api_router.include_router(audit_router)
if settings.IDENTITY_ENABLED:
    api_router.include_router(api_keys_router)
    api_router.include_router(service_accounts_router)
    api_router.include_router(sessions_router)
    api_router.include_router(security_policy_router)
    api_router.include_router(mfa_router)
    api_router.include_router(identity_router)
if settings.BILLING_ENABLED:
    api_router.include_router(billing_router)
if settings.AI_PLATFORM_ENABLED:
    api_router.include_router(ai_platform_router)
if settings.PLATFORM_CONVERGENCE_ENABLED:
    api_router.include_router(platform_router)
if settings.HARDENING_ENABLED:
    from app.api.v1.hardening import router as hardening_router

    api_router.include_router(hardening_router)
if settings.PRODUCT_EXCELLENCE_ENABLED:
    from app.api.v1.product import router as product_router

    api_router.include_router(product_router)
if settings.AUTONOMOUS_SRE_ENABLED:
    from app.api.v1.sre import router as sre_router

    api_router.include_router(sre_router)
if settings.GA_READINESS_ENABLED:
    from app.api.v1.ga import router as ga_router

    api_router.include_router(ga_router)
if settings.CONTROL_PLANE_ENABLED:
    from app.api.v1.control_plane import router as control_plane_router

    api_router.include_router(control_plane_router)
    from app.api.v1.k8s_operations import router as k8s_operations_router

    api_router.include_router(k8s_operations_router)
if settings.DELIVERY_ENABLED:
    from app.api.v1.delivery import router as delivery_router

    api_router.include_router(delivery_router)
if settings.OPS_WORKSPACE_ENABLED:
    from app.api.v1.devops_sre_workspace import router as ops_workspace_router

    api_router.include_router(ops_workspace_router)
if settings.PLATFORM_ENGINEERING_ENABLED:
    from app.api.v1.platform_engineering import router as platform_engineering_router

    api_router.include_router(platform_engineering_router)
if settings.AI_OPERATOR_ENABLED:
    from app.api.v1.operator import router as operator_router

    api_router.include_router(operator_router)
if settings.OBSERVABILITY_PLATFORM_ENABLED:
    from app.api.v1.observability_platform import router as observability_platform_router

    api_router.include_router(observability_platform_router)
if settings.INCIDENT_RESPONSE_PLATFORM_ENABLED:
    from app.api.v1.incident_response import router as incident_response_router

    api_router.include_router(incident_response_router)
if settings.SECURITY_PLATFORM_ENABLED:
    from app.api.v1.security_platform import router as security_platform_router

    api_router.include_router(security_platform_router)
if settings.PILOT_MODE_ENABLED:
    from app.api.v1.pilot import router as pilot_router
    from app.api.v1.customer_pilot import router as customer_pilot_router

    api_router.include_router(pilot_router)
    api_router.include_router(customer_pilot_router)
api_router.include_router(jobs_router)
api_router.include_router(organization_router)
api_router.include_router(invitation_router)
api_router.include_router(team_router)
api_router.include_router(responsibility_router)
api_router.include_router(team_template_router)
api_router.include_router(workflow_router)
api_router.include_router(stage_router)
api_router.include_router(workflow_template_router)
api_router.include_router(ai_agent_router)
api_router.include_router(ai_agent_component_router)
api_router.include_router(ai_agent_template_router)
api_router.include_router(ai_team_router)
api_router.include_router(ai_team_agent_router)
api_router.include_router(ai_team_workflow_router)
api_router.include_router(ai_team_workflow_schedule_router)
api_router.include_router(ai_tools_router)
api_router.include_router(incidents_router)
api_router.include_router(remediation_actions_router)
api_router.include_router(deployment_risk_router)
api_router.include_router(monitoring_router)
api_router.include_router(oncall_router)
api_router.include_router(service_health_router)
api_router.include_router(deployment_safety_router)
api_router.include_router(capacity_router)
api_router.include_router(cost_optimization_router)
api_router.include_router(postmortem_router)
api_router.include_router(service_dependency_router)
api_router.include_router(change_failure_router)
api_router.include_router(runbook_router)
# The single, unified AI assistant: /v1/copilot (Reliability + SRE + Grounded
# copilots were converged into this one surface in Sprint 60B).
api_router.include_router(grounded_copilot_router)
api_router.include_router(reliability_dashboard_router)
api_router.include_router(reliability_maturity_router)
api_router.include_router(architecture_router)
api_router.include_router(executive_report_router)
api_router.include_router(war_room_router)
if settings.WAR_ROOM_REALTIME_ENABLED:
    api_router.include_router(war_room_collab_router)
api_router.include_router(discovery_router)
api_router.include_router(integration_router)
api_router.include_router(integration_onboarding_router)
api_router.include_router(onboarding_router)
api_router.include_router(documentation_router)
api_router.include_router(test_playbook_router)
api_router.include_router(demo_asset_router)
api_router.include_router(product_tour_router)
api_router.include_router(documentation_generator_router)
api_router.include_router(customer_success_router)
api_router.include_router(docs_readiness_router)
api_router.include_router(demo_organization_router)
api_router.include_router(demo_scenarios_router)
api_router.include_router(demo_walkthroughs_router)
api_router.include_router(demo_sales_mode_router)
if settings.ROI_ENABLED:
    api_router.include_router(roi_router)
api_router.include_router(sales_enablement_router)
api_router.include_router(workflow_approval_router)
api_router.include_router(workflow_execution_router)
api_router.include_router(business_analyst_router)
api_router.include_router(backend_architect_router)
api_router.include_router(backend_v1_router)
api_router.include_router(backend_v2_router)
api_router.include_router(backend_v3_router)
api_router.include_router(backend_code_review_router)
api_router.include_router(backend_execution_router)
api_router.include_router(uiux_router)
api_router.include_router(frontend_architect_router)
api_router.include_router(frontend_v1_router)
api_router.include_router(frontend_v2_router)
api_router.include_router(frontend_v3_router)
api_router.include_router(frontend_code_review_router)
api_router.include_router(frontend_execution_router)
api_router.include_router(qa_architect_router)
api_router.include_router(unit_tests_router)
api_router.include_router(integration_tests_router)
api_router.include_router(security_tests_router)
api_router.include_router(performance_tests_router)
api_router.include_router(qa_approvals_router)
api_router.include_router(infrastructure_architect_router)
api_router.include_router(docker_agent_router)
api_router.include_router(cicd_router)
api_router.include_router(kubernetes_router)
api_router.include_router(observability_router)
api_router.include_router(sre_approval_router)
api_router.include_router(fullstack_assembly_router)
api_router.include_router(approval_workflow_router)
api_router.include_router(approval_decisions_router)
api_router.include_router(deployment_agent_router)
api_router.include_router(deployments_router)
api_router.include_router(credentials_router)
api_router.include_router(org_config_router)
api_router.include_router(lifecycle_router)
api_router.include_router(workspace_router)
api_router.include_router(project_router)
api_router.include_router(requirement_router)
api_router.include_router(agent_router)
