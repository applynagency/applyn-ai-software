// Auto-generated Nexora TypeScript SDK. Do not edit by hand.
// Regenerate with `python -m scripts.generate_sdk`.

export interface NexoraClientOptions {
  baseUrl: string;
  token?: string;
}

export class NexoraClient {
  private baseUrl: string;
  private token?: string;

  constructor(opts: NexoraClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.token = opts.token;
  }

  async request<T = unknown>(
    method: string,
    path: string,
    opts: { params?: Record<string, unknown>; body?: unknown } = {}
  ): Promise<T> {
    const url = new URL(this.baseUrl + path);
    if (opts.params) {
      for (const [k, v] of Object.entries(opts.params)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      }
    }
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const res = await fetch(url.toString(), {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) throw new Error(`Nexora API ${res.status}: ${await res.text()}`);
    const ct = res.headers.get("content-type") || "";
    return (ct.includes("application/json") ? await res.json() : await res.text()) as T;
  }

  abortRolloutNexoraApiV1DeliveryReleaseReliabilityReliabilityIdAbortPost(reliability_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/abort`);
  }

  academyDashboardNexoraApiV1CustomerSuccessAcademyGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/academy`, { params: opts.params });
  }

  academyProgressNexoraApiV1CustomerSuccessAcademyProgressPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/academy/progress`, { body: opts.body });
  }

  academyTrackNexoraApiV1CustomerSuccessAcademyTracksKeyGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/academy/tracks/${key}`, { params: opts.params });
  }

  academyTrackProgressNexoraApiV1CustomerSuccessAcademyTracksKeyProgressPost(key: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/academy/tracks/${key}/progress`, { body: opts.body });
  }

  academyTracksNexoraApiV1CustomerSuccessAcademyTracksGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/academy/tracks`, { params: opts.params });
  }

  acceptInvitationNexoraApiV1InvitationsAcceptPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/invitations/accept`, { body: opts.body });
  }

  acknowledgeCommunicationNexoraApiV1CustomerPilotCommunicationsCommunicationIdAcknowledgePost(communication_id: string) {
    return this.request("POST", `/nexora-api/v1/customer-pilot/communications/${communication_id}/acknowledge`);
  }

  acknowledgeConnectionExpiryNexoraApiV1IntegrationsConnectionsConnectionIdAcknowledgeExpiryPost(connection_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/integrations/connections/${connection_id}/acknowledge-expiry`, { body: opts.body });
  }

  acknowledgeDriftNexoraApiV1PlatformEngineeringDriftFindingIdAcknowledgePost(finding_id: string) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/drift/${finding_id}/acknowledge`);
  }

  acknowledgeIncidentNexoraApiV1IncidentsInvestigationIdAcknowledgePost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/acknowledge`, { body: opts.body });
  }

  acknowledgeNexoraApiV1OncallIncidentsIncidentIdAcknowledgePost(incident_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/oncall/incidents/${incident_id}/acknowledge`, { body: opts.body });
  }

  acknowledgeSessionNexoraApiV1OnboardingIntegrationsSessionsSessionIdAcknowledgePost(session_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/acknowledge`, { body: opts.body });
  }

  addCommentNexoraApiV1ProductCollaborationResourceTypeResourceIdCommentsPost(resource_type: string, resource_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/collaboration/${resource_type}/${resource_id}/comments`, { body: opts.body });
  }

  addIncidentCommentNexoraApiV1IncidentsInvestigationIdCommentsPost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/comments`, { body: opts.body });
  }

  addOrganizationMemberNexoraApiV1OrganizationsOrganizationIdMembersPost(organization_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/organizations/${organization_id}/members`, { body: opts.body });
  }

  addReactionNexoraApiV1ProductCollaborationReactionsPost(opts: { params?: Record<string, unknown>; body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/collaboration/reactions`, { params: opts.params, body: opts.body });
  }

  addStatusComponentNexoraApiV1IncidentsStatusPagesPageIdComponentsPost(page_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/status-pages/${page_id}/components`, { body: opts.body });
  }

  adoptionAnalyticsAnalyzeNexoraApiV1CustomerSuccessAdoptionAnalyticsAnalyzePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/adoption-analytics/analyze`, { body: opts.body });
  }

  adoptionAnalyticsNexoraApiV1CustomerSuccessAdoptionAnalyticsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/adoption-analytics`);
  }

  advanceExecutionStageNexoraApiV1PilotExecutionStagesStageKeyAdvancePost(stage_key: string) {
    return this.request("POST", `/nexora-api/v1/pilot/execution/stages/${stage_key}/advance`);
  }

  aiBudgetNexoraApiV1AiBudgetGet() {
    return this.request("GET", `/nexora-api/v1/ai/budget`);
  }

  aiContextNexoraApiV1OperatorAiContextGet() {
    return this.request("GET", `/nexora-api/v1/operator/ai-context`);
  }

  aiContextNexoraApiV1OpsWorkspaceAiContextPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ops-workspace/ai-context`, { body: opts.body });
  }

  aiContextNexoraApiV1PlatformEngineeringAiContextGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform-engineering/ai-context`, { params: opts.params });
  }

  aiHealthNexoraApiV1AiHealthGet() {
    return this.request("GET", `/nexora-api/v1/ai/health`);
  }

  aiToolConnectionStatusNexoraApiV1AiToolsToolIdConnectionStatusGet(tool_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-tools/${tool_id}/connection-status`);
  }

  alertIntelligenceNexoraApiV1ObservabilityAlertsIntelligenceGet() {
    return this.request("GET", `/nexora-api/v1/observability/alerts/intelligence`);
  }

  analyticsNexoraApiV1SecurityAnalyticsGet() {
    return this.request("GET", `/nexora-api/v1/security/analytics`);
  }

  analyticsSummaryNexoraApiV1ProductAnalyticsSummaryGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product/analytics/summary`, { params: opts.params });
  }

  analyzeChangeFailureNexoraApiV1ChangeFailurePredictionAnalyzePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/change-failure-prediction/analyze`, { body: opts.body });
  }

  analyzeCostNexoraApiV1CostOptimizationAnalyzePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/cost-optimization/analyze`, { body: opts.body });
  }

  analyzeDeploymentRiskNexoraApiV1DeploymentRiskAnalyzePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/deployment-risk/analyze`, { body: opts.body });
  }

  analyzeDeploymentSafetyNexoraApiV1DeploymentSafetyAnalyzePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/deployment-safety/analyze`, { body: opts.body });
  }

  analyzeNexoraApiV1OperatorAnalyzePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/operator/analyze`, { body: opts.body });
  }

  analyzeNexoraApiV1ReliabilityAnalyzePost() {
    return this.request("POST", `/nexora-api/v1/reliability/analyze`);
  }

  analyzeRcaNexoraApiV1SreRcaIncidentIdAnalyzePost(incident_id: string) {
    return this.request("POST", `/nexora-api/v1/sre/rca/${incident_id}/analyze`);
  }

  annotationSummaryNexoraApiV1CustomerSuccessAnnotationsSummaryGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/annotations/summary`);
  }

  applyAiAgentTemplateNexoraApiV1AiAgentTemplatesApplyPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-agent-templates/apply`, { body: opts.body });
  }

  applyTeamTemplateNexoraApiV1TeamTemplatesApplyPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/team-templates/apply`, { body: opts.body });
  }

  applyWorkflowTemplateNexoraApiV1WorkflowTemplatesApplyPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflow-templates/apply`, { body: opts.body });
  }

  approveAgentNexoraApiV1AiAgentsRunIdApprovePost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/ai/agents/${run_id}/approve`);
  }

  approveArtifactNexoraApiV1ApprovalArtifactIdApprovePost(artifact_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/approval/${artifact_id}/approve`, { body: opts.body });
  }

  approveCommanderNexoraApiV1SreCommanderCommanderIdApprovePost(commander_id: string) {
    return this.request("POST", `/nexora-api/v1/sre/commander/${commander_id}/approve`);
  }

  approveExecutionNexoraApiV1PlatformExecutionsRunIdApprovePost(run_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/executions/${run_id}/approve`, { body: opts.body });
  }

  approveReleaseNexoraApiV1DeliveryReleasesReleaseIdApprovePost(release_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/releases/${release_id}/approve`);
  }

  approveRemediationActionNexoraApiV1RemediationActionsActionIdApprovePost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/approve`, { body: opts.body });
  }

  approveRunbookExecutionNexoraApiV1SreRunbooksExecutionsExecutionIdApprovePost(execution_id: string) {
    return this.request("POST", `/nexora-api/v1/sre/runbooks/executions/${execution_id}/approve`);
  }

  approveWorkflowApprovalNexoraApiV1WorkflowApprovalsApprovalIdApprovePost(approval_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflow-approvals/${approval_id}/approve`, { body: opts.body });
  }

  archiveAiAgentNexoraApiV1AiAgentsAgentIdArchivePost(agent_id: string) {
    return this.request("POST", `/nexora-api/v1/ai-agents/${agent_id}/archive`);
  }

  archiveTeamNexoraApiV1TeamsTeamIdArchivePost(team_id: string) {
    return this.request("POST", `/nexora-api/v1/teams/${team_id}/archive`);
  }

  archiveWorkflowNexoraApiV1WorkflowsWorkflowIdArchivePost(workflow_id: string) {
    return this.request("POST", `/nexora-api/v1/workflows/${workflow_id}/archive`);
  }

  assessChangeRiskNexoraApiV1SreChangeRiskAssessPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/change-risk/assess`, { body: opts.body });
  }

  assignAgentToStageNexoraApiV1AiAgentsAgentIdAssignPost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-agents/${agent_id}/assign`, { body: opts.body });
  }

  assignAiTeamAgentToolNexoraApiV1AiTeamAgentsAgentIdToolsPost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-agents/${agent_id}/tools`, { body: opts.body });
  }

  assignIncidentNexoraApiV1IncidentsInvestigationIdAssignPost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/assign`, { body: opts.body });
  }

  assignPlanNexoraApiV1BillingAdminOrgsOrgIdAssignPlanPost(org_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/admin/orgs/${org_id}/assign-plan`, { body: opts.body });
  }

  assignTeamNexoraApiV1StagesStageIdTeamsPost(stage_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/stages/${stage_id}/teams`, { body: opts.body });
  }

  attachAiToolCredentialNexoraApiV1AiToolsToolIdCredentialsPost(tool_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-tools/${tool_id}/credentials`, { body: opts.body });
  }

  automationSuggestionsNexoraApiV1OpsWorkspaceAutomationSuggestionsGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/automation-suggestions`);
  }

  backfillDryRunNexoraApiV1SecurityBackfillDryRunPost() {
    return this.request("POST", `/nexora-api/v1/security/backfill/dry-run`);
  }

  backfillExecuteNexoraApiV1SecurityBackfillExecutePost() {
    return this.request("POST", `/nexora-api/v1/security/backfill/execute`);
  }

  backfillStatusNexoraApiV1SecurityBackfillStatusGet() {
    return this.request("GET", `/nexora-api/v1/security/backfill/status`);
  }

  bindRemediationActionNexoraApiV1RemediationActionsActionIdBindPost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/bind`, { body: opts.body });
  }

  blastRadiusDashboardNexoraApiV1BlastRadiusDashboardGet() {
    return this.request("GET", `/nexora-api/v1/blast-radius/dashboard`);
  }

  bulkNexoraApiV1ScimV2BulkPost() {
    return this.request("POST", `/nexora-api/v1/scim/v2/Bulk`);
  }

  cancelAgentNexoraApiV1AiAgentsRunIdCancelPost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/ai/agents/${run_id}/cancel`);
  }

  cancelCommunicationNexoraApiV1PilotCommunicationsCommunicationIdCancelPost(communication_id: string) {
    return this.request("POST", `/nexora-api/v1/pilot/communications/${communication_id}/cancel`);
  }

  cancelExecutionNexoraApiV1PlatformExecutionsRunIdCancelPost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/platform/executions/${run_id}/cancel`);
  }

  cancelJobNexoraApiV1JobsJobIdCancelPost(job_id: string) {
    return this.request("POST", `/nexora-api/v1/jobs/${job_id}/cancel`);
  }

  cancelSessionNexoraApiV1OnboardingIntegrationsSessionsSessionIdCancelPost(session_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/cancel`, { body: opts.body });
  }

  capacityDashboardNexoraApiV1CapacityDashboardGet() {
    return this.request("GET", `/nexora-api/v1/capacity/dashboard`);
  }

  captureBaselineNexoraApiV1PilotBaselineCapturePost() {
    return this.request("POST", `/nexora-api/v1/pilot/baseline/capture`);
  }

  captureIncidentKnowledgeNexoraApiV1SreLearningCapturePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/learning/capture`, { body: opts.body });
  }

  changeCenterNexoraApiV1OpsWorkspaceChangesGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/changes`);
  }

  changeFailureDashboardNexoraApiV1ChangeFailurePredictionDashboardGet() {
    return this.request("GET", `/nexora-api/v1/change-failure-prediction/dashboard`);
  }

  chatNexoraApiV1CopilotChatPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/copilot/chat`, { body: opts.body });
  }

  chatStreamNexoraApiV1CopilotChatStreamPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/copilot/chat/stream`, { body: opts.body });
  }

  checkExecutionReadinessNexoraApiV1PilotLiveOperationsOperationIdExecutionReadinessPost(operation_id: string) {
    return this.request("POST", `/nexora-api/v1/pilot/live-operations/${operation_id}/execution-readiness`);
  }

  checkPilotReadinessNexoraApiV1PilotReadinessCheckPost() {
    return this.request("POST", `/nexora-api/v1/pilot/readiness/check`);
  }

  checkpointExecutionNexoraApiV1PlatformExecutionsRunIdCheckpointPost(run_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/executions/${run_id}/checkpoint`, { body: opts.body });
  }

  clonePlanNexoraApiV1BillingAdminPlansPlanIdClonePost(plan_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/admin/plans/${plan_id}/clone`, { body: opts.body });
  }

  closeInternalPilotNexoraApiV1PilotClosurePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/closure`, { body: opts.body });
  }

  cloudCostsNexoraApiV1ControlPlaneCloudAccountsAccountIdCostsGet(account_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/cloud-accounts/${account_id}/costs`);
  }

  cloudPostureNexoraApiV1SecurityCloudGet() {
    return this.request("GET", `/nexora-api/v1/security/cloud`);
  }

  clusterReadNexoraApiV1ControlPlaneClustersClusterIdReadPost(cluster_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/read`, { params: opts.params });
  }

  collectDiagnosticsNexoraApiV1ControlPlaneClustersClusterIdK8SDiagnosticsPost(cluster_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/diagnostics`, { body: opts.body });
  }

  commandPaletteNexoraApiV1ProductCommandsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product/commands`, { params: opts.params });
  }

  commentCommunicationNexoraApiV1CustomerPilotCommunicationsCommunicationIdCommentPost(communication_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-pilot/communications/${communication_id}/comment`, { body: opts.body });
  }

  competitiveComparisonNexoraApiV1SalesCompetitiveComparisonGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/sales/competitive-comparison`, { params: opts.params });
  }

  completeNexoraApiV1AiCompletePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/complete`, { body: opts.body });
  }

  completeOnboardingNexoraApiV1OnboardingSessionIdCompletePost(session_id: string) {
    return this.request("POST", `/nexora-api/v1/onboarding/${session_id}/complete`);
  }

  completeTourNexoraApiV1ProductToursTourIdCompletePost(tour_id: string) {
    return this.request("POST", `/nexora-api/v1/product-tours/${tour_id}/complete`);
  }

  complianceNexoraApiV1SecurityComplianceGet() {
    return this.request("GET", `/nexora-api/v1/security/compliance`);
  }

  confirmLiveOperationNexoraApiV1PilotLiveOperationsOperationIdConfirmPost(operation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/live-operations/${operation_id}/confirm`, { body: opts.body });
  }

  confirmMfaNexoraApiV1AuthMfaConfirmPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/mfa/confirm`, { body: opts.body });
  }

  connectIntegrationNexoraApiV1IntegrationsConnectPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/integrations/connect`, { body: opts.body });
  }

  connectSourceNexoraApiV1DeliverySourceConnectionsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/source-connections`, { body: opts.body });
  }

  consistencyNexoraApiV1CustomerSuccessConsistencyGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/consistency`);
  }

  contextualHelpNexoraApiV1ProductToursContextualGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product-tours/contextual`, { params: opts.params });
  }

  coordinateIncidentNexoraApiV1IncidentsCoordinatePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/coordinate`, { body: opts.body });
  }

  correlateNexoraApiV1ObservabilityCorrelationPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/observability/correlation`, { body: opts.body });
  }

  costDashboardNexoraApiV1CostOptimizationDashboardGet() {
    return this.request("GET", `/nexora-api/v1/cost-optimization/dashboard`);
  }

  costOperationsNexoraApiV1OpsWorkspaceCostGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/cost`);
  }

  costReportNexoraApiV1AiCostGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai/cost`, { params: opts.params });
  }

  createAgentInputNexoraApiV1AiAgentsAgentIdInputsPost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-agents/${agent_id}/inputs`, { body: opts.body });
  }

  createAgentOutputNexoraApiV1AiAgentsAgentIdOutputsPost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-agents/${agent_id}/outputs`, { body: opts.body });
  }

  createAgentResponsibilityNexoraApiV1AiAgentsAgentIdResponsibilitiesPost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-agents/${agent_id}/responsibilities`, { body: opts.body });
  }

  createAiAgentNexoraApiV1AiAgentsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-agents`, { body: opts.body });
  }

  createAiTeamAgentMemoryNexoraApiV1AiTeamAgentsAgentIdMemoryPost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-agents/${agent_id}/memory`, { body: opts.body });
  }

  createAiTeamAgentNexoraApiV1AiTeamAgentsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-agents`, { body: opts.body });
  }

  createAiTeamNexoraApiV1AiTeamsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-teams`, { body: opts.body });
  }

  createAiTeamWorkflowNexoraApiV1AiTeamWorkflowsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-workflows`, { body: opts.body });
  }

  createAiToolNexoraApiV1AiToolsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-tools`, { body: opts.body });
  }

  createArticleNexoraApiV1DocsArticlesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/docs/articles`, { body: opts.body });
  }

  createAssetNexoraApiV1DemoAssetsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/demo-assets`, { body: opts.body });
  }

  createBackupNexoraApiV1GaBackupsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ga/backups`, { body: opts.body });
  }

  createChangeRequestNexoraApiV1ChangeRequestsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/change-requests`, { body: opts.body });
  }

  createCommunicationNexoraApiV1IncidentsCommunicationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/communications`, { body: opts.body });
  }

  createCommunicationTemplateNexoraApiV1IncidentsCommunicationsTemplatesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/communications/templates`, { body: opts.body });
  }

  createConnectionNexoraApiV1AuthSsoConnectionsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/sso/connections`, { body: opts.body });
  }

  createCredentialNexoraApiV1CredentialsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/credentials`, { body: opts.body });
  }

  createCustomerApprovalNexoraApiV1PilotApprovalsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/approvals`, { body: opts.body });
  }

  createDashboardNexoraApiV1ProductDashboardsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/dashboards`, { body: opts.body });
  }

  createDemoOrganizationNexoraApiV1DemoOrganizationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/demo-organizations`, { body: opts.body });
  }

  createDependencyNexoraApiV1ServiceDependenciesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/service-dependencies`, { body: opts.body });
  }

  createEnvironmentNexoraApiV1PlatformEngineeringEnvironmentsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/environments`, { body: opts.body });
  }

  createForecastNexoraApiV1CapacityForecastsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/capacity/forecasts`, { body: opts.body });
  }

  createFreezeWindowNexoraApiV1DeliveryFreezeWindowsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/freeze-windows`, { body: opts.body });
  }

  createGoalNexoraApiV1OperatorGoalsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/operator/goals`, { body: opts.body });
  }

  createGoldenTemplateNexoraApiV1PlatformEngineeringGoldenTemplatesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/golden-templates`, { body: opts.body });
  }

  createGroupNexoraApiV1ScimV2GroupsPost() {
    return this.request("POST", `/nexora-api/v1/scim/v2/Groups`);
  }

  createIncidentTaskNexoraApiV1IncidentsInvestigationIdTasksPost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/tasks`, { body: opts.body });
  }

  createIntegrationNexoraApiV1ObservabilityIntegrationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/observability/integrations`, { body: opts.body });
  }

  createInvestigationNexoraApiV1SecurityInvestigationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/investigations`, { body: opts.body });
  }

  createInvitationNexoraApiV1InvitationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/invitations`, { body: opts.body });
  }

  createMaintenanceNexoraApiV1OpsWorkspaceMaintenancePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ops-workspace/maintenance`, { body: opts.body });
  }

  createOrgKeyNexoraApiV1ApiKeysOrganizationPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/api-keys/organization`, { body: opts.body });
  }

  createOrganizationNexoraApiV1OrganizationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/organizations`, { body: opts.body });
  }

  createPersonalKeyNexoraApiV1ApiKeysPersonalPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/api-keys/personal`, { body: opts.body });
  }

  createPlanNexoraApiV1BillingAdminPlansPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/admin/plans`, { body: opts.body });
  }

  createPlaybookNexoraApiV1TestPlaybooksPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/test-playbooks`, { body: opts.body });
  }

  createPolicyNexoraApiV1OncallEscalationPoliciesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/oncall/escalation-policies`, { body: opts.body });
  }

  createPolicyNexoraApiV1OperatorPoliciesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/operator/policies`, { body: opts.body });
  }

  createProjectNexoraApiV1ProjectsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/projects`, { body: opts.body });
  }

  createPromotionPolicyNexoraApiV1DeliveryPromotionPoliciesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/promotion-policies`, { body: opts.body });
  }

  createPromptNexoraApiV1AiPromptsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/prompts`, { body: opts.body });
  }

  createProviderNexoraApiV1SecurityProvidersPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/providers`, { body: opts.body });
  }

  createReleaseNexoraApiV1DeliveryReleasesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/releases`, { body: opts.body });
  }

  createReleaseNexoraApiV1ReleasesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/releases`, { body: opts.body });
  }

  createReleaseReliabilityNexoraApiV1DeliveryReleaseReliabilityPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability`, { body: opts.body });
  }

  createRemediationWorkflowNexoraApiV1SreRemediationWorkflowsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/remediation/workflows`, { body: opts.body });
  }

  createReportScheduleNexoraApiV1ProductReportsSchedulesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/reports/schedules`, { body: opts.body });
  }

  createRepositoryNexoraApiV1PlatformEngineeringRepositoriesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/repositories`, { body: opts.body });
  }

  createRuleNexoraApiV1WorkflowsWorkflowIdRulesPost(workflow_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflows/${workflow_id}/rules`, { body: opts.body });
  }

  createSavedSearchNexoraApiV1ObservabilityLogsSavedSearchesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/observability/logs/saved-searches`, { body: opts.body });
  }

  createSavedViewNexoraApiV1ProductViewsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/views`, { body: opts.body });
  }

  createScheduleNexoraApiV1OncallSchedulesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/oncall/schedules`, { body: opts.body });
  }

  createScheduleOverrideNexoraApiV1IncidentsOncallOverridesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/oncall/overrides`, { body: opts.body });
  }

  createScimTokenNexoraApiV1ScimV2AdminTokensPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/scim/v2/admin/tokens`, { body: opts.body });
  }

  createSecretRefNexoraApiV1PlatformEngineeringSecretsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/secrets`, { body: opts.body });
  }

  createServiceAccountNexoraApiV1ServiceAccountsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/service-accounts`, { body: opts.body });
  }

  createServiceNexoraApiV1ServicesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/services`, { body: opts.body });
  }

  createServiceOwnerNexoraApiV1OncallServiceOwnersPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/oncall/service-owners`, { body: opts.body });
  }

  createSessionNexoraApiV1OnboardingIntegrationsSessionsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/onboarding/integrations/sessions`, { body: opts.body });
  }

  createSloNexoraApiV1ServicesServiceIdSlosPost(service_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/services/${service_id}/slos`, { body: opts.body });
  }

  createStackNexoraApiV1PlatformEngineeringStacksPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/stacks`, { body: opts.body });
  }

  createStageNexoraApiV1WorkflowsWorkflowIdStagesPost(workflow_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflows/${workflow_id}/stages`, { body: opts.body });
  }

  createStatusPageNexoraApiV1IncidentsStatusPagesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/status-pages`, { body: opts.body });
  }

  createTeamNexoraApiV1TeamsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/teams`, { body: opts.body });
  }

  createTeamResponsibilityNexoraApiV1TeamsTeamIdResponsibilitiesPost(team_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/teams/${team_id}/responsibilities`, { body: opts.body });
  }

  createUserNexoraApiV1ScimV2UsersPost() {
    return this.request("POST", `/nexora-api/v1/scim/v2/Users`);
  }

  createVariableNexoraApiV1OrgConfigVariablesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/org-config/variables`, { body: opts.body });
  }

  createWarRoomNexoraApiV1WarRoomsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/war-rooms`, { body: opts.body });
  }

  createWebhookNexoraApiV1BillingWebhooksPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/webhooks`, { body: opts.body });
  }

  createWorkflowNexoraApiV1WorkflowsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflows`, { body: opts.body });
  }

  createWorkflowScheduleNexoraApiV1AiTeamWorkflowSchedulesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-workflow-schedules`, { body: opts.body });
  }

  createWorkspaceNexoraApiV1WorkspacesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workspaces`, { body: opts.body });
  }

  credentialStatusNexoraApiV1CredentialsCredentialIdStatusGet(credential_id: string) {
    return this.request("GET", `/nexora-api/v1/credentials/${credential_id}/status`);
  }

  currentOncallNexoraApiV1OncallCurrentGet() {
    return this.request("GET", `/nexora-api/v1/oncall/current`);
  }

  customerSuccessNexoraApiV1GaSuccessGet() {
    return this.request("GET", `/nexora-api/v1/ga/success`);
  }

  dashboardNexoraApiV1ArchitectureDashboardGet() {
    return this.request("GET", `/nexora-api/v1/architecture/dashboard`);
  }

  dashboardNexoraApiV1DeliveryDashboardGet() {
    return this.request("GET", `/nexora-api/v1/delivery/dashboard`);
  }

  dashboardNexoraApiV1ObservabilityDashboardGet() {
    return this.request("GET", `/nexora-api/v1/observability/dashboard`);
  }

  dashboardNexoraApiV1OperatorDashboardGet() {
    return this.request("GET", `/nexora-api/v1/operator/dashboard`);
  }

  dashboardNexoraApiV1PlatformEngineeringDashboardGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/dashboard`);
  }

  dashboardNexoraApiV1ReliabilityDashboardGet() {
    return this.request("GET", `/nexora-api/v1/reliability/dashboard`);
  }

  decideApprovalNexoraApiV1CustomerPilotOperationOperationIdApprovalDecidePost(operation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-pilot/operation/${operation_id}/approval/decide`, { body: opts.body });
  }

  decideCatalogRequestNexoraApiV1PlatformEngineeringCatalogRequestsRequestIdDecidePost(request_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/catalog/requests/${request_id}/decide`, { params: opts.params });
  }

  decideChangeRequestNexoraApiV1ChangeRequestsRunIdDecidePost(run_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/change-requests/${run_id}/decide`, { body: opts.body });
  }

  decideCustomerApprovalNexoraApiV1PilotApprovalsApprovalIdDecidePost(approval_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/approvals/${approval_id}/decide`, { body: opts.body });
  }

  decideEnvironmentNexoraApiV1PlatformEngineeringEnvironmentsEnvironmentIdDecidePost(environment_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/environments/${environment_id}/decide`, { params: opts.params });
  }

  decideK8SOperationNexoraApiV1ControlPlaneClustersClusterIdK8SOperationsOperationIdDecidePost(cluster_id: string, operation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/operations/${operation_id}/decide`, { body: opts.body });
  }

  decideMaintenanceNexoraApiV1OpsWorkspaceMaintenanceWindowIdDecidePost(window_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/ops-workspace/maintenance/${window_id}/decide`, { params: opts.params });
  }

  decideOperationNexoraApiV1ControlPlaneOperationsOperationIdDecidePost(operation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/operations/${operation_id}/decide`, { body: opts.body });
  }

  decideOperationNexoraApiV1DeliveryOperationsOperationIdDecidePost(operation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/operations/${operation_id}/decide`, { body: opts.body });
  }

  decideProposalNexoraApiV1OperatorProposalsProposalIdDecidePost(proposal_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/operator/proposals/${proposal_id}/decide`, { params: opts.params });
  }

  decideProvisionNexoraApiV1PlatformEngineeringProvisionsProvisionIdDecidePost(provision_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/provisions/${provision_id}/decide`, { params: opts.params });
  }

  decideRemediationNexoraApiV1SecurityRemediationProposalIdDecidePost(proposal_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/security/remediation/${proposal_id}/decide`, { params: opts.params });
  }

  decideRunNexoraApiV1PlatformEngineeringRunsRunIdDecidePost(run_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/runs/${run_id}/decide`, { params: opts.params });
  }

  deleteAgentInputNexoraApiV1AiAgentInputsInputIdDelete(input_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-agent-inputs/${input_id}`);
  }

  deleteAgentOutputNexoraApiV1AiAgentOutputsOutputIdDelete(output_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-agent-outputs/${output_id}`);
  }

  deleteAgentResponsibilityNexoraApiV1AiAgentResponsibilitiesResponsibilityIdDelete(responsibility_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-agent-responsibilities/${responsibility_id}`);
  }

  deleteAiAgentNexoraApiV1AiAgentsAgentIdDelete(agent_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-agents/${agent_id}`);
  }

  deleteAiTeamAgentMemoryNexoraApiV1AiTeamAgentsMemoryMemoryIdDelete(memory_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-team-agents/memory/${memory_id}`);
  }

  deleteAiTeamAgentNexoraApiV1AiTeamAgentsAgentIdDelete(agent_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-team-agents/${agent_id}`);
  }

  deleteAiTeamDocumentNexoraApiV1AiTeamsDocumentsDocumentIdDelete(document_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-teams/documents/${document_id}`);
  }

  deleteAiTeamNexoraApiV1AiTeamsTeamIdDelete(team_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-teams/${team_id}`);
  }

  deleteAiTeamWorkflowNexoraApiV1AiTeamWorkflowsWorkflowIdDelete(workflow_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-team-workflows/${workflow_id}`);
  }

  deleteAiToolNexoraApiV1AiToolsToolIdDelete(tool_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-tools/${tool_id}`);
  }

  deleteArticleNexoraApiV1DocsArticlesArticleIdDelete(article_id: string) {
    return this.request("DELETE", `/nexora-api/v1/docs/articles/${article_id}`);
  }

  deleteAssetNexoraApiV1DemoAssetsAssetIdDelete(asset_id: string) {
    return this.request("DELETE", `/nexora-api/v1/demo-assets/${asset_id}`);
  }

  deleteConnectionNexoraApiV1AuthSsoConnectionsConnectionIdDelete(connection_id: string) {
    return this.request("DELETE", `/nexora-api/v1/auth/sso/connections/${connection_id}`);
  }

  deleteCredentialNexoraApiV1CredentialsCredentialIdDelete(credential_id: string) {
    return this.request("DELETE", `/nexora-api/v1/credentials/${credential_id}`);
  }

  deleteDashboardNexoraApiV1ProductDashboardsDashIdDelete(dash_id: string) {
    return this.request("DELETE", `/nexora-api/v1/product/dashboards/${dash_id}`);
  }

  deleteDemoOrganizationNexoraApiV1DemoOrganizationsOrganizationIdDelete(organization_id: string) {
    return this.request("DELETE", `/nexora-api/v1/demo-organizations/${organization_id}`);
  }

  deleteDependencyNexoraApiV1ServiceDependenciesDependencyIdDelete(dependency_id: string) {
    return this.request("DELETE", `/nexora-api/v1/service-dependencies/${dependency_id}`);
  }

  deleteDeploymentNexoraApiV1DeploymentsDeploymentIdDelete(deployment_id: string) {
    return this.request("DELETE", `/nexora-api/v1/deployments/${deployment_id}`);
  }

  deleteGroupNexoraApiV1ScimV2GroupsScimIdDelete(scim_id: string) {
    return this.request("DELETE", `/nexora-api/v1/scim/v2/Groups/${scim_id}`);
  }

  deleteOrganizationNexoraApiV1OrganizationsOrganizationIdDelete(organization_id: string) {
    return this.request("DELETE", `/nexora-api/v1/organizations/${organization_id}`);
  }

  deletePlaybookNexoraApiV1TestPlaybooksPlaybookIdDelete(playbook_id: string) {
    return this.request("DELETE", `/nexora-api/v1/test-playbooks/${playbook_id}`);
  }

  deletePolicyNexoraApiV1OncallEscalationPoliciesPolicyIdDelete(policy_id: string) {
    return this.request("DELETE", `/nexora-api/v1/oncall/escalation-policies/${policy_id}`);
  }

  deleteProjectNexoraApiV1ProjectsProjectIdDelete(project_id: string) {
    return this.request("DELETE", `/nexora-api/v1/projects/${project_id}`);
  }

  deleteResponsibilityNexoraApiV1ResponsibilitiesResponsibilityIdDelete(responsibility_id: string) {
    return this.request("DELETE", `/nexora-api/v1/responsibilities/${responsibility_id}`);
  }

  deleteSavedViewNexoraApiV1ProductViewsViewIdDelete(view_id: string) {
    return this.request("DELETE", `/nexora-api/v1/product/views/${view_id}`);
  }

  deleteScheduleNexoraApiV1OncallSchedulesScheduleIdDelete(schedule_id: string) {
    return this.request("DELETE", `/nexora-api/v1/oncall/schedules/${schedule_id}`);
  }

  deleteSecretRefNexoraApiV1PlatformEngineeringSecretsRefIdDelete(ref_id: string) {
    return this.request("DELETE", `/nexora-api/v1/platform-engineering/secrets/${ref_id}`);
  }

  deleteServiceNexoraApiV1ServicesServiceIdDelete(service_id: string) {
    return this.request("DELETE", `/nexora-api/v1/services/${service_id}`);
  }

  deleteServiceOwnerNexoraApiV1OncallServiceOwnersOwnerIdDelete(owner_id: string) {
    return this.request("DELETE", `/nexora-api/v1/oncall/service-owners/${owner_id}`);
  }

  deleteSloNexoraApiV1ServicesSlosSloIdDelete(slo_id: string) {
    return this.request("DELETE", `/nexora-api/v1/services/slos/${slo_id}`);
  }

  deleteStageNexoraApiV1StagesStageIdDelete(stage_id: string) {
    return this.request("DELETE", `/nexora-api/v1/stages/${stage_id}`);
  }

  deleteTeamNexoraApiV1TeamsTeamIdDelete(team_id: string) {
    return this.request("DELETE", `/nexora-api/v1/teams/${team_id}`);
  }

  deleteUserNexoraApiV1ScimV2UsersScimIdDelete(scim_id: string) {
    return this.request("DELETE", `/nexora-api/v1/scim/v2/Users/${scim_id}`);
  }

  deleteVariableNexoraApiV1OrgConfigVariablesVariableIdDelete(variable_id: string) {
    return this.request("DELETE", `/nexora-api/v1/org-config/variables/${variable_id}`);
  }

  deleteWorkflowNexoraApiV1WorkflowsWorkflowIdDelete(workflow_id: string) {
    return this.request("DELETE", `/nexora-api/v1/workflows/${workflow_id}`);
  }

  deleteWorkflowScheduleNexoraApiV1AiTeamWorkflowSchedulesScheduleIdDelete(schedule_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-team-workflow-schedules/${schedule_id}`);
  }

  deleteWorkspaceNexoraApiV1WorkspacesWorkspaceIdDelete(workspace_id: string) {
    return this.request("DELETE", `/nexora-api/v1/workspaces/${workspace_id}`);
  }

  demoDashboardNexoraApiV1CustomerSuccessDemosGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/demos`);
  }

  demoLaunchNexoraApiV1CustomerSuccessDemosScenariosKeyLaunchPost(key: string) {
    return this.request("POST", `/nexora-api/v1/customer-success/demos/scenarios/${key}/launch`);
  }

  demoRecordingsNexoraApiV1SalesDemoRecordingsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/sales/demo-recordings`, { params: opts.params });
  }

  demoSalesModeNexoraApiV1CustomerSuccessDemosScenariosKeySalesModeGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/demos/scenarios/${key}/sales-mode`);
  }

  demoScenarioNexoraApiV1CustomerSuccessDemosScenariosKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/demos/scenarios/${key}`);
  }

  demoStateNexoraApiV1CustomerSuccessDemosScenariosKeyStatePost(key: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/demos/scenarios/${key}/state`, { body: opts.body });
  }

  dependencyGraphNexoraApiV1ServiceDependenciesGraphGet() {
    return this.request("GET", `/nexora-api/v1/service-dependencies/graph`);
  }

  deploymentSafetyDashboardNexoraApiV1DeploymentSafetyDashboardGet() {
    return this.request("GET", `/nexora-api/v1/deployment-safety/dashboard`);
  }

  deregisterMcpServerNexoraApiV1AiMcpServersServerIdDelete(server_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai/mcp/servers/${server_id}`);
  }

  detachAiToolCredentialNexoraApiV1AiToolsToolIdCredentialsCredentialIdDelete(tool_id: string, credential_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-tools/${tool_id}/credentials/${credential_id}`);
  }

  diagnosticsJsonNexoraApiV1GaDiagnosticsGet() {
    return this.request("GET", `/nexora-api/v1/ga/diagnostics`);
  }

  diagnosticsZipNexoraApiV1GaDiagnosticsZipGet() {
    return this.request("GET", `/nexora-api/v1/ga/diagnostics/zip`);
  }

  disableMfaNexoraApiV1AuthMfaDisablePost() {
    return this.request("POST", `/nexora-api/v1/auth/mfa/disable`);
  }

  disableServiceAccountNexoraApiV1ServiceAccountsSaIdDisablePost(sa_id: string) {
    return this.request("POST", `/nexora-api/v1/service-accounts/${sa_id}/disable`);
  }

  disconnectIntegrationNexoraApiV1IntegrationsConnectionsConnectionIdDelete(connection_id: string) {
    return this.request("DELETE", `/nexora-api/v1/integrations/connections/${connection_id}`);
  }

  discoverClusterNexoraApiV1ControlPlaneClustersClusterIdDiscoverPost(cluster_id: string) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/discover`);
  }

  discoverMetricsNexoraApiV1ObservabilityMetricsDiscoverGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/observability/metrics/discover`, { params: opts.params });
  }

  discoverNexoraApiV1ArchitectureDiscoverPost() {
    return this.request("POST", `/nexora-api/v1/architecture/discover`);
  }

  discoveryAssetsNexoraApiV1DiscoveryAssetsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/discovery/assets`, { params: opts.params });
  }

  discoveryContextNexoraApiV1DiscoveryContextGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/discovery/context`, { params: opts.params });
  }

  discoveryEventsNexoraApiV1DiscoveryEventsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/discovery/events`, { params: opts.params });
  }

  discoveryGraphNexoraApiV1DiscoveryGraphGet() {
    return this.request("GET", `/nexora-api/v1/discovery/graph`);
  }

  discoveryProgressNexoraApiV1DiscoveryProgressGet() {
    return this.request("GET", `/nexora-api/v1/discovery/progress`);
  }

  discoverySummaryNexoraApiV1DiscoverySummaryGet() {
    return this.request("GET", `/nexora-api/v1/discovery/summary`);
  }

  dismissAutomationNexoraApiV1OpsWorkspaceAutomationSuggestionsSuggestionIdDismissPost(suggestion_id: string) {
    return this.request("POST", `/nexora-api/v1/ops-workspace/automation-suggestions/${suggestion_id}/dismiss`);
  }

  documentationAuditGuideNexoraApiV1CustomerSuccessDocumentationAuditGuidesKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/documentation-audit/guides/${key}`);
  }

  documentationAuditNexoraApiV1CustomerSuccessDocumentationAuditGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/documentation-audit`);
  }

  documentationCertificationDashboardNexoraApiV1CustomerSuccessCertificationDashboardGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/certification/dashboard`);
  }

  documentationCertificationNexoraApiV1CustomerSuccessCertificationGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/certification`);
  }

  documentationDiagramsNexoraApiV1ProductDocsDiagramsGet() {
    return this.request("GET", `/nexora-api/v1/product/docs/diagrams`);
  }

  doraMetricsNexoraApiV1DeliveryDoraGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/delivery/dora`, { params: opts.params });
  }

  draftCommunicationNexoraApiV1PilotCommunicationsDraftPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/communications/draft`, { body: opts.body });
  }

  drainEventsNexoraApiV1PlatformEventsDrainPost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/events/drain`, { params: opts.params });
  }

  driftNexoraApiV1CustomerSuccessDriftGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/drift`);
  }

  duplicateAiAgentNexoraApiV1AiAgentsAgentIdDuplicatePost(agent_id: string) {
    return this.request("POST", `/nexora-api/v1/ai-agents/${agent_id}/duplicate`);
  }

  duplicateTeamNexoraApiV1TeamsTeamIdDuplicatePost(team_id: string) {
    return this.request("POST", `/nexora-api/v1/teams/${team_id}/duplicate`);
  }

  duplicateWorkflowNexoraApiV1WorkflowsWorkflowIdDuplicatePost(workflow_id: string) {
    return this.request("POST", `/nexora-api/v1/workflows/${workflow_id}/duplicate`);
  }

  enableLiveOperationsNexoraApiV1PilotLiveOperationsEnablePost() {
    return this.request("POST", `/nexora-api/v1/pilot/live-operations/enable`);
  }

  endMajorIncidentNexoraApiV1IncidentsMajorMajorIdEndPost(major_id: string) {
    return this.request("POST", `/nexora-api/v1/incidents/major/${major_id}/end`);
  }

  enrollMfaNexoraApiV1AuthMfaEnrollPost() {
    return this.request("POST", `/nexora-api/v1/auth/mfa/enroll`);
  }

  errorBudgetsNexoraApiV1ObservabilityErrorBudgetGet() {
    return this.request("GET", `/nexora-api/v1/observability/error-budget`);
  }

  escalateIncidentNexoraApiV1IncidentsInvestigationIdEscalatePost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/escalate`, { body: opts.body });
  }

  escalationDashboardNexoraApiV1IncidentsEscalationGet() {
    return this.request("GET", `/nexora-api/v1/incidents/escalation`);
  }

  evaluateSlaNexoraApiV1SecuritySlaEvaluatePost() {
    return this.request("POST", `/nexora-api/v1/security/sla/evaluate`);
  }

  evaluateSlosNexoraApiV1ObservabilitySloEvaluatePost() {
    return this.request("POST", `/nexora-api/v1/observability/slo/evaluate`);
  }

  evaluationSummaryNexoraApiV1AiEvaluationsSummaryGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai/evaluations/summary`, { params: opts.params });
  }

  eventsPendingNexoraApiV1PlatformEventsPendingGet() {
    return this.request("GET", `/nexora-api/v1/platform/events/pending`);
  }

  executeAiTeamAgentNexoraApiV1AiTeamAgentsAgentIdExecutePost(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-agents/${agent_id}/execute`, { body: opts.body });
  }

  executeAiTeamNexoraApiV1AiTeamsTeamIdExecutePost(team_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-teams/${team_id}/execute`, { body: opts.body });
  }

  executeAiTeamWorkflowNexoraApiV1AiTeamWorkflowsWorkflowIdExecutePost(workflow_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-team-workflows/${workflow_id}/execute`, { body: opts.body });
  }

  executeAiToolNexoraApiV1AiToolsToolIdExecutePost(tool_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-tools/${tool_id}/execute`, { body: opts.body });
  }

  executeK8SOperationNexoraApiV1ControlPlaneClustersClusterIdK8SOperationsOperationIdExecutePost(cluster_id: string, operation_id: string) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/operations/${operation_id}/execute`);
  }

  executeOperationNexoraApiV1ControlPlaneOperationsOperationIdExecutePost(operation_id: string) {
    return this.request("POST", `/nexora-api/v1/control-plane/operations/${operation_id}/execute`);
  }

  executeOperationNexoraApiV1DeliveryOperationsOperationIdExecutePost(operation_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/operations/${operation_id}/execute`);
  }

  executePlaybookNexoraApiV1TestPlaybooksPlaybookIdExecutePost(playbook_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/test-playbooks/${playbook_id}/execute`, { body: opts.body });
  }

  executeRegenerationNexoraApiV1RegenerationPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/regeneration`, { body: opts.body });
  }

  executeRemediationNexoraApiV1SecurityRemediationProposalIdExecutePost(proposal_id: string) {
    return this.request("POST", `/nexora-api/v1/security/remediation/${proposal_id}/execute`);
  }

  executeRunbookNexoraApiV1SreRunbooksRunbookIdExecutePost(runbook_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/runbooks/${runbook_id}/execute`, { body: opts.body });
  }

  executeScanNexoraApiV1SecurityScansScanIdExecutePost(scan_id: string) {
    return this.request("POST", `/nexora-api/v1/security/scans/${scan_id}/execute`);
  }

  executeToolNexoraApiV1AiToolsNameExecutePost(name: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/tools/${name}/execute`, { body: opts.body });
  }

  executeWarRoomNexoraApiV1WarRoomsWarRoomIdExecutePost(war_room_id: string) {
    return this.request("POST", `/nexora-api/v1/war-rooms/${war_room_id}/execute`);
  }

  executeWorkflowNexoraApiV1WorkflowsWorkflowIdExecutePost(workflow_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflows/${workflow_id}/execute`, { body: opts.body });
  }

  executionAnalyticsNexoraApiV1PlatformExecutionsAnalyticsGet() {
    return this.request("GET", `/nexora-api/v1/platform/executions/analytics`);
  }

  executiveAiReportNexoraApiV1SreReportsExecutivePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/reports/executive`, { body: opts.body });
  }

  executivePdfNexoraApiV1OpsWorkspaceExecutiveExportPdfGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/executive/export/pdf`);
  }

  executiveViewNexoraApiV1OpsWorkspaceExecutiveGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/executive`);
  }

  exportArticleNexoraApiV1DocsArticlesArticleIdExportGet(article_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/docs/articles/${article_id}/export`, { params: opts.params });
  }

  exportComparisonNexoraApiV1SalesCompetitiveComparisonExportGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/sales/competitive-comparison/export`, { params: opts.params });
  }

  exportConfigNexoraApiV1OpsConfigExportGet() {
    return this.request("GET", `/nexora-api/v1/ops/config/export`);
  }

  exportDashboardNexoraApiV1ReliabilityDashboardExportGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/reliability-dashboard/export`, { params: opts.params });
  }

  exportEvidenceNexoraApiV1CustomerPilotOperationOperationIdEvidenceExportGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation/${operation_id}/evidence/export`);
  }

  exportEvidencePackNexoraApiV1PilotEvidencePackExportGet() {
    return this.request("GET", `/nexora-api/v1/pilot/evidence-pack/export`);
  }

  exportHumanGuideNexoraApiV1CustomerSuccessHumanGuidesKeyExportGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/human-guides/${key}/export`, { params: opts.params });
  }

  exportLogsNexoraApiV1AuditLogsExportGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/audit/logs/export`, { params: opts.params });
  }

  exportManualNexoraApiV1DocsManualGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/docs/manual`, { params: opts.params });
  }

  exportPilotReportNexoraApiV1PilotReportExportGet() {
    return this.request("GET", `/nexora-api/v1/pilot/report/export`);
  }

  exportPostmortemNexoraApiV1PostmortemsPostmortemIdExportGet(postmortem_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/postmortems/${postmortem_id}/export`, { params: opts.params });
  }

  exportProposalNexoraApiV1SalesProposalExportPost(opts: { params?: Record<string, unknown>; body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sales/proposal/export`, { params: opts.params, body: opts.body });
  }

  exportReportNexoraApiV1ExecutiveReportsReportIdExportGet(report_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/executive-reports/${report_id}/export`, { params: opts.params });
  }

  exportRunNexoraApiV1TestPlaybooksRunsRunIdExportGet(run_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/test-playbooks/runs/${run_id}/export`, { params: opts.params });
  }

  exportSuccessPlaybookNexoraApiV1CustomerSuccessSuccessPlaybooksKeyExportGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/success-playbooks/${key}/export`, { params: opts.params });
  }

  exportSupportDiagnosticsNexoraApiV1PilotSupportDiagnosticsExportGet() {
    return this.request("GET", `/nexora-api/v1/pilot/support/diagnostics/export`);
  }

  exportTimelineNexoraApiV1CustomerPilotTimelineExportGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/timeline/export`, { params: opts.params });
  }

  exportValuePropositionNexoraApiV1SalesValuePropositionExportPost(opts: { params?: Record<string, unknown>; body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sales/value-proposition/export`, { params: opts.params, body: opts.body });
  }

  exportVideoNexoraApiV1CustomerSuccessVideosVideoIdExportGet(video_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/videos/${video_id}/export`, { params: opts.params });
  }

  exportVisualDocsNexoraApiV1CustomerSuccessExportGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/export`, { params: opts.params });
  }

  featureFlagsNexoraApiV1BillingFeatureFlagsGet() {
    return this.request("GET", `/nexora-api/v1/billing/feature-flags`);
  }

  featuredVideosNexoraApiV1CustomerSuccessVideosFeaturedGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/videos/featured`);
  }

  galleryNexoraApiV1CustomerSuccessGalleryGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/gallery`, { params: opts.params });
  }

  generateComplianceReportNexoraApiV1GaComplianceReportsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ga/compliance/reports`, { body: opts.body });
  }

  generateDailyBriefingNexoraApiV1OpsWorkspaceBriefingDailyPost() {
    return this.request("POST", `/nexora-api/v1/ops-workspace/briefing/daily`);
  }

  generateDocumentationNexoraApiV1DocsGeneratePost() {
    return this.request("POST", `/nexora-api/v1/docs/generate`);
  }

  generateExecutiveBriefingNexoraApiV1OperatorExecutiveBriefingPost() {
    return this.request("POST", `/nexora-api/v1/operator/executive/briefing`);
  }

  generateHandoverNexoraApiV1OpsWorkspaceHandoverPost() {
    return this.request("POST", `/nexora-api/v1/ops-workspace/handover`);
  }

  generatePostmortemNexoraApiV1IncidentsInvestigationIdGeneratePostmortemPost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/generate-postmortem`, { body: opts.body });
  }

  generatePostmortemNexoraApiV1IncidentsPostmortemsIncidentIdGeneratePost(incident_id: string) {
    return this.request("POST", `/nexora-api/v1/incidents/postmortems/${incident_id}/generate`);
  }

  generateReportNexoraApiV1ExecutiveReportsGeneratePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/executive-reports/generate`, { body: opts.body });
  }

  generateRunbookNexoraApiV1RunbooksGeneratePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/runbooks/generate`, { body: opts.body });
  }

  generateSampleIncidentNexoraApiV1OnboardingSessionIdSampleIncidentPost(session_id: string) {
    return this.request("POST", `/nexora-api/v1/onboarding/${session_id}/sample-incident`);
  }

  generateScreenshotAssetsNexoraApiV1CustomerSuccessScreenshotAssetsGeneratePost() {
    return this.request("POST", `/nexora-api/v1/customer-success/screenshot-assets/generate`);
  }

  getAgentRunNexoraApiV1AgentsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/runs/${run_id}`);
  }

  getAgentRunNexoraApiV1AiAgentsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/ai/agents/${run_id}`);
  }

  getAiAgentNexoraApiV1AiAgentsAgentIdGet(agent_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-agents/${agent_id}`);
  }

  getAiAgentTemplateNexoraApiV1AiAgentTemplatesSlugGet(slug: string) {
    return this.request("GET", `/nexora-api/v1/ai-agent-templates/${slug}`);
  }

  getAiTeamAgentNexoraApiV1AiTeamAgentsAgentIdGet(agent_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-team-agents/${agent_id}`);
  }

  getAiTeamNexoraApiV1AiTeamsTeamIdGet(team_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-teams/${team_id}`);
  }

  getAiTeamRunNexoraApiV1AiTeamsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-teams/runs/${run_id}`);
  }

  getAiTeamWorkflowNexoraApiV1AiTeamWorkflowsWorkflowIdGet(workflow_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-team-workflows/${workflow_id}`);
  }

  getAiToolNexoraApiV1AiToolsToolIdGet(tool_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-tools/${tool_id}`);
  }

  getAlertNexoraApiV1MonitoringAlertsAlertIdGet(alert_id: string) {
    return this.request("GET", `/nexora-api/v1/monitoring/alerts/${alert_id}`);
  }

  getAnalysisNexoraApiV1CostOptimizationAnalysesAnalysisIdGet(analysis_id: string) {
    return this.request("GET", `/nexora-api/v1/cost-optimization/analyses/${analysis_id}`);
  }

  getApprovalArtifactNexoraApiV1AgentsApprovalArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/approval/artifacts/${artifact_id}`);
  }

  getApprovalPackageNexoraApiV1CustomerPilotOperationOperationIdApprovalPackageGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation/${operation_id}/approval-package`);
  }

  getApprovalRunNexoraApiV1AgentsApprovalRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/approval/runs/${run_id}`);
  }

  getArchitectureNexoraApiV1CustomerSuccessArchitectureKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/architecture/${key}`);
  }

  getArticleNexoraApiV1DocsArticlesArticleIdGet(article_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/docs/articles/${article_id}`, { params: opts.params });
  }

  getAssessmentNexoraApiV1PilotAssessmentGet() {
    return this.request("GET", `/nexora-api/v1/pilot/assessment`);
  }

  getAssessmentNexoraApiV1ReliabilityAssessmentIdGet(assessment_id: string) {
    return this.request("GET", `/nexora-api/v1/reliability/${assessment_id}`);
  }

  getAssetNexoraApiV1DemoAssetsAssetIdGet(asset_id: string) {
    return this.request("GET", `/nexora-api/v1/demo-assets/${asset_id}`);
  }

  getAssignmentNexoraApiV1OncallIncidentsIncidentIdAssignmentGet(incident_id: string) {
    return this.request("GET", `/nexora-api/v1/oncall/incidents/${incident_id}/assignment`);
  }

  getBackendArchitectArtifactNexoraApiV1AgentsBackendArchitectArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-architect/artifacts/${artifact_id}`);
  }

  getBackendArchitectRunNexoraApiV1AgentsBackendArchitectRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-architect/runs/${run_id}`);
  }

  getBackendCodeReviewArtifactNexoraApiV1AgentsBackendCodeReviewArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-code-review/artifacts/${artifact_id}`);
  }

  getBackendCodeReviewRunNexoraApiV1AgentsBackendCodeReviewRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-code-review/runs/${run_id}`);
  }

  getBackendExecutionArtifactNexoraApiV1AgentsBackendExecutionArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-execution/artifacts/${artifact_id}`);
  }

  getBackendExecutionRunNexoraApiV1AgentsBackendExecutionRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-execution/runs/${run_id}`);
  }

  getBackendV1ArtifactNexoraApiV1AgentsBackendV1ArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v1/artifacts/${artifact_id}`);
  }

  getBackendV1RunNexoraApiV1AgentsBackendV1RunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v1/runs/${run_id}`);
  }

  getBackendV2ArtifactNexoraApiV1AgentsBackendV2ArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v2/artifacts/${artifact_id}`);
  }

  getBackendV2RunNexoraApiV1AgentsBackendV2RunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v2/runs/${run_id}`);
  }

  getBackendV3ArtifactNexoraApiV1AgentsBackendV3ArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v3/artifacts/${artifact_id}`);
  }

  getBackendV3RunNexoraApiV1AgentsBackendV3RunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v3/runs/${run_id}`);
  }

  getBusinessAnalystArtifactNexoraApiV1AgentsBusinessAnalystArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/business-analyst/artifacts/${artifact_id}`);
  }

  getBusinessAnalystRunNexoraApiV1AgentsBusinessAnalystRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/business-analyst/runs/${run_id}`);
  }

  getChangeFailureNexoraApiV1ChangeFailurePredictionPredictionIdGet(prediction_id: string) {
    return this.request("GET", `/nexora-api/v1/change-failure-prediction/${prediction_id}`);
  }

  getChangeRequestNexoraApiV1ChangeRequestsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/change-requests/${run_id}`);
  }

  getCicdArtifactNexoraApiV1AgentsCicdArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/cicd/artifacts/${artifact_id}`);
  }

  getCicdRunNexoraApiV1AgentsCicdRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/cicd/runs/${run_id}`);
  }

  getCloseoutNexoraApiV1CustomerPilotCloseoutGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/closeout`);
  }

  getClusterNexoraApiV1ControlPlaneClustersClusterIdGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}`);
  }

  getCommanderNexoraApiV1SreCommanderCommanderIdGet(commander_id: string) {
    return this.request("GET", `/nexora-api/v1/sre/commander/${commander_id}`);
  }

  getCommunicationNexoraApiV1CustomerPilotCommunicationsCommunicationIdGet(communication_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/communications/${communication_id}`);
  }

  getConfigNexoraApiV1PlatformConfigKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/platform/config/${key}`);
  }

  getConnectionCapabilitiesNexoraApiV1IntegrationsConnectionsConnectionIdCapabilitiesGet(connection_id: string) {
    return this.request("GET", `/nexora-api/v1/integrations/connections/${connection_id}/capabilities`);
  }

  getConnectionExpiryNexoraApiV1IntegrationsConnectionsConnectionIdExpiryGet(connection_id: string) {
    return this.request("GET", `/nexora-api/v1/integrations/connections/${connection_id}/expiry`);
  }

  getConnectionHealthNexoraApiV1IntegrationsConnectionsConnectionIdHealthGet(connection_id: string) {
    return this.request("GET", `/nexora-api/v1/integrations/connections/${connection_id}/health`);
  }

  getConnectionHistoryNexoraApiV1IntegrationsConnectionsConnectionIdHistoryGet(connection_id: string) {
    return this.request("GET", `/nexora-api/v1/integrations/connections/${connection_id}/history`);
  }

  getConnectionNexoraApiV1AuthSsoConnectionsConnectionIdGet(connection_id: string) {
    return this.request("GET", `/nexora-api/v1/auth/sso/connections/${connection_id}`);
  }

  getConversationNexoraApiV1CopilotConversationsConversationIdGet(conversation_id: string) {
    return this.request("GET", `/nexora-api/v1/copilot/conversations/${conversation_id}`);
  }

  getCredentialNexoraApiV1CredentialsCredentialIdGet(credential_id: string) {
    return this.request("GET", `/nexora-api/v1/credentials/${credential_id}`);
  }

  getCurrentOperationNexoraApiV1CustomerPilotOperationGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation`);
  }

  getCustomerApprovalNexoraApiV1PilotApprovalsApprovalIdGet(approval_id: string) {
    return this.request("GET", `/nexora-api/v1/pilot/approvals/${approval_id}`);
  }

  getCustomerPilotPrerequisitesNexoraApiV1OnboardingIntegrationsCustomerPilotPrerequisitesGet() {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/customer-pilot-prerequisites`);
  }

  getDashboardNexoraApiV1CustomerSuccessDashboardGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/dashboard`);
  }

  getDashboardNexoraApiV1MonitoringDashboardGet() {
    return this.request("GET", `/nexora-api/v1/monitoring/dashboard`);
  }

  getDashboardNexoraApiV1ReliabilityDashboardGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/reliability-dashboard`, { params: opts.params });
  }

  getDeploymentArtifactNexoraApiV1AgentsDeploymentArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/deployment/artifacts/${artifact_id}`);
  }

  getDeploymentDryRunStatusNexoraApiV1PilotDeploymentReadinessDryRunGet() {
    return this.request("GET", `/nexora-api/v1/pilot/deployment-readiness/dry-run`);
  }

  getDeploymentLogsNexoraApiV1DeploymentsDeploymentIdLogsGet(deployment_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/deployments/${deployment_id}/logs`, { params: opts.params });
  }

  getDeploymentNexoraApiV1DeliveryDeploymentsDeploymentIdGet(deployment_id: string) {
    return this.request("GET", `/nexora-api/v1/delivery/deployments/${deployment_id}`);
  }

  getDeploymentNexoraApiV1DeploymentsDeploymentIdGet(deployment_id: string) {
    return this.request("GET", `/nexora-api/v1/deployments/${deployment_id}`);
  }

  getDeploymentReadinessNexoraApiV1PilotDeploymentReadinessGet() {
    return this.request("GET", `/nexora-api/v1/pilot/deployment-readiness`);
  }

  getDeploymentRiskNexoraApiV1DeploymentRiskGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/deployment-risk`, { params: opts.params });
  }

  getDeploymentRunNexoraApiV1AgentsDeploymentRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/deployment/runs/${run_id}`);
  }

  getDeploymentSafetyAnalysisNexoraApiV1DeploymentSafetyAnalysesAnalysisIdGet(analysis_id: string) {
    return this.request("GET", `/nexora-api/v1/deployment-safety/analyses/${analysis_id}`);
  }

  getDiagnosticsNexoraApiV1PilotSupportDiagnosticsGet() {
    return this.request("GET", `/nexora-api/v1/pilot/support/diagnostics`);
  }

  getDockerAgentArtifactNexoraApiV1AgentsDockerAgentArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/docker-agent/artifacts/${artifact_id}`);
  }

  getDockerAgentRunNexoraApiV1AgentsDockerAgentRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/docker-agent/runs/${run_id}`);
  }

  getDocsImageRenderingNexoraApiV1DocsImageRenderingGet() {
    return this.request("GET", `/nexora-api/v1/docs/image-rendering`);
  }

  getDocsReadinessNexoraApiV1DocsReadinessGet() {
    return this.request("GET", `/nexora-api/v1/docs/readiness`);
  }

  getDocsScreenshotAuditNexoraApiV1DocsScreenshotAuditGet() {
    return this.request("GET", `/nexora-api/v1/docs/screenshot-audit`);
  }

  getDocsVerificationReadinessNexoraApiV1DocsVerificationReadinessGet() {
    return this.request("GET", `/nexora-api/v1/docs/verification-readiness`);
  }

  getDocsVisualReadinessNexoraApiV1DocsVisualReadinessGet() {
    return this.request("GET", `/nexora-api/v1/docs/visual-readiness`);
  }

  getEvidenceNexoraApiV1CustomerPilotOperationOperationIdEvidenceGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation/${operation_id}/evidence`);
  }

  getEvidenceNexoraApiV1OnboardingIntegrationsSessionsSessionIdEvidenceGet(session_id: string) {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/evidence`);
  }

  getExecutionNexoraApiV1PlatformExecutionsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/platform/executions/${run_id}`);
  }

  getExecutionPlanNexoraApiV1WorkflowsWorkflowIdExecutionPlanGet(workflow_id: string) {
    return this.request("GET", `/nexora-api/v1/workflows/${workflow_id}/execution-plan`);
  }

  getExecutionStatusNexoraApiV1CustomerPilotOperationOperationIdExecutionStatusGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation/${operation_id}/execution-status`);
  }

  getExecutionStatusNexoraApiV1PilotExecutionStatusGet() {
    return this.request("GET", `/nexora-api/v1/pilot/execution/status`);
  }

  getForecastNexoraApiV1CapacityForecastsForecastIdGet(forecast_id: string) {
    return this.request("GET", `/nexora-api/v1/capacity/forecasts/${forecast_id}`);
  }

  getFrontendArchitectArtifactNexoraApiV1AgentsFrontendArchitectArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-architect/artifacts/${artifact_id}`);
  }

  getFrontendArchitectRunNexoraApiV1AgentsFrontendArchitectRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-architect/runs/${run_id}`);
  }

  getFrontendCodeReviewArtifactNexoraApiV1AgentsFrontendCodeReviewArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-code-review/artifacts/${artifact_id}`);
  }

  getFrontendCodeReviewRunNexoraApiV1AgentsFrontendCodeReviewRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-code-review/runs/${run_id}`);
  }

  getFrontendExecutionArtifactNexoraApiV1AgentsFrontendExecutionArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-execution/artifacts/${artifact_id}`);
  }

  getFrontendExecutionRunNexoraApiV1AgentsFrontendExecutionRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-execution/runs/${run_id}`);
  }

  getFrontendV1ArtifactNexoraApiV1AgentsFrontendV1ArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v1/artifacts/${artifact_id}`);
  }

  getFrontendV1RunNexoraApiV1AgentsFrontendV1RunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v1/runs/${run_id}`);
  }

  getFrontendV2ArtifactNexoraApiV1AgentsFrontendV2ArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v2/artifacts/${artifact_id}`);
  }

  getFrontendV2RunNexoraApiV1AgentsFrontendV2RunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v2/runs/${run_id}`);
  }

  getFrontendV3ArtifactNexoraApiV1AgentsFrontendV3ArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v3/artifacts/${artifact_id}`);
  }

  getFrontendV3RunNexoraApiV1AgentsFrontendV3RunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v3/runs/${run_id}`);
  }

  getFullstackAssemblyArtifactNexoraApiV1AgentsFullstackAssemblyArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/fullstack-assembly/artifacts/${artifact_id}`);
  }

  getFullstackAssemblyRunNexoraApiV1AgentsFullstackAssemblyRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/fullstack-assembly/runs/${run_id}`);
  }

  getGalleryNexoraApiV1DemoAssetsGalleryGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/demo-assets/gallery`, { params: opts.params });
  }

  getHumanGuideNexoraApiV1CustomerSuccessHumanGuidesKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/human-guides/${key}`);
  }

  getImpactAnalysisNexoraApiV1ImpactAnalysisRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/impact-analysis/${run_id}`);
  }

  getIncidentActionsNexoraApiV1IncidentsInvestigationIdActionsGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/actions`);
  }

  getIncidentChangesNexoraApiV1IncidentsInvestigationIdChangesGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/changes`);
  }

  getIncidentCommandCenterNexoraApiV1IncidentsInvestigationIdCommandCenterGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/command-center`);
  }

  getIncidentNexoraApiV1IncidentsInvestigationIdGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}`);
  }

  getIncidentRecommendationsNexoraApiV1IncidentsInvestigationIdRecommendationsGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/recommendations`);
  }

  getIncidentTimelineNexoraApiV1IncidentsInvestigationIdTimelineGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/timeline`);
  }

  getInfrastructureArchitectArtifactNexoraApiV1AgentsInfrastructureArchitectArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/infrastructure-architect/artifacts/${artifact_id}`);
  }

  getInfrastructureArchitectRunNexoraApiV1AgentsInfrastructureArchitectRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/infrastructure-architect/runs/${run_id}`);
  }

  getIntegrationTestArtifactNexoraApiV1AgentsIntegrationTestsArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/integration-tests/artifacts/${artifact_id}`);
  }

  getIntegrationTestRunNexoraApiV1AgentsIntegrationTestsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/integration-tests/runs/${run_id}`);
  }

  getIntegrationVisualNexoraApiV1CustomerSuccessIntegrationVisualsKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/integration-visuals/${key}`);
  }

  getJobNexoraApiV1JobsJobIdGet(job_id: string) {
    return this.request("GET", `/nexora-api/v1/jobs/${job_id}`);
  }

  getJourneyNexoraApiV1CustomerSuccessJourneysKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/journeys/${key}`);
  }

  getKubernetesArtifactNexoraApiV1AgentsKubernetesArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/kubernetes/artifacts/${artifact_id}`);
  }

  getKubernetesRunNexoraApiV1AgentsKubernetesRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/kubernetes/runs/${run_id}`);
  }

  getLaunchReadinessNexoraApiV1PilotLaunchReadinessGet() {
    return this.request("GET", `/nexora-api/v1/pilot/launch-readiness`);
  }

  getLearningPathNexoraApiV1CustomerSuccessLearningPathsKeyGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/learning-paths/${key}`, { params: opts.params });
  }

  getLeastPrivilegeGuideNexoraApiV1OnboardingIntegrationsSessionsSessionIdLeastPrivilegeGuideGet(session_id: string) {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/least-privilege-guide`);
  }

  getLiveOperationNexoraApiV1PilotLiveOperationsOperationIdGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/pilot/live-operations/${operation_id}`);
  }

  getMaintenanceNexoraApiV1OpsMaintenanceGet() {
    return this.request("GET", `/nexora-api/v1/ops/maintenance`);
  }

  getModuleNexoraApiV1CustomerSuccessModulesKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/modules/${key}`);
  }

  getNavigationNexoraApiV1DocsNavigationGet() {
    return this.request("GET", `/nexora-api/v1/docs/navigation`);
  }

  getNotificationPreferencesNexoraApiV1CustomerPilotNotificationPreferencesGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/notification-preferences`);
  }

  getObservabilityArtifactNexoraApiV1AgentsObservabilityArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/observability/artifacts/${artifact_id}`);
  }

  getObservabilityRunNexoraApiV1AgentsObservabilityRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/observability/runs/${run_id}`);
  }

  getOnboardingNexoraApiV1OnboardingSessionIdGet(session_id: string) {
    return this.request("GET", `/nexora-api/v1/onboarding/${session_id}`);
  }

  getOperationNexoraApiV1CustomerPilotOperationOperationIdGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation/${operation_id}`);
  }

  getOperationsReadinessNexoraApiV1PilotOperationsReadinessGet() {
    return this.request("GET", `/nexora-api/v1/pilot/operations-readiness`);
  }

  getOperatorHandoffNexoraApiV1PilotLiveOperationsOperationIdOperatorHandoffGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/pilot/live-operations/${operation_id}/operator-handoff`);
  }

  getOrganizationNexoraApiV1OrganizationsOrganizationIdGet(organization_id: string) {
    return this.request("GET", `/nexora-api/v1/organizations/${organization_id}`);
  }

  getOverviewNexoraApiV1CustomerPilotOverviewGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/overview`);
  }

  getPerformanceTestArtifactNexoraApiV1AgentsPerformanceTestsArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/performance-tests/artifacts/${artifact_id}`);
  }

  getPerformanceTestRunNexoraApiV1AgentsPerformanceTestsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/performance-tests/runs/${run_id}`);
  }

  getPilotDashboardNexoraApiV1PilotDashboardGet() {
    return this.request("GET", `/nexora-api/v1/pilot/dashboard`);
  }

  getPilotReadinessNexoraApiV1PilotReadinessGet() {
    return this.request("GET", `/nexora-api/v1/pilot/readiness`);
  }

  getPlaybookNexoraApiV1CustomerSuccessPlaybooksKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/playbooks/${key}`);
  }

  getPlaybookNexoraApiV1TestPlaybooksPlaybookIdGet(playbook_id: string) {
    return this.request("GET", `/nexora-api/v1/test-playbooks/${playbook_id}`);
  }

  getPortalNexoraApiV1CustomerSuccessPortalGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/portal`);
  }

  getPortalNexoraApiV1DocsPortalGet() {
    return this.request("GET", `/nexora-api/v1/docs/portal`);
  }

  getPostmortemNexoraApiV1PostmortemsPostmortemIdGet(postmortem_id: string) {
    return this.request("GET", `/nexora-api/v1/postmortems/${postmortem_id}`);
  }

  getPreferencesNexoraApiV1ProductPreferencesGet() {
    return this.request("GET", `/nexora-api/v1/product/preferences`);
  }

  getProjectNexoraApiV1ProjectsProjectIdGet(project_id: string) {
    return this.request("GET", `/nexora-api/v1/projects/${project_id}`);
  }

  getPromptNexoraApiV1AiPromptsKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/ai/prompts/${key}`);
  }

  getQaApprovalArtifactNexoraApiV1AgentsQaApprovalsArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/qa-approvals/artifacts/${artifact_id}`);
  }

  getQaApprovalRunNexoraApiV1AgentsQaApprovalsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/qa-approvals/runs/${run_id}`);
  }

  getQaArchitectArtifactNexoraApiV1AgentsQaArchitectArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/qa-architect/artifacts/${artifact_id}`);
  }

  getQaArchitectRunNexoraApiV1AgentsQaArchitectRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/qa-architect/runs/${run_id}`);
  }

  getQualityNexoraApiV1CustomerSuccessQualityGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/quality`);
  }

  getRbacReportNexoraApiV1OnboardingIntegrationsSessionsSessionIdRbacReportGet(session_id: string) {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/rbac-report`);
  }

  getReadinessNexoraApiV1CustomerPilotReadinessGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/readiness`);
  }

  getReadinessNexoraApiV1CustomerSuccessReadinessGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/readiness`);
  }

  getReadinessNexoraApiV1OnboardingIntegrationsReadinessGet() {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/readiness`);
  }

  getRecommendationNexoraApiV1OperatorRecommendationsRecommendationIdGet(recommendation_id: string) {
    return this.request("GET", `/nexora-api/v1/operator/recommendations/${recommendation_id}`);
  }

  getRegenerationNexoraApiV1RegenerationRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/regeneration/${run_id}`);
  }

  getReleaseChannelNexoraApiV1GaReleaseChannelGet() {
    return this.request("GET", `/nexora-api/v1/ga/release/channel`);
  }

  getReleaseEvidenceNexoraApiV1DeliveryReleaseReliabilityReliabilityIdEvidenceGet(reliability_id: string) {
    return this.request("GET", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/evidence`);
  }

  getReleaseReliabilityNexoraApiV1DeliveryReleaseReliabilityReliabilityIdGet(reliability_id: string) {
    return this.request("GET", `/nexora-api/v1/delivery/release-reliability/${reliability_id}`);
  }

  getRemediationActionApprovalsNexoraApiV1RemediationActionsActionIdApprovalsGet(action_id: string) {
    return this.request("GET", `/nexora-api/v1/remediation-actions/${action_id}/approvals`);
  }

  getRemediationActionNexoraApiV1RemediationActionsActionIdGet(action_id: string) {
    return this.request("GET", `/nexora-api/v1/remediation-actions/${action_id}`);
  }

  getRemediationExecutionNexoraApiV1SecurityRemediationProposalIdExecutionGet(proposal_id: string) {
    return this.request("GET", `/nexora-api/v1/security/remediation/${proposal_id}/execution`);
  }

  getReportNexoraApiV1ExecutiveReportsReportIdGet(report_id: string) {
    return this.request("GET", `/nexora-api/v1/executive-reports/${report_id}`);
  }

  getRepositoryNexoraApiV1DeliveryRepositoriesRepoIdGet(repo_id: string) {
    return this.request("GET", `/nexora-api/v1/delivery/repositories/${repo_id}`);
  }

  getRequirementNexoraApiV1RequirementsRequirementIdGet(requirement_id: string) {
    return this.request("GET", `/nexora-api/v1/requirements/${requirement_id}`);
  }

  getRoutingNexoraApiV1AiRoutingGet() {
    return this.request("GET", `/nexora-api/v1/ai/routing`);
  }

  getRunNexoraApiV1TestPlaybooksRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/test-playbooks/runs/${run_id}`);
  }

  getRunbookNexoraApiV1RunbooksRunbookIdGet(runbook_id: string) {
    return this.request("GET", `/nexora-api/v1/runbooks/${runbook_id}`);
  }

  getSalesModeNexoraApiV1DemoSalesModeGet() {
    return this.request("GET", `/nexora-api/v1/demo/sales-mode`);
  }

  getScenarioNexoraApiV1DemoScenariosScenarioIdGet(scenario_id: string) {
    return this.request("GET", `/nexora-api/v1/demo-scenarios/${scenario_id}`);
  }

  getScheduleNexoraApiV1OncallSchedulesScheduleIdGet(schedule_id: string) {
    return this.request("GET", `/nexora-api/v1/oncall/schedules/${schedule_id}`);
  }

  getScorecardNexoraApiV1PilotScorecardGet() {
    return this.request("GET", `/nexora-api/v1/pilot/scorecard`);
  }

  getScreenshotCoverageNexoraApiV1CustomerSuccessScreenshotCoverageGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-coverage`);
  }

  getScreenshotManifestNexoraApiV1DemoWalkthroughsScreenshotsGet() {
    return this.request("GET", `/nexora-api/v1/demo-walkthroughs/screenshots`);
  }

  getScreenshotNexoraApiV1CustomerSuccessScreenshotsScreenshotIdGet(screenshot_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshots/${screenshot_id}`);
  }

  getScreenshotsNexoraApiV1CustomerSuccessScreenshotsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshots`, { params: opts.params });
  }

  getSecurityPolicyNexoraApiV1SecurityPolicyGet() {
    return this.request("GET", `/nexora-api/v1/security-policy`);
  }

  getSecurityTestArtifactNexoraApiV1AgentsSecurityTestsArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/security-tests/artifacts/${artifact_id}`);
  }

  getSecurityTestRunNexoraApiV1AgentsSecurityTestsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/security-tests/runs/${run_id}`);
  }

  getServiceAccountNexoraApiV1ServiceAccountsSaIdGet(sa_id: string) {
    return this.request("GET", `/nexora-api/v1/service-accounts/${sa_id}`);
  }

  getServiceNexoraApiV1ServicesServiceIdGet(service_id: string) {
    return this.request("GET", `/nexora-api/v1/services/${service_id}`);
  }

  getSessionNexoraApiV1OnboardingIntegrationsSessionsSessionIdGet(session_id: string) {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}`);
  }

  getSlaNexoraApiV1SecuritySlaGet() {
    return this.request("GET", `/nexora-api/v1/security/sla`);
  }

  getSnapshotNexoraApiV1ArchitectureSnapshotIdGet(snapshot_id: string) {
    return this.request("GET", `/nexora-api/v1/architecture/${snapshot_id}`);
  }

  getSreApprovalArtifactNexoraApiV1AgentsSreApprovalArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/sre-approval/artifacts/${artifact_id}`);
  }

  getSreApprovalRunNexoraApiV1AgentsSreApprovalRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/sre-approval/runs/${run_id}`);
  }

  getSubscriptionNexoraApiV1BillingSubscriptionGet() {
    return this.request("GET", `/nexora-api/v1/billing/subscription`);
  }

  getSuccessNexoraApiV1CustomerSuccessSuccessCenterKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/success-center/${key}`);
  }

  getSummaryNexoraApiV1ReliabilityDashboardSummaryGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/reliability-dashboard/summary`, { params: opts.params });
  }

  getTeamNexoraApiV1TeamsTeamIdGet(team_id: string) {
    return this.request("GET", `/nexora-api/v1/teams/${team_id}`);
  }

  getTeamTemplateNexoraApiV1TeamTemplatesSlugGet(slug: string) {
    return this.request("GET", `/nexora-api/v1/team-templates/${slug}`);
  }

  getTimelineNexoraApiV1CustomerPilotTimelineGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/timeline`, { params: opts.params });
  }

  getTourNexoraApiV1CustomerSuccessToursKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/tours/${key}`);
  }

  getTourNexoraApiV1ProductToursTourIdGet(tour_id: string) {
    return this.request("GET", `/nexora-api/v1/product-tours/${tour_id}`);
  }

  getUiuxArtifactNexoraApiV1AgentsUiuxArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/uiux/artifacts/${artifact_id}`);
  }

  getUiuxRunNexoraApiV1AgentsUiuxRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/uiux/runs/${run_id}`);
  }

  getUnitTestArtifactNexoraApiV1AgentsUnitTestsArtifactsArtifactIdGet(artifact_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/unit-tests/artifacts/${artifact_id}`);
  }

  getUnitTestRunNexoraApiV1AgentsUnitTestsRunsRunIdGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/agents/unit-tests/runs/${run_id}`);
  }

  getVerificationNexoraApiV1CustomerPilotOperationOperationIdVerificationGet(operation_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-pilot/operation/${operation_id}/verification`);
  }

  getVideoNexoraApiV1CustomerSuccessVideosVideoIdGet(video_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/videos/${video_id}`);
  }

  getWalkthroughNexoraApiV1DemoWalkthroughsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/demo-walkthroughs`, { params: opts.params });
  }

  getWarRoomNexoraApiV1WarRoomsWarRoomIdGet(war_room_id: string) {
    return this.request("GET", `/nexora-api/v1/war-rooms/${war_room_id}`);
  }

  getWorkflowApprovalNexoraApiV1WorkflowApprovalsApprovalIdGet(approval_id: string) {
    return this.request("GET", `/nexora-api/v1/workflow-approvals/${approval_id}`);
  }

  getWorkflowExecutionNexoraApiV1WorkflowExecutionsExecutionIdGet(execution_id: string) {
    return this.request("GET", `/nexora-api/v1/workflow-executions/${execution_id}`);
  }

  getWorkflowExecutionStatusNexoraApiV1WorkflowExecutionsExecutionIdStatusGet(execution_id: string) {
    return this.request("GET", `/nexora-api/v1/workflow-executions/${execution_id}/status`);
  }

  getWorkflowNexoraApiV1WorkflowsWorkflowIdGet(workflow_id: string) {
    return this.request("GET", `/nexora-api/v1/workflows/${workflow_id}`);
  }

  getWorkflowScheduleNexoraApiV1AiTeamWorkflowSchedulesScheduleIdGet(schedule_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-team-workflow-schedules/${schedule_id}`);
  }

  getWorkflowTemplateNexoraApiV1WorkflowTemplatesSlugGet(slug: string) {
    return this.request("GET", `/nexora-api/v1/workflow-templates/${slug}`);
  }

  getWorkspaceNexoraApiV1WorkspacesWorkspaceIdGet(workspace_id: string) {
    return this.request("GET", `/nexora-api/v1/workspaces/${workspace_id}`);
  }

  globalSearchNexoraApiV1PlatformSearchGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/search`, { params: opts.params });
  }

  grantExceptionNexoraApiV1SecurityExceptionsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/exceptions`, { body: opts.body });
  }

  graphAnalyticsNexoraApiV1PlatformGraphAnalyticsGet() {
    return this.request("GET", `/nexora-api/v1/platform/graph/analytics`);
  }

  handoverPdfNexoraApiV1OpsWorkspaceHandoverHandoverIdExportPdfGet(handover_id: string) {
    return this.request("GET", `/nexora-api/v1/ops-workspace/handover/${handover_id}/export/pdf`);
  }

  healthCenterNexoraApiV1GaHealthGet() {
    return this.request("GET", `/nexora-api/v1/ga/health`);
  }

  healthNexoraApiHealthGet() {
    return this.request("GET", `/nexora-api/health`);
  }

  healthOverviewNexoraApiV1ServicesHealthGet() {
    return this.request("GET", `/nexora-api/v1/services/health`);
  }

  historyNexoraApiV1OperatorHistoryGet() {
    return this.request("GET", `/nexora-api/v1/operator/history`);
  }

  humanGuidesQualityNexoraApiV1CustomerSuccessHumanGuidesQualityGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/human-guides-quality`);
  }

  iacSecurityNexoraApiV1SecurityIacGet() {
    return this.request("GET", `/nexora-api/v1/security/iac`);
  }

  identitySecurityNexoraApiV1SecurityIdentityGet() {
    return this.request("GET", `/nexora-api/v1/security/identity`);
  }

  importConfigNexoraApiV1OpsConfigImportPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ops/config/import`, { body: opts.body });
  }

  importSamlMetadataNexoraApiV1AuthSsoConnectionsConnectionIdSamlImportMetadataPost(connection_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/sso/connections/${connection_id}/saml/import-metadata`, { body: opts.body });
  }

  importSbomNexoraApiV1SecuritySbomImportPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/sbom/import`, { body: opts.body });
  }

  inboxUnreadCountNexoraApiV1ProductInboxUnreadCountGet() {
    return this.request("GET", `/nexora-api/v1/product/inbox/unread-count`);
  }

  incidentAnalyticsNexoraApiV1IncidentsAnalyticsGet() {
    return this.request("GET", `/nexora-api/v1/incidents/analytics`);
  }

  incidentBlastRadiusNexoraApiV1IncidentsIncidentIdBlastRadiusGet(incident_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${incident_id}/blast-radius`);
  }

  ingestMetricsNexoraApiV1CapacityMetricsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/capacity/metrics`, { body: opts.body });
  }

  ingestWebhookNexoraApiV1MonitoringIngestPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/monitoring/ingest`, { body: opts.body });
  }

  installPluginNexoraApiV1PlatformPluginsInstallPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/plugins/install`, { body: opts.body });
  }

  integrationDashboardNexoraApiV1IntegrationsDashboardGet() {
    return this.request("GET", `/nexora-api/v1/integrations/dashboard`);
  }

  integrationHealthBoardNexoraApiV1IntegrationsConnectionsHealthBoardGet() {
    return this.request("GET", `/nexora-api/v1/integrations/connections/health-board`);
  }

  integrationVisualsNexoraApiV1CustomerSuccessIntegrationVisualsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/integration-visuals`);
  }

  investigateIncidentNexoraApiV1IncidentsInvestigatePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/investigate`, { body: opts.body });
  }

  issueConfirmationTokenNexoraApiV1PilotLiveOperationsOperationIdConfirmationTokenPost(operation_id: string) {
    return this.request("POST", `/nexora-api/v1/pilot/live-operations/${operation_id}/confirmation-token`);
  }

  issueLicenseNexoraApiV1BillingAdminLicensesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/admin/licenses`, { body: opts.body });
  }

  issueServiceAccountKeyNexoraApiV1ServiceAccountsSaIdKeysPost(sa_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/service-accounts/${sa_id}/keys`, { body: opts.body });
  }

  issueSupportTokenNexoraApiV1GaSupportTokenPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ga/support/token`, { body: opts.body });
  }

  issueSupportTokenNexoraApiV1PilotSupportTokenPost() {
    return this.request("POST", `/nexora-api/v1/pilot/support/token`);
  }

  journeyDiagramsNexoraApiV1CustomerSuccessJourneyDiagramsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/journey-diagrams`);
  }

  journeyExportNexoraApiV1CustomerSuccessJourneysKeyExportGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/journeys/${key}/export`, { params: opts.params });
  }

  journeyManualNexoraApiV1CustomerSuccessJourneysKeyManualGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/journeys/${key}/manual`);
  }

  journeyManualsNexoraApiV1CustomerSuccessJourneyManualsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/journey-manuals`);
  }

  journeyVerificationNexoraApiV1CustomerSuccessJourneyVerificationGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/journey-verification`);
  }

  journeyWalkthroughsNexoraApiV1CustomerSuccessJourneyWalkthroughsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/journey-walkthroughs`);
  }

  k8sCapabilitiesNexoraApiV1ControlPlaneClustersClusterIdK8SCapabilitiesGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/capabilities`);
  }

  k8sOverviewNexoraApiV1ControlPlaneClustersClusterIdK8SOverviewGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/overview`);
  }

  k8sReadNexoraApiV1ControlPlaneClustersClusterIdK8SReadPost(cluster_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/read`, { body: opts.body });
  }

  kubernetesSecurityNexoraApiV1SecurityKubernetesGet() {
    return this.request("GET", `/nexora-api/v1/security/kubernetes`);
  }

  latestComplianceNexoraApiV1PlatformEngineeringComplianceLatestGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/compliance/latest`);
  }

  latestDailyBriefingNexoraApiV1OpsWorkspaceBriefingDailyLatestGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/briefing/daily/latest`);
  }

  latestExecutiveBriefingNexoraApiV1OperatorExecutiveLatestGet() {
    return this.request("GET", `/nexora-api/v1/operator/executive/latest`);
  }

  latestHandoverNexoraApiV1OpsWorkspaceHandoverLatestGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/handover/latest`);
  }

  learningNexoraApiV1OperatorLearningGet() {
    return this.request("GET", `/nexora-api/v1/operator/learning`);
  }

  lifecycleNexoraApiV1CustomerSuccessLifecycleGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/lifecycle`);
  }

  lifecycleReportNexoraApiV1CustomerSuccessLifecycleReportGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/lifecycle-report`);
  }

  listActivityNexoraApiV1PlatformActivityGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/activity`, { params: opts.params });
  }

  listAgentAuditNexoraApiV1AiAgentsAgentIdAuditGet(agent_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-agents/${agent_id}/audit`);
  }

  listAgentRunsNexoraApiV1AgentsRunsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/runs`, { params: opts.params });
  }

  listAiAgentTemplatesNexoraApiV1AiAgentTemplatesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-agent-templates`, { params: opts.params });
  }

  listAiAgentsNexoraApiV1AiAgentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-agents`, { params: opts.params });
  }

  listAiTeamAgentMemoryNexoraApiV1AiTeamAgentsAgentIdMemoryGet(agent_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-team-agents/${agent_id}/memory`, { params: opts.params });
  }

  listAiTeamAgentRunsNexoraApiV1AiTeamAgentsAgentIdRunsGet(agent_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-team-agents/${agent_id}/runs`, { params: opts.params });
  }

  listAiTeamAgentToolsNexoraApiV1AiTeamAgentsAgentIdToolsGet(agent_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-team-agents/${agent_id}/tools`);
  }

  listAiTeamAgentsNexoraApiV1AiTeamAgentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-team-agents`, { params: opts.params });
  }

  listAiTeamDocumentsNexoraApiV1AiTeamsTeamIdDocumentsGet(team_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-teams/${team_id}/documents`, { params: opts.params });
  }

  listAiTeamRunsNexoraApiV1AiTeamsTeamIdRunsGet(team_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-teams/${team_id}/runs`, { params: opts.params });
  }

  listAiTeamWorkflowRunsNexoraApiV1AiTeamWorkflowsWorkflowIdRunsGet(workflow_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-team-workflows/${workflow_id}/runs`, { params: opts.params });
  }

  listAiTeamWorkflowsNexoraApiV1AiTeamWorkflowsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-team-workflows`, { params: opts.params });
  }

  listAiTeamsNexoraApiV1AiTeamsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-teams`, { params: opts.params });
  }

  listAiToolRunsNexoraApiV1AiToolsToolIdRunsGet(tool_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-tools/${tool_id}/runs`, { params: opts.params });
  }

  listAiToolsNexoraApiV1AiToolsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-tools`, { params: opts.params });
  }

  listAlertsNexoraApiV1MonitoringAlertsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/monitoring/alerts`, { params: opts.params });
  }

  listAllRunsNexoraApiV1DemoScenariosRunsGet() {
    return this.request("GET", `/nexora-api/v1/demo-scenarios/runs`);
  }

  listAnalysesNexoraApiV1CostOptimizationAnalysesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/cost-optimization/analyses`, { params: opts.params });
  }

  listAnnotationsNexoraApiV1CustomerSuccessAnnotationsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/annotations`, { params: opts.params });
  }

  listApplicationVersionsNexoraApiV1ApplicationVersionsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/application-versions`, { params: opts.params });
  }

  listApprovalRunsForRequirementNexoraApiV1AgentsApprovalRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/approval/${requirement_id}`, { params: opts.params });
  }

  listArchitectureNexoraApiV1CustomerSuccessArchitectureGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/architecture`);
  }

  listArticlesNexoraApiV1DocsArticlesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/docs/articles`, { params: opts.params });
  }

  listArtifactsNexoraApiV1DeliveryArtifactsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/artifacts`);
  }

  listAssessmentsNexoraApiV1ReliabilityGet() {
    return this.request("GET", `/nexora-api/v1/reliability`);
  }

  listAssetsNexoraApiV1DemoAssetsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/demo-assets`, { params: opts.params });
  }

  listBackendArchitectRunsForRequirementNexoraApiV1AgentsBackendArchitectRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/backend-architect/${requirement_id}`, { params: opts.params });
  }

  listBackendCodeReviewRunsForRequirementNexoraApiV1AgentsBackendCodeReviewRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/backend-code-review/${requirement_id}`, { params: opts.params });
  }

  listBackendExecutionRunsForRequirementNexoraApiV1AgentsBackendExecutionRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/backend-execution/${requirement_id}`, { params: opts.params });
  }

  listBackendV1RunsForRequirementNexoraApiV1AgentsBackendV1RequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v1/${requirement_id}`, { params: opts.params });
  }

  listBackendV2RunsForRequirementNexoraApiV1AgentsBackendV2RequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v2/${requirement_id}`, { params: opts.params });
  }

  listBackendV3RunsForRequirementNexoraApiV1AgentsBackendV3RequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/backend-v3/${requirement_id}`, { params: opts.params });
  }

  listBackupsNexoraApiV1GaBackupsGet() {
    return this.request("GET", `/nexora-api/v1/ga/backups`);
  }

  listBusinessAnalystRunsForRequirementNexoraApiV1AgentsBusinessAnalystRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/business-analyst/${requirement_id}`, { params: opts.params });
  }

  listCapturesNexoraApiV1CustomerSuccessCapturesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/captures`, { params: opts.params });
  }

  listCatalogNexoraApiV1PlatformEngineeringCatalogGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/catalog`);
  }

  listCategoriesNexoraApiV1DocsCategoriesGet() {
    return this.request("GET", `/nexora-api/v1/docs/categories`);
  }

  listChangeFailuresNexoraApiV1ChangeFailurePredictionGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/change-failure-prediction`, { params: opts.params });
  }

  listChangeRequestsNexoraApiV1ChangeRequestsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/change-requests`, { params: opts.params });
  }

  listCicdRunsForRequirementNexoraApiV1AgentsCicdRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/cicd/${requirement_id}`, { params: opts.params });
  }

  listCloudAccountsNexoraApiV1ControlPlaneCloudAccountsGet() {
    return this.request("GET", `/nexora-api/v1/control-plane/cloud-accounts`);
  }

  listClusterResourcesNexoraApiV1ControlPlaneClustersClusterIdResourcesGet(cluster_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/resources`, { params: opts.params });
  }

  listClustersNexoraApiV1ControlPlaneClustersGet() {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters`);
  }

  listCommentsNexoraApiV1ProductCollaborationResourceTypeResourceIdCommentsGet(resource_type: string, resource_id: string) {
    return this.request("GET", `/nexora-api/v1/product/collaboration/${resource_type}/${resource_id}/comments`);
  }

  listCommunicationTemplatesNexoraApiV1IncidentsCommunicationsTemplatesGet() {
    return this.request("GET", `/nexora-api/v1/incidents/communications/templates`);
  }

  listCommunicationTemplatesNexoraApiV1PilotCommunicationsTemplatesGet() {
    return this.request("GET", `/nexora-api/v1/pilot/communications/templates`);
  }

  listCommunicationsNexoraApiV1CustomerPilotCommunicationsGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/communications`);
  }

  listCommunicationsNexoraApiV1IncidentsCommunicationsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/incidents/communications`, { params: opts.params });
  }

  listConnectionsNexoraApiV1AuthSsoConnectionsGet() {
    return this.request("GET", `/nexora-api/v1/auth/sso/connections`);
  }

  listConnectionsNexoraApiV1IntegrationsConnectionsGet() {
    return this.request("GET", `/nexora-api/v1/integrations/connections`);
  }

  listConversationsNexoraApiV1CopilotConversationsGet() {
    return this.request("GET", `/nexora-api/v1/copilot/conversations`);
  }

  listCorrelationsNexoraApiV1ObservabilityCorrelationGet() {
    return this.request("GET", `/nexora-api/v1/observability/correlation`);
  }

  listCredentialsNexoraApiV1CredentialsGet() {
    return this.request("GET", `/nexora-api/v1/credentials`);
  }

  listDashboardsNexoraApiV1ProductDashboardsGet() {
    return this.request("GET", `/nexora-api/v1/product/dashboards`);
  }

  listDeadLetterNexoraApiV1JobsDeadLetterGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/jobs/dead-letter`, { params: opts.params });
  }

  listDeadLettersNexoraApiV1MonitoringDeadLettersGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/monitoring/dead-letters`, { params: opts.params });
  }

  listDemoOrganizationsNexoraApiV1DemoOrganizationsGet() {
    return this.request("GET", `/nexora-api/v1/demo-organizations`);
  }

  listDependenciesNexoraApiV1ServiceDependenciesGet() {
    return this.request("GET", `/nexora-api/v1/service-dependencies`);
  }

  listDeploymentRunsForRequirementNexoraApiV1AgentsDeploymentRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/deployment/${requirement_id}`, { params: opts.params });
  }

  listDeploymentSafetyAnalysesNexoraApiV1DeploymentSafetyAnalysesGet() {
    return this.request("GET", `/nexora-api/v1/deployment-safety/analyses`);
  }

  listDeploymentsNexoraApiV1DeliveryDeploymentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/delivery/deployments`, { params: opts.params });
  }

  listDeploymentsNexoraApiV1DeploymentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/deployments`, { params: opts.params });
  }

  listDiagnosticsNexoraApiV1ControlPlaneClustersClusterIdK8SDiagnosticsGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/diagnostics`);
  }

  listDockerAgentRunsForRequirementNexoraApiV1AgentsDockerAgentRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/docker-agent/${requirement_id}`, { params: opts.params });
  }

  listDriftNexoraApiV1PlatformEngineeringDriftGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/drift`);
  }

  listEnvironmentsNexoraApiV1DeliveryEnvironmentsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/environments`);
  }

  listEnvironmentsNexoraApiV1PlatformEngineeringEnvironmentsGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/environments`);
  }

  listEvaluationsNexoraApiV1AiEvaluationsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai/evaluations`, { params: opts.params });
  }

  listEventsNexoraApiV1PlatformEventsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/events`, { params: opts.params });
  }

  listExceptionsNexoraApiV1SecurityExceptionsGet() {
    return this.request("GET", `/nexora-api/v1/security/exceptions`);
  }

  listFindingsNexoraApiV1SecurityFindingsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/security/findings`, { params: opts.params });
  }

  listForecastsNexoraApiV1CapacityForecastsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/capacity/forecasts`, { params: opts.params });
  }

  listFreezeWindowsNexoraApiV1DeliveryFreezeWindowsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/freeze-windows`);
  }

  listFrontendArchitectRunsForRequirementNexoraApiV1AgentsFrontendArchitectRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-architect/${requirement_id}`, { params: opts.params });
  }

  listFrontendCodeReviewRunsForRequirementNexoraApiV1AgentsFrontendCodeReviewRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-code-review/${requirement_id}`, { params: opts.params });
  }

  listFrontendExecutionRunsForRequirementNexoraApiV1AgentsFrontendExecutionRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-execution/${requirement_id}`, { params: opts.params });
  }

  listFrontendV1RunsForRequirementNexoraApiV1AgentsFrontendV1RequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v1/${requirement_id}`, { params: opts.params });
  }

  listFrontendV2RunsForRequirementNexoraApiV1AgentsFrontendV2RequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v2/${requirement_id}`, { params: opts.params });
  }

  listFrontendV3RunsForRequirementNexoraApiV1AgentsFrontendV3RequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/frontend-v3/${requirement_id}`, { params: opts.params });
  }

  listFullstackAssemblyRunsForRequirementNexoraApiV1AgentsFullstackAssemblyRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/fullstack-assembly/${requirement_id}`, { params: opts.params });
  }

  listGitopsNexoraApiV1ControlPlaneClustersClusterIdGitopsGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/gitops`);
  }

  listGitopsNexoraApiV1DeliveryGitopsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/gitops`);
  }

  listGoalsNexoraApiV1OperatorGoalsGet() {
    return this.request("GET", `/nexora-api/v1/operator/goals`);
  }

  listGoldenTemplatesNexoraApiV1PlatformEngineeringGoldenTemplatesGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/golden-templates`);
  }

  listGroupsNexoraApiV1ScimV2GroupsGet() {
    return this.request("GET", `/nexora-api/v1/scim/v2/Groups`);
  }

  listHelmNexoraApiV1ControlPlaneClustersClusterIdHelmGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/helm`);
  }

  listHumanGuidesNexoraApiV1CustomerSuccessHumanGuidesGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/human-guides`);
  }

  listInboxNexoraApiV1ProductInboxGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product/inbox`, { params: opts.params });
  }

  listIncidentCommentsNexoraApiV1IncidentsInvestigationIdCommentsGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/comments`);
  }

  listIncidentEventsNexoraApiV1IncidentsInvestigationIdEventsGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/events`);
  }

  listIncidentTasksNexoraApiV1IncidentsInvestigationIdTasksGet(investigation_id: string) {
    return this.request("GET", `/nexora-api/v1/incidents/${investigation_id}/tasks`);
  }

  listIncidentsNexoraApiV1IncidentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/incidents`, { params: opts.params });
  }

  listInfrastructureArchitectRunsForRequirementNexoraApiV1AgentsInfrastructureArchitectRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/infrastructure-architect/${requirement_id}`, { params: opts.params });
  }

  listInstalledPluginsNexoraApiV1PlatformPluginsGet() {
    return this.request("GET", `/nexora-api/v1/platform/plugins`);
  }

  listIntegrationProvidersNexoraApiV1IntegrationsProvidersGet() {
    return this.request("GET", `/nexora-api/v1/integrations/providers`);
  }

  listIntegrationTestRunsForRequirementNexoraApiV1AgentsIntegrationTestsRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/integration-tests/${requirement_id}`, { params: opts.params });
  }

  listIntegrationsNexoraApiV1IntegrationsGet() {
    return this.request("GET", `/nexora-api/v1/integrations`);
  }

  listIntegrationsNexoraApiV1ObservabilityIntegrationsGet() {
    return this.request("GET", `/nexora-api/v1/observability/integrations`);
  }

  listInvestigationsNexoraApiV1SecurityInvestigationsGet() {
    return this.request("GET", `/nexora-api/v1/security/investigations`);
  }

  listInvoicesNexoraApiV1BillingInvoicesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/billing/invoices`, { params: opts.params });
  }

  listJobsNexoraApiV1JobsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/jobs`, { params: opts.params });
  }

  listJourneysNexoraApiV1CustomerSuccessJourneysGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/journeys`);
  }

  listKubernetesRunsForRequirementNexoraApiV1AgentsKubernetesRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/kubernetes/${requirement_id}`, { params: opts.params });
  }

  listLearningPathsNexoraApiV1CustomerSuccessLearningPathsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/learning-paths`, { params: opts.params });
  }

  listLinkedIncidentsNexoraApiV1DeliveryLinkedIncidentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/delivery/linked-incidents`, { params: opts.params });
  }

  listLiveOperationsNexoraApiV1PilotLiveOperationsGet() {
    return this.request("GET", `/nexora-api/v1/pilot/live-operations`);
  }

  listLogsNexoraApiV1AuditLogsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/audit/logs`, { params: opts.params });
  }

  listMajorIncidentsNexoraApiV1IncidentsMajorGet() {
    return this.request("GET", `/nexora-api/v1/incidents/major`);
  }

  listMcpServersNexoraApiV1AiMcpServersGet() {
    return this.request("GET", `/nexora-api/v1/ai/mcp/servers`);
  }

  listMemoryNexoraApiV1AiMemoryGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai/memory`, { params: opts.params });
  }

  listModulesNexoraApiV1CustomerSuccessModulesGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/modules`);
  }

  listNamespacesNexoraApiV1ControlPlaneClustersClusterIdK8SNamespacesGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/namespaces`);
  }

  listNetworkingNexoraApiV1ControlPlaneClustersClusterIdK8SNetworkingNetKindGet(cluster_id: string, net_kind: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/networking/${net_kind}`, { params: opts.params });
  }

  listNodesNexoraApiV1ControlPlaneClustersClusterIdK8SNodesGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/nodes`);
  }

  listNotificationsNexoraApiV1CustomerPilotNotificationsGet() {
    return this.request("GET", `/nexora-api/v1/customer-pilot/notifications`);
  }

  listNotificationsNexoraApiV1PlatformNotificationsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/notifications`, { params: opts.params });
  }

  listObservabilityRunsForRequirementNexoraApiV1AgentsObservabilityRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/observability/${requirement_id}`, { params: opts.params });
  }

  listOnboardingPathsNexoraApiV1PilotOnboardingPathsGet() {
    return this.request("GET", `/nexora-api/v1/pilot/onboarding-paths`);
  }

  listOperationCatalogNexoraApiV1PilotOperationsCatalogGet() {
    return this.request("GET", `/nexora-api/v1/pilot/operations/catalog`);
  }

  listOperationsNexoraApiV1ControlPlaneOperationsGet() {
    return this.request("GET", `/nexora-api/v1/control-plane/operations`);
  }

  listOperationsNexoraApiV1DeliveryOperationsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/operations`);
  }

  listOrgKeysNexoraApiV1ApiKeysOrganizationGet() {
    return this.request("GET", `/nexora-api/v1/api-keys/organization`);
  }

  listOrganizationInvitationsNexoraApiV1OrganizationsOrganizationIdInvitationsGet(organization_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/organizations/${organization_id}/invitations`, { params: opts.params });
  }

  listOrganizationMembersNexoraApiV1OrganizationsOrganizationIdMembersGet(organization_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/organizations/${organization_id}/members`, { params: opts.params });
  }

  listOrganizationsNexoraApiV1OrganizationsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/organizations`, { params: opts.params });
  }

  listPerformanceTestRunsForRequirementNexoraApiV1AgentsPerformanceTestsRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/performance-tests/${requirement_id}`, { params: opts.params });
  }

  listPersonalKeysNexoraApiV1ApiKeysPersonalGet() {
    return this.request("GET", `/nexora-api/v1/api-keys/personal`);
  }

  listPipelineRunsNexoraApiV1DeliveryPipelineRunsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/pipeline-runs`);
  }

  listPipelinesNexoraApiV1DeliveryPipelinesGet() {
    return this.request("GET", `/nexora-api/v1/delivery/pipelines`);
  }

  listPlansNexoraApiV1BillingPlansGet() {
    return this.request("GET", `/nexora-api/v1/billing/plans`);
  }

  listPlaybooksNexoraApiV1CustomerSuccessPlaybooksGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/playbooks`);
  }

  listPlaybooksNexoraApiV1TestPlaybooksGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/test-playbooks`, { params: opts.params });
  }

  listPodsNexoraApiV1ControlPlaneClustersClusterIdK8SPodsGet(cluster_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/pods`, { params: opts.params });
  }

  listPoliciesNexoraApiV1ControlPlaneClustersClusterIdPoliciesGet(cluster_id: string) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/policies`);
  }

  listPoliciesNexoraApiV1OncallEscalationPoliciesGet() {
    return this.request("GET", `/nexora-api/v1/oncall/escalation-policies`);
  }

  listPoliciesNexoraApiV1OperatorPoliciesGet() {
    return this.request("GET", `/nexora-api/v1/operator/policies`);
  }

  listPostmortemsNexoraApiV1PostmortemsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/postmortems`, { params: opts.params });
  }

  listProjectsNexoraApiV1ProjectsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/projects`, { params: opts.params });
  }

  listPromotionPoliciesNexoraApiV1DeliveryPromotionPoliciesGet() {
    return this.request("GET", `/nexora-api/v1/delivery/promotion-policies`);
  }

  listPromptVersionsNexoraApiV1AiPromptsKeyVersionsGet(key: string) {
    return this.request("GET", `/nexora-api/v1/ai/prompts/${key}/versions`);
  }

  listProposalsNexoraApiV1OperatorProposalsGet() {
    return this.request("GET", `/nexora-api/v1/operator/proposals`);
  }

  listProviderCatalogNexoraApiV1SecurityProvidersGet() {
    return this.request("GET", `/nexora-api/v1/security/providers`);
  }

  listProviderConfigsNexoraApiV1SecurityProvidersConfigGet() {
    return this.request("GET", `/nexora-api/v1/security/providers/config`);
  }

  listProvidersNexoraApiV1AiProvidersGet() {
    return this.request("GET", `/nexora-api/v1/ai/providers`);
  }

  listProvidersNexoraApiV1AuthSsoProvidersGet() {
    return this.request("GET", `/nexora-api/v1/auth/sso/providers`);
  }

  listProvidersNexoraApiV1ControlPlaneProvidersGet() {
    return this.request("GET", `/nexora-api/v1/control-plane/providers`);
  }

  listProvidersNexoraApiV1DeliveryProvidersGet() {
    return this.request("GET", `/nexora-api/v1/delivery/providers`);
  }

  listProvidersNexoraApiV1ObservabilityProvidersGet() {
    return this.request("GET", `/nexora-api/v1/observability/providers`);
  }

  listProvidersNexoraApiV1OnboardingIntegrationsProvidersGet() {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/providers`);
  }

  listProvidersNexoraApiV1PlatformEngineeringProvidersGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/providers`);
  }

  listProvisionsNexoraApiV1PlatformEngineeringProvisionsGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/provisions`);
  }

  listQaApprovalRunsForRequirementNexoraApiV1AgentsQaApprovalsRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/qa-approvals/${requirement_id}`, { params: opts.params });
  }

  listQaArchitectRunsForRequirementNexoraApiV1AgentsQaArchitectRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/qa-architect/${requirement_id}`, { params: opts.params });
  }

  listRcaHypothesesNexoraApiV1SreRcaIncidentIdHypothesesGet(incident_id: string) {
    return this.request("GET", `/nexora-api/v1/sre/rca/${incident_id}/hypotheses`);
  }

  listReadinessConnectionsNexoraApiV1IntegrationsConnectionsReadinessGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/integrations/connections/readiness`, { params: opts.params });
  }

  listRecommendationsNexoraApiV1OperatorRecommendationsGet() {
    return this.request("GET", `/nexora-api/v1/operator/recommendations`);
  }

  listRecommendationsNexoraApiV1SreRecommendationsResourceTypeResourceIdGet(resource_type: string, resource_id: string) {
    return this.request("GET", `/nexora-api/v1/sre/recommendations/${resource_type}/${resource_id}`);
  }

  listReleaseReliabilityNexoraApiV1DeliveryReleaseReliabilityGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/delivery/release-reliability`, { params: opts.params });
  }

  listReleasesNexoraApiV1DeliveryReleasesGet() {
    return this.request("GET", `/nexora-api/v1/delivery/releases`);
  }

  listReleasesNexoraApiV1ReleasesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/releases`, { params: opts.params });
  }

  listRemediationsNexoraApiV1SecurityRemediationGet() {
    return this.request("GET", `/nexora-api/v1/security/remediation`);
  }

  listReportSchedulesNexoraApiV1ProductReportsSchedulesGet() {
    return this.request("GET", `/nexora-api/v1/product/reports/schedules`);
  }

  listReportsNexoraApiV1ExecutiveReportsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/executive-reports`, { params: opts.params });
  }

  listRepositoriesNexoraApiV1DeliveryRepositoriesGet() {
    return this.request("GET", `/nexora-api/v1/delivery/repositories`);
  }

  listRepositoriesNexoraApiV1PlatformEngineeringRepositoriesGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/repositories`);
  }

  listRequirementsNexoraApiV1RequirementsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/requirements`, { params: opts.params });
  }

  listRunApprovalsNexoraApiV1WorkflowRunsRunIdApprovalsGet(run_id: string) {
    return this.request("GET", `/nexora-api/v1/workflow-runs/${run_id}/approvals`);
  }

  listRunbooksNexoraApiV1RunbooksGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/runbooks`, { params: opts.params });
  }

  listRunsNexoraApiV1PlatformEngineeringRunsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform-engineering/runs`, { params: opts.params });
  }

  listSavedSearchesNexoraApiV1ObservabilityLogsSavedSearchesGet() {
    return this.request("GET", `/nexora-api/v1/observability/logs/saved-searches`);
  }

  listSavedViewsNexoraApiV1ProductViewsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product/views`, { params: opts.params });
  }

  listSbomComponentsNexoraApiV1SecuritySbomComponentsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/security/sbom/components`, { params: opts.params });
  }

  listScanRunsNexoraApiV1SecurityScanRunsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/security/scan-runs`, { params: opts.params });
  }

  listScansNexoraApiV1SecurityScansGet() {
    return this.request("GET", `/nexora-api/v1/security/scans`);
  }

  listScenarioRunsNexoraApiV1DemoScenariosScenarioIdRunsGet(scenario_id: string) {
    return this.request("GET", `/nexora-api/v1/demo-scenarios/${scenario_id}/runs`);
  }

  listScenariosNexoraApiV1DemoScenariosGet() {
    return this.request("GET", `/nexora-api/v1/demo-scenarios`);
  }

  listSchedulesNexoraApiV1OncallSchedulesGet() {
    return this.request("GET", `/nexora-api/v1/oncall/schedules`);
  }

  listScimTokensNexoraApiV1ScimV2AdminTokensGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/scim/v2/admin/tokens`, { params: opts.params });
  }

  listScopesNexoraApiV1IdentityScopesGet() {
    return this.request("GET", `/nexora-api/v1/identity/scopes`);
  }

  listSecretsNexoraApiV1PlatformEngineeringSecretsGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/secrets`);
  }

  listSecurityScansNexoraApiV1DeliverySecurityScansGet() {
    return this.request("GET", `/nexora-api/v1/delivery/security/scans`);
  }

  listSecurityTestRunsForRequirementNexoraApiV1AgentsSecurityTestsRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/security-tests/${requirement_id}`, { params: opts.params });
  }

  listServiceAccountKeysNexoraApiV1ServiceAccountsSaIdKeysGet(sa_id: string) {
    return this.request("GET", `/nexora-api/v1/service-accounts/${sa_id}/keys`);
  }

  listServiceAccountsNexoraApiV1ServiceAccountsGet() {
    return this.request("GET", `/nexora-api/v1/service-accounts`);
  }

  listServiceOwnersNexoraApiV1OncallServiceOwnersGet() {
    return this.request("GET", `/nexora-api/v1/oncall/service-owners`);
  }

  listServicesNexoraApiV1ServicesGet() {
    return this.request("GET", `/nexora-api/v1/services`);
  }

  listSessionsNexoraApiV1AuthSessionsGet() {
    return this.request("GET", `/nexora-api/v1/auth/sessions`);
  }

  listSessionsNexoraApiV1OnboardingIntegrationsSessionsGet() {
    return this.request("GET", `/nexora-api/v1/onboarding/integrations/sessions`);
  }

  listSessionsNexoraApiV1SessionsGet() {
    return this.request("GET", `/nexora-api/v1/sessions`);
  }

  listSimulationsNexoraApiV1OperatorSimulationsGet() {
    return this.request("GET", `/nexora-api/v1/operator/simulations`);
  }

  listSlosNexoraApiV1ServicesServiceIdSlosGet(service_id: string) {
    return this.request("GET", `/nexora-api/v1/services/${service_id}/slos`);
  }

  listSnapshotsNexoraApiV1ArchitectureGet() {
    return this.request("GET", `/nexora-api/v1/architecture`);
  }

  listSourceConnectionsNexoraApiV1DeliverySourceConnectionsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/source-connections`);
  }

  listSreApprovalRunsForRequirementNexoraApiV1AgentsSreApprovalRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/sre-approval/${requirement_id}`, { params: opts.params });
  }

  listStacksNexoraApiV1PlatformEngineeringStacksGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/stacks`);
  }

  listStatusPagesNexoraApiV1IncidentsStatusPagesGet() {
    return this.request("GET", `/nexora-api/v1/incidents/status-pages`);
  }

  listStorageNexoraApiV1ControlPlaneClustersClusterIdK8SStorageStorageKindGet(cluster_id: string, storage_kind: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/storage/${storage_kind}`, { params: opts.params });
  }

  listSuccessNexoraApiV1CustomerSuccessSuccessCenterGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/success-center`);
  }

  listTeamAuditEventsNexoraApiV1TeamsTeamIdAuditGet(team_id: string) {
    return this.request("GET", `/nexora-api/v1/teams/${team_id}/audit`);
  }

  listTeamTemplatesNexoraApiV1TeamTemplatesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/team-templates`, { params: opts.params });
  }

  listTeamsNexoraApiV1TeamsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/teams`, { params: opts.params });
  }

  listTemplatesNexoraApiV1DemoOrganizationsTemplatesGet() {
    return this.request("GET", `/nexora-api/v1/demo-organizations/templates`);
  }

  listTemplatesNexoraApiV1PlatformEngineeringTemplatesGet() {
    return this.request("GET", `/nexora-api/v1/platform-engineering/templates`);
  }

  listToolsNexoraApiV1AiToolsGet() {
    return this.request("GET", `/nexora-api/v1/ai/tools`);
  }

  listTourGuidesNexoraApiV1CustomerSuccessTourGuidesGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/tour-guides`);
  }

  listToursNexoraApiV1CustomerSuccessToursGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/tours`, { params: opts.params });
  }

  listToursNexoraApiV1ProductToursGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product-tours`, { params: opts.params });
  }

  listUiuxRunsForRequirementNexoraApiV1AgentsUiuxRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/uiux/${requirement_id}`, { params: opts.params });
  }

  listUnitTestRunsForRequirementNexoraApiV1AgentsUnitTestsRequirementIdGet(requirement_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/agents/unit-tests/${requirement_id}`, { params: opts.params });
  }

  listUsersNexoraApiV1ScimV2UsersGet() {
    return this.request("GET", `/nexora-api/v1/scim/v2/Users`);
  }

  listVariablesNexoraApiV1OrgConfigVariablesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/org-config/variables`, { params: opts.params });
  }

  listVerificationsNexoraApiV1CustomerSuccessVerificationsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/verifications`, { params: opts.params });
  }

  listWarRoomsNexoraApiV1WarRoomsGet() {
    return this.request("GET", `/nexora-api/v1/war-rooms`);
  }

  listWebhooksNexoraApiV1BillingWebhooksGet() {
    return this.request("GET", `/nexora-api/v1/billing/webhooks`);
  }

  listWorkflowApprovalsNexoraApiV1WorkflowApprovalsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/workflow-approvals`, { params: opts.params });
  }

  listWorkflowAuditNexoraApiV1WorkflowsWorkflowIdAuditGet(workflow_id: string) {
    return this.request("GET", `/nexora-api/v1/workflows/${workflow_id}/audit`);
  }

  listWorkflowExecutionAuditNexoraApiV1WorkflowExecutionsExecutionIdAuditGet(execution_id: string) {
    return this.request("GET", `/nexora-api/v1/workflow-executions/${execution_id}/audit`);
  }

  listWorkflowExecutionsNexoraApiV1WorkflowExecutionsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/workflow-executions`, { params: opts.params });
  }

  listWorkflowSchedulesNexoraApiV1AiTeamWorkflowSchedulesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ai-team-workflow-schedules`, { params: opts.params });
  }

  listWorkflowTemplatesNexoraApiV1WorkflowTemplatesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/workflow-templates`, { params: opts.params });
  }

  listWorkflowsNexoraApiV1WorkflowsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/workflows`, { params: opts.params });
  }

  listWorkloadsNexoraApiV1ControlPlaneClustersClusterIdK8SWorkloadsWorkloadKindGet(cluster_id: string, workload_kind: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/workloads/${workload_kind}`, { params: opts.params });
  }

  listWorkspacesNexoraApiV1WorkspacesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/workspaces`, { params: opts.params });
  }

  livezLivezGet() {
    return this.request("GET", `/livez`);
  }

  loginNexoraApiV1AuthLoginPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/login`, { body: opts.body });
  }

  logoutAllNexoraApiV1SessionsLogoutAllPost() {
    return this.request("POST", `/nexora-api/v1/sessions/logout-all`);
  }

  logoutNexoraApiV1AuthLogoutPost() {
    return this.request("POST", `/nexora-api/v1/auth/logout`);
  }

  maintenanceCenterNexoraApiV1OpsWorkspaceMaintenanceGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/maintenance`);
  }

  markAllInboxReadNexoraApiV1ProductInboxReadAllPost() {
    return this.request("POST", `/nexora-api/v1/product/inbox/read-all`);
  }

  markInboxReadNexoraApiV1ProductInboxNoteIdReadPost(note_id: string) {
    return this.request("POST", `/nexora-api/v1/product/inbox/${note_id}/read`);
  }

  markNotificationReadNexoraApiV1CustomerPilotNotificationsNotificationIdReadPost(notification_id: string) {
    return this.request("POST", `/nexora-api/v1/customer-pilot/notifications/${notification_id}/read`);
  }

  marketplaceDiscoverNexoraApiV1GaMarketplaceGet() {
    return this.request("GET", `/nexora-api/v1/ga/marketplace`);
  }

  marketplaceInstallNexoraApiV1GaMarketplaceSlugInstallPost(slug: string) {
    return this.request("POST", `/nexora-api/v1/ga/marketplace/${slug}/install`);
  }

  marketplaceUpgradeNexoraApiV1GaMarketplaceSlugUpgradePost(slug: string) {
    return this.request("POST", `/nexora-api/v1/ga/marketplace/${slug}/upgrade`);
  }

  mcpManifestNexoraApiV1AiMcpManifestGet() {
    return this.request("GET", `/nexora-api/v1/ai/mcp/manifest`);
  }

  meNexoraApiV1AuthMeGet() {
    return this.request("GET", `/nexora-api/v1/auth/me`);
  }

  mfaStatusNexoraApiV1AuthMfaStatusGet() {
    return this.request("GET", `/nexora-api/v1/auth/mfa/status`);
  }

  migrationPreviewNexoraApiV1GaUpgradeMigrationPreviewGet() {
    return this.request("GET", `/nexora-api/v1/ga/upgrade/migration-preview`);
  }

  mttaNexoraApiV1OncallMttaGet() {
    return this.request("GET", `/nexora-api/v1/oncall/mtta`);
  }

  myActivityNexoraApiV1PlatformActivityMeGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/activity/me`, { params: opts.params });
  }

  myLicenseNexoraApiV1BillingLicenseGet() {
    return this.request("GET", `/nexora-api/v1/billing/license`);
  }

  myWorkNexoraApiV1OpsWorkspaceMyWorkGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/my-work`);
  }

  navigationHealthNexoraApiV1CustomerSuccessNavigationHealthGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/navigation-health`);
  }

  navigationMapsNexoraApiV1CustomerSuccessNavigationMapsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/navigation-maps`);
  }

  oncallDashboardNexoraApiV1IncidentsOncallGet() {
    return this.request("GET", `/nexora-api/v1/incidents/oncall`);
  }

  operationalKpisNexoraApiV1OpsWorkspaceKpisGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ops-workspace/kpis`, { params: opts.params });
  }

  operationsCalendarNexoraApiV1OpsWorkspaceCalendarGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/calendar`);
  }

  operationsQueueNexoraApiV1OpsWorkspaceQueueGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/queue`);
  }

  opsCenterNexoraApiV1SreOpsCenterGet() {
    return this.request("GET", `/nexora-api/v1/sre/ops-center`);
  }

  opsDiagnosticsNexoraApiV1OpsDiagnosticsGet() {
    return this.request("GET", `/nexora-api/v1/ops/diagnostics`);
  }

  orgUsageReportNexoraApiV1BillingAdminOrgsOrgIdUsageReportGet(org_id: string) {
    return this.request("GET", `/nexora-api/v1/billing/admin/orgs/${org_id}/usage-report`);
  }

  overrideRemediationActionNexoraApiV1RemediationActionsActionIdOverridePost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/override`, { body: opts.body });
  }

  overviewNexoraApiV1SecurityOverviewGet() {
    return this.request("GET", `/nexora-api/v1/security/overview`);
  }

  patchGroupNexoraApiV1ScimV2GroupsScimIdPatch(scim_id: string) {
    return this.request("PATCH", `/nexora-api/v1/scim/v2/Groups/${scim_id}`);
  }

  patchUserNexoraApiV1ScimV2UsersScimIdPatch(scim_id: string) {
    return this.request("PATCH", `/nexora-api/v1/scim/v2/Users/${scim_id}`);
  }

  pauseRemediationActionNexoraApiV1RemediationActionsActionIdPausePost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/pause`, { body: opts.body });
  }

  pauseRolloutNexoraApiV1DeliveryReleaseReliabilityReliabilityIdPausePost(reliability_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/pause`);
  }

  personasNexoraApiV1SalesPersonasGet() {
    return this.request("GET", `/nexora-api/v1/sales/personas`);
  }

  pinInboxNexoraApiV1ProductInboxNoteIdPinPost(note_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/product/inbox/${note_id}/pin`, { params: opts.params });
  }

  playbookExportNexoraApiV1CustomerSuccessPlaybooksKeyExportGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/playbooks/${key}/export`, { params: opts.params });
  }

  playbookManualNexoraApiV1CustomerSuccessPlaybooksKeyManualGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/playbooks/${key}/manual`);
  }

  playbookManualsNexoraApiV1CustomerSuccessPlaybookManualsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/playbook-manuals`);
  }

  playgroundModelsNexoraApiV1AiPlaygroundModelsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/playground/models`, { body: opts.body });
  }

  playgroundPromptNexoraApiV1AiPlaygroundPromptPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/playground/prompt`, { body: opts.body });
  }

  playgroundProvidersNexoraApiV1AiPlaygroundProvidersPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/playground/providers`, { body: opts.body });
  }

  playgroundTemperaturesNexoraApiV1AiPlaygroundTemperaturesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/playground/temperatures`, { body: opts.body });
  }

  pluginCapabilitiesNexoraApiV1PlatformPluginsCapabilitiesGet() {
    return this.request("GET", `/nexora-api/v1/platform/plugins/capabilities`);
  }

  pluginCatalogNexoraApiV1PlatformPluginsCatalogGet() {
    return this.request("GET", `/nexora-api/v1/platform/plugins/catalog`);
  }

  pluginLifecycleNexoraApiV1PlatformPluginsSlugActionPost(slug: string, action: string) {
    return this.request("POST", `/nexora-api/v1/platform/plugins/${slug}/${action}`);
  }

  pollNexoraApiV1MonitoringPollPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/monitoring/poll`, { body: opts.body });
  }

  postmortemDashboardNexoraApiV1IncidentsPostmortemsGet() {
    return this.request("GET", `/nexora-api/v1/incidents/postmortems`);
  }

  previewInvitationNexoraApiV1InvitationsPreviewTokenGet(token: string) {
    return this.request("GET", `/nexora-api/v1/invitations/preview/${token}`);
  }

  pricingNexoraApiV1SalesPricingGet() {
    return this.request("GET", `/nexora-api/v1/sales/pricing`);
  }

  productVideosNexoraApiV1SalesProductVideosGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/sales/product-videos`, { params: opts.params });
  }

  promoteRolloutNexoraApiV1DeliveryReleaseReliabilityReliabilityIdPromotePost(reliability_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/promote`);
  }

  promotionQueueNexoraApiV1DeliveryPromotionQueueGet() {
    return this.request("GET", `/nexora-api/v1/delivery/promotion-queue`);
  }

  proposalNexoraApiV1SalesProposalPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sales/proposal`, { body: opts.body });
  }

  proposeActionNexoraApiV1OperatorRecommendationsRecommendationIdProposePost(recommendation_id: string) {
    return this.request("POST", `/nexora-api/v1/operator/recommendations/${recommendation_id}/propose`);
  }

  proposeK8SOperationNexoraApiV1ControlPlaneClustersClusterIdK8SOperationsPost(cluster_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters/${cluster_id}/k8s/operations`, { body: opts.body });
  }

  proposeLiveOperationNexoraApiV1PilotLiveOperationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/live-operations`, { body: opts.body });
  }

  proposeOperationNexoraApiV1ControlPlaneOperationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/operations`, { body: opts.body });
  }

  proposeOperationNexoraApiV1DeliveryOperationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/operations`, { body: opts.body });
  }

  proposeRemediationNexoraApiV1SecurityRemediationPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/remediation`, { body: opts.body });
  }

  proposeRolloutNexoraApiV1DeliveryReleaseReliabilityReliabilityIdProposeRolloutPost(reliability_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/propose-rollout`, { body: opts.body });
  }

  proposeRunNexoraApiV1PlatformEngineeringStacksStackIdRunsPost(stack_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/stacks/${stack_id}/runs`, { body: opts.body });
  }

  publicStatusPageNexoraApiV1IncidentsStatusPagesSlugPublicGet(slug: string) {
    return this.request("GET", `/nexora-api/v1/incidents/status-pages/${slug}/public`);
  }

  publishEventNexoraApiV1PlatformEventsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/events`, { body: opts.body });
  }

  publishStatusIncidentNexoraApiV1IncidentsStatusPagesPageIdIncidentsPost(page_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/status-pages/${page_id}/incidents`, { body: opts.body });
  }

  queryMetricsNexoraApiV1ObservabilityMetricsQueryPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/observability/metrics/query`, { body: opts.body });
  }

  readyzReadyzGet() {
    return this.request("GET", `/readyz`);
  }

  recallMemoryNexoraApiV1AiMemoryRecallPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/memory/recall`, { body: opts.body });
  }

  recentlyAddedVideosNexoraApiV1CustomerSuccessVideosRecentlyAddedGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/videos/recently-added`, { params: opts.params });
  }

  recomputeImpactAnalysisNexoraApiV1ImpactAnalysisPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/impact-analysis`, { body: opts.body });
  }

  recordStepNexoraApiV1ProductToursTourIdStepPost(tour_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product-tours/${tour_id}/step`, { body: opts.body });
  }

  recoverExecutionsNexoraApiV1PlatformExecutionsRecoverPost() {
    return this.request("POST", `/nexora-api/v1/platform/executions/recover`);
  }

  refreshBaselineNexoraApiV1PilotBaselineRefreshPost() {
    return this.request("POST", `/nexora-api/v1/pilot/baseline/refresh`);
  }

  refreshNexoraApiV1AuthRefreshPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/refresh`, { body: opts.body });
  }

  regenerateDemoOrganizationNexoraApiV1DemoOrganizationsOrganizationIdRegeneratePost(organization_id: string) {
    return this.request("POST", `/nexora-api/v1/demo-organizations/${organization_id}/regenerate`);
  }

  regenerateRecoveryCodesNexoraApiV1AuthMfaRecoveryCodesRegeneratePost() {
    return this.request("POST", `/nexora-api/v1/auth/mfa/recovery-codes/regenerate`);
  }

  registerCloudAccountNexoraApiV1ControlPlaneCloudAccountsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/cloud-accounts`, { body: opts.body });
  }

  registerClusterNexoraApiV1ControlPlaneClustersPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/control-plane/clusters`, { body: opts.body });
  }

  registerMcpServerNexoraApiV1AiMcpServersPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/mcp/servers`, { body: opts.body });
  }

  registerNexoraApiV1AuthRegisterPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/register`, { body: opts.body });
  }

  reindexSearchNexoraApiV1PlatformSearchReindexPost() {
    return this.request("POST", `/nexora-api/v1/platform/search/reindex`);
  }

  rejectArtifactNexoraApiV1ApprovalArtifactIdRejectPost(artifact_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/approval/${artifact_id}/reject`, { body: opts.body });
  }

  rejectRemediationActionNexoraApiV1RemediationActionsActionIdRejectPost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/reject`, { body: opts.body });
  }

  rejectWorkflowApprovalNexoraApiV1WorkflowApprovalsApprovalIdRejectPost(approval_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/workflow-approvals/${approval_id}/reject`, { body: opts.body });
  }

  releaseAnalyticsNexoraApiV1DeliveryReleaseAnalyticsGet() {
    return this.request("GET", `/nexora-api/v1/delivery/release-analytics`);
  }

  releaseHistoryNexoraApiV1DeliveryReleaseReliabilityReliabilityIdHistoryGet(reliability_id: string) {
    return this.request("GET", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/history`);
  }

  releaseReportNexoraApiV1CustomerSuccessReleaseReportGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/release-report`);
  }

  removeOrganizationMemberNexoraApiV1OrganizationsOrganizationIdMembersMemberIdDelete(organization_id: string, member_id: string) {
    return this.request("DELETE", `/nexora-api/v1/organizations/${organization_id}/members/${member_id}`);
  }

  renderPromptNexoraApiV1AiPromptsKeyRenderPost(key: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/prompts/${key}/render`, { body: opts.body });
  }

  renderScreenshotNexoraApiV1CustomerSuccessScreenshotRenderGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-render`, { params: opts.params });
  }

  repairDocsImageRenderingNexoraApiV1DocsImageRenderingRepairPost() {
    return this.request("POST", `/nexora-api/v1/docs/image-rendering/repair`);
  }

  replaceGroupNexoraApiV1ScimV2GroupsScimIdPut(scim_id: string) {
    return this.request("PUT", `/nexora-api/v1/scim/v2/Groups/${scim_id}`);
  }

  replaceUserNexoraApiV1ScimV2UsersScimIdPut(scim_id: string) {
    return this.request("PUT", `/nexora-api/v1/scim/v2/Users/${scim_id}`);
  }

  replayEventNexoraApiV1PlatformEventsEventIdReplayPost(event_id: string) {
    return this.request("POST", `/nexora-api/v1/platform/events/${event_id}/replay`);
  }

  replayEventsNexoraApiV1PlatformEventsReplayPost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/events/replay`, { params: opts.params });
  }

  replayScenarioNexoraApiV1DemoScenariosScenarioIdReplayPost(scenario_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/demo-scenarios/${scenario_id}/replay`, { body: opts.body });
  }

  reproductionPackageNexoraApiV1GaSupportReproductionPackageGet() {
    return this.request("GET", `/nexora-api/v1/ga/support/reproduction-package`);
  }

  requestCatalogNexoraApiV1PlatformEngineeringCatalogRequestsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/catalog/requests`, { body: opts.body });
  }

  requestCloseoutNexoraApiV1CustomerPilotCloseoutRequestPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-pilot/closeout/request`, { body: opts.body });
  }

  requestPromotionNexoraApiV1DeliveryReleaseReliabilityReliabilityIdRequestPromotionPost(reliability_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/request-promotion`, { params: opts.params });
  }

  requeueEventNexoraApiV1PlatformEventsEventIdRequeuePost(event_id: string) {
    return this.request("POST", `/nexora-api/v1/platform/events/${event_id}/requeue`);
  }

  requeueNotificationDeliveryNexoraApiV1PilotCommunicationsCommunicationIdDeliveriesDeliveryIdRequeuePost(communication_id: string, delivery_id: string) {
    return this.request("POST", `/nexora-api/v1/pilot/communications/${communication_id}/deliveries/${delivery_id}/requeue`);
  }

  resendInvitationNexoraApiV1InvitationsInvitationIdResendPost(invitation_id: string) {
    return this.request("POST", `/nexora-api/v1/invitations/${invitation_id}/resend`);
  }

  resetDemoOrganizationNexoraApiV1DemoOrganizationsOrganizationIdResetPost(organization_id: string) {
    return this.request("POST", `/nexora-api/v1/demo-organizations/${organization_id}/reset`);
  }

  resetScenarioNexoraApiV1DemoScenariosScenarioIdResetPost(scenario_id: string) {
    return this.request("POST", `/nexora-api/v1/demo-scenarios/${scenario_id}/reset`);
  }

  resolveConfigNexoraApiV1PlatformConfigGet() {
    return this.request("GET", `/nexora-api/v1/platform/config`);
  }

  resolveStageAgentsNexoraApiV1AiAgentsStagesWorkflowStageIdResolutionGet(workflow_stage_id: string) {
    return this.request("GET", `/nexora-api/v1/ai-agents/stages/${workflow_stage_id}/resolution`);
  }

  resourceTimelineNexoraApiV1ProductTimelineResourceTypeResourceIdGet(resource_type: string, resource_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/product/timeline/${resource_type}/${resource_id}`, { params: opts.params });
  }

  resourceTypesNexoraApiV1ScimV2ResourceTypesGet() {
    return this.request("GET", `/nexora-api/v1/scim/v2/ResourceTypes`);
  }

  restoreBackupNexoraApiV1GaBackupsBackupIdRestorePost(backup_id: string) {
    return this.request("POST", `/nexora-api/v1/ga/backups/${backup_id}/restore`);
  }

  resumeAgentNexoraApiV1AiAgentsRunIdResumePost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/ai/agents/${run_id}/resume`);
  }

  resumeExecutionNexoraApiV1PlatformExecutionsRunIdResumePost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/platform/executions/${run_id}/resume`);
  }

  resumeOrgNexoraApiV1BillingAdminOrgsOrgIdResumePost(org_id: string) {
    return this.request("POST", `/nexora-api/v1/billing/admin/orgs/${org_id}/resume`);
  }

  resumeRemediationActionNexoraApiV1RemediationActionsActionIdResumePost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/resume`, { body: opts.body });
  }

  resumeRolloutNexoraApiV1DeliveryReleaseReliabilityReliabilityIdResumePost(reliability_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/resume`);
  }

  retentionPurgeNexoraApiV1AuditRetentionPurgePost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/audit/retention/purge`, { params: opts.params });
  }

  retryExecutionNexoraApiV1PlatformExecutionsRunIdRetryPost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/platform/executions/${run_id}/retry`);
  }

  retryJobNexoraApiV1JobsJobIdRetryPost(job_id: string) {
    return this.request("POST", `/nexora-api/v1/jobs/${job_id}/retry`);
  }

  retryNotificationNexoraApiV1PlatformNotificationsMessageIdRetryPost(message_id: string) {
    return this.request("POST", `/nexora-api/v1/platform/notifications/${message_id}/retry`);
  }

  retryRemediationActionNexoraApiV1RemediationActionsActionIdRetryPost(action_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/remediation-actions/${action_id}/retry`, { body: opts.body });
  }

  revokeInvitationNexoraApiV1InvitationsInvitationIdDelete(invitation_id: string) {
    return this.request("DELETE", `/nexora-api/v1/invitations/${invitation_id}`);
  }

  revokeOrgKeyNexoraApiV1ApiKeysOrganizationKeyIdDelete(key_id: string) {
    return this.request("DELETE", `/nexora-api/v1/api-keys/organization/${key_id}`);
  }

  revokeOtherSessionsNexoraApiV1AuthSessionsRevokeOthersPost() {
    return this.request("POST", `/nexora-api/v1/auth/sessions/revoke-others`);
  }

  revokePersonalKeyNexoraApiV1ApiKeysPersonalKeyIdDelete(key_id: string) {
    return this.request("DELETE", `/nexora-api/v1/api-keys/personal/${key_id}`);
  }

  revokeScimTokenNexoraApiV1ScimV2AdminTokensTokenIdDelete(token_id: string) {
    return this.request("DELETE", `/nexora-api/v1/scim/v2/admin/tokens/${token_id}`);
  }

  revokeServiceAccountKeyNexoraApiV1ServiceAccountsSaIdKeysKeyIdDelete(sa_id: string, key_id: string) {
    return this.request("DELETE", `/nexora-api/v1/service-accounts/${sa_id}/keys/${key_id}`);
  }

  revokeSessionNexoraApiV1AuthSessionsJtiDelete(jti: string) {
    return this.request("DELETE", `/nexora-api/v1/auth/sessions/${jti}`);
  }

  revokeSessionNexoraApiV1SessionsSessionIdDelete(session_id: string) {
    return this.request("DELETE", `/nexora-api/v1/sessions/${session_id}`);
  }

  rewrittenGuideNexoraApiV1CustomerSuccessRewrittenGuidesKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/rewritten-guides/${key}`);
  }

  rewrittenGuidesNexoraApiV1CustomerSuccessRewrittenGuidesGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/rewritten-guides`);
  }

  rewrittenGuidesQualityNexoraApiV1CustomerSuccessRewrittenGuidesQualityGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/rewritten-guides/quality`);
  }

  rollbackDeploymentNexoraApiV1DeploymentsDeploymentIdRollbackPost(deployment_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/deployments/${deployment_id}/rollback`, { body: opts.body });
  }

  rollbackPromptNexoraApiV1AiPromptsKeyRollbackPost(key: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/prompts/${key}/rollback`, { body: opts.body });
  }

  rollbackReleaseNexoraApiV1DeliveryReleaseReliabilityReliabilityIdRollbackPost(reliability_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/rollback`, { params: opts.params });
  }

  rotateOrgKeyNexoraApiV1ApiKeysOrganizationKeyIdRotatePost(key_id: string) {
    return this.request("POST", `/nexora-api/v1/api-keys/organization/${key_id}/rotate`);
  }

  rotatePersonalKeyNexoraApiV1ApiKeysPersonalKeyIdRotatePost(key_id: string) {
    return this.request("POST", `/nexora-api/v1/api-keys/personal/${key_id}/rotate`);
  }

  rotateSecretNexoraApiV1PlatformEngineeringSecretsRefIdRotatePost(ref_id: string) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/secrets/${ref_id}/rotate`);
  }

  runAgentNexoraApiV1AiAgentsRunIdRunPost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/ai/agents/${run_id}/run`);
  }

  runApprovalWorkflowAgentNexoraApiV1AgentsApprovalRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/approval/run`, { body: opts.body });
  }

  runAssessmentNexoraApiV1PilotAssessmentRunPost() {
    return this.request("POST", `/nexora-api/v1/pilot/assessment/run`);
  }

  runBackendArchitectAgentNexoraApiV1AgentsBackendArchitectRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/backend-architect/run`, { body: opts.body });
  }

  runBackendCodeReviewAgentNexoraApiV1AgentsBackendCodeReviewRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/backend-code-review/run`, { body: opts.body });
  }

  runBackendExecutionAgentNexoraApiV1AgentsBackendExecutionRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/backend-execution/run`, { body: opts.body });
  }

  runBackendV1AgentNexoraApiV1AgentsBackendV1RunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/backend-v1/run`, { body: opts.body });
  }

  runBackendV2AgentNexoraApiV1AgentsBackendV2RunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/backend-v2/run`, { body: opts.body });
  }

  runBackendV3AgentNexoraApiV1AgentsBackendV3RunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/backend-v3/run`, { body: opts.body });
  }

  runBusinessAnalystAgentNexoraApiV1AgentsBusinessAnalystRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/business-analyst/run`, { body: opts.body });
  }

  runCicdAgentNexoraApiV1AgentsCicdRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/cicd/run`, { body: opts.body });
  }

  runComplianceNexoraApiV1PlatformEngineeringComplianceScanPost() {
    return this.request("POST", `/nexora-api/v1/platform-engineering/compliance/scan`);
  }

  runDeploymentAgentNexoraApiV1AgentsDeploymentRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/deployment/run`, { body: opts.body });
  }

  runDockerAgentNexoraApiV1AgentsDockerAgentRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/docker-agent/run`, { body: opts.body });
  }

  runDueReportSchedulesNexoraApiV1ProductReportsSchedulesRunDuePost() {
    return this.request("POST", `/nexora-api/v1/product/reports/schedules/run-due`);
  }

  runEscalationNexoraApiV1IncidentsEscalationRunPost() {
    return this.request("POST", `/nexora-api/v1/incidents/escalation/run`);
  }

  runEscalationsNexoraApiV1OncallEscalationsRunPost() {
    return this.request("POST", `/nexora-api/v1/oncall/escalations/run`);
  }

  runFrontendArchitectAgentNexoraApiV1AgentsFrontendArchitectRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/frontend-architect/run`, { body: opts.body });
  }

  runFrontendCodeReviewAgentNexoraApiV1AgentsFrontendCodeReviewRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/frontend-code-review/run`, { body: opts.body });
  }

  runFrontendExecutionAgentNexoraApiV1AgentsFrontendExecutionRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/frontend-execution/run`, { body: opts.body });
  }

  runFrontendV1AgentNexoraApiV1AgentsFrontendV1RunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/frontend-v1/run`, { body: opts.body });
  }

  runFrontendV2AgentNexoraApiV1AgentsFrontendV2RunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/frontend-v2/run`, { body: opts.body });
  }

  runFrontendV3AgentNexoraApiV1AgentsFrontendV3RunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/frontend-v3/run`, { body: opts.body });
  }

  runFullstackAssemblyAgentNexoraApiV1AgentsFullstackAssemblyRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/fullstack-assembly/run`, { body: opts.body });
  }

  runInfrastructureArchitectAgentNexoraApiV1AgentsInfrastructureArchitectRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/infrastructure-architect/run`, { body: opts.body });
  }

  runInstallReadinessNexoraApiV1GaInstallReadinessPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ga/install/readiness`, { body: opts.body });
  }

  runIntegrationTestAgentNexoraApiV1AgentsIntegrationTestsRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/integration-tests/run`, { body: opts.body });
  }

  runKubernetesAgentNexoraApiV1AgentsKubernetesRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/kubernetes/run`, { body: opts.body });
  }

  runObservabilityAgentNexoraApiV1AgentsObservabilityRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/observability/run`, { body: opts.body });
  }

  runPerformanceTestAgentNexoraApiV1AgentsPerformanceTestsRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/performance-tests/run`, { body: opts.body });
  }

  runPredictionsNexoraApiV1SrePredictionsRunPost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/predictions/run`, { params: opts.params });
  }

  runProductOwnerAgentNexoraApiV1AgentsProductOwnerRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/product-owner/run`, { body: opts.body });
  }

  runQaApprovalAgentNexoraApiV1AgentsQaApprovalsRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/qa-approvals/run`, { body: opts.body });
  }

  runQaArchitectAgentNexoraApiV1AgentsQaArchitectRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/qa-architect/run`, { body: opts.body });
  }

  runScanNexoraApiV1SecurityScansPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/scans`, { body: opts.body });
  }

  runScenarioNexoraApiV1DemoScenariosScenarioIdRunPost(scenario_id: string) {
    return this.request("POST", `/nexora-api/v1/demo-scenarios/${scenario_id}/run`);
  }

  runSecurityScanNexoraApiV1DeliverySecurityScansPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/security/scans`, { body: opts.body });
  }

  runSecurityTestAgentNexoraApiV1AgentsSecurityTestsRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/security-tests/run`, { body: opts.body });
  }

  runSreApprovalAgentNexoraApiV1AgentsSreApprovalRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/sre-approval/run`, { body: opts.body });
  }

  runUiuxDesignerAgentNexoraApiV1AgentsUiuxRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/uiux/run`, { body: opts.body });
  }

  runUnitTestGeneratorAgentNexoraApiV1AgentsUnitTestsRunPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/agents/unit-tests/run`, { body: opts.body });
  }

  runVerificationNexoraApiV1CustomerSuccessVerifyPost() {
    return this.request("POST", `/nexora-api/v1/customer-success/verify`);
  }

  runWorkflowScheduleNowNexoraApiV1AiTeamWorkflowSchedulesScheduleIdRunNowPost(schedule_id: string) {
    return this.request("POST", `/nexora-api/v1/ai-team-workflow-schedules/${schedule_id}/run-now`);
  }

  savingsNexoraApiV1OperatorSavingsGet() {
    return this.request("GET", `/nexora-api/v1/operator/savings`);
  }

  sbomInventoryNexoraApiV1SecuritySbomGet() {
    return this.request("GET", `/nexora-api/v1/security/sbom`);
  }

  scanDriftNexoraApiV1PlatformEngineeringDriftScanPost() {
    return this.request("POST", `/nexora-api/v1/platform-engineering/drift/scan`);
  }

  scenarioLauncherNexoraApiV1SalesScenarioLauncherGet() {
    return this.request("GET", `/nexora-api/v1/sales/scenario-launcher`);
  }

  schemasNexoraApiV1ScimV2SchemasGet() {
    return this.request("GET", `/nexora-api/v1/scim/v2/Schemas`);
  }

  scimGetGroupNexoraApiV1ScimV2GroupsScimIdGet(scim_id: string) {
    return this.request("GET", `/nexora-api/v1/scim/v2/Groups/${scim_id}`);
  }

  scimGetUserNexoraApiV1ScimV2UsersScimIdGet(scim_id: string) {
    return this.request("GET", `/nexora-api/v1/scim/v2/Users/${scim_id}`);
  }

  screenshotAssetsNexoraApiV1CustomerSuccessScreenshotAssetsGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-assets`);
  }

  screenshotRealityEnsureNexoraApiV1CustomerSuccessScreenshotRealityEnsurePost() {
    return this.request("POST", `/nexora-api/v1/customer-success/screenshot-reality/ensure`);
  }

  screenshotRealityNexoraApiV1CustomerSuccessScreenshotRealityGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-reality`);
  }

  screenshotReleaseGateNexoraApiV1CustomerSuccessScreenshotRealityReleaseGateGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-reality/release-gate`);
  }

  screenshotValidationGuideNexoraApiV1CustomerSuccessScreenshotValidationGuidesGuideIdGet(guide_id: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-validation/guides/${guide_id}`);
  }

  screenshotValidationNexoraApiV1CustomerSuccessScreenshotValidationGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/screenshot-validation`);
  }

  searchAnalyticsNexoraApiV1PlatformSearchAnalyticsGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/search/analytics`, { params: opts.params });
  }

  searchAutocompleteNexoraApiV1PlatformSearchAutocompleteGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/platform/search/autocomplete`, { params: opts.params });
  }

  searchLogsNexoraApiV1ObservabilityLogsSearchPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/observability/logs/search`, { body: opts.body });
  }

  searchTracesNexoraApiV1ObservabilityTracesSearchPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/observability/traces/search`, { body: opts.body });
  }

  seedLibraryNexoraApiV1TestPlaybooksSeedLibraryPost() {
    return this.request("POST", `/nexora-api/v1/test-playbooks/seed-library`);
  }

  seedScenariosNexoraApiV1DemoScenariosSeedPost() {
    return this.request("POST", `/nexora-api/v1/demo-scenarios/seed`);
  }

  sendCommunicationNexoraApiV1PilotCommunicationsCommunicationIdSendPost(communication_id: string) {
    return this.request("POST", `/nexora-api/v1/pilot/communications/${communication_id}/send`);
  }

  sendNotificationNexoraApiV1PlatformNotificationsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/notifications`, { body: opts.body });
  }

  serviceDependenciesNexoraApiV1ServicesServiceIdDependenciesGet(service_id: string) {
    return this.request("GET", `/nexora-api/v1/services/${service_id}/dependencies`);
  }

  serviceHealthNexoraApiV1ServicesServiceIdHealthGet(service_id: string) {
    return this.request("GET", `/nexora-api/v1/services/${service_id}/health`);
  }

  serviceMapNexoraApiV1ObservabilityServiceMapGet() {
    return this.request("GET", `/nexora-api/v1/observability/service-map`);
  }

  serviceProviderConfigNexoraApiV1ScimV2ServiceProviderConfigGet() {
    return this.request("GET", `/nexora-api/v1/scim/v2/ServiceProviderConfig`);
  }

  setConfigNexoraApiV1PlatformConfigPut(opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/platform/config`, { body: opts.body });
  }

  setKillSwitchNexoraApiV1OpsKillSwitchNamePost(name: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/ops/kill-switch/${name}`, { params: opts.params });
  }

  setKillSwitchNexoraApiV1PilotSafetyKillSwitchPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/safety/kill-switch`, { body: opts.body });
  }

  setMaintenanceNexoraApiV1OpsMaintenancePost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/ops/maintenance`, { params: opts.params });
  }

  setPreferenceNexoraApiV1ProductPreferencesPut(opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/product/preferences`, { body: opts.body });
  }

  setQuotaOverrideNexoraApiV1BillingAdminOrgsOrgIdQuotaOverridesPost(org_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/admin/orgs/${org_id}/quota-overrides`, { body: opts.body });
  }

  setReleaseChannelNexoraApiV1GaReleaseChannelPut(opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ga/release/channel`, { body: opts.body });
  }

  setRolloutNexoraApiV1OpsRolloutFeaturePost(feature: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/ops/rollout/${feature}`, { params: opts.params });
  }

  setStateNexoraApiV1OncallIncidentsIncidentIdStatePost(incident_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/oncall/incidents/${incident_id}/state`, { body: opts.body });
  }

  simulateRecommendationNexoraApiV1OperatorRecommendationsRecommendationIdSimulatePost(recommendation_id: string) {
    return this.request("POST", `/nexora-api/v1/operator/recommendations/${recommendation_id}/simulate`);
  }

  sloCenterNexoraApiV1OpsWorkspaceSloGet() {
    return this.request("GET", `/nexora-api/v1/ops-workspace/slo`);
  }

  sloDashboardNexoraApiV1ObservabilitySloGet() {
    return this.request("GET", `/nexora-api/v1/observability/slo`);
  }

  snoozeConnectionExpiryNexoraApiV1IntegrationsConnectionsConnectionIdSnoozeExpiryPost(connection_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/integrations/connections/${connection_id}/snooze-expiry`, { body: opts.body });
  }

  snoozeInboxNexoraApiV1ProductInboxNoteIdSnoozePost(note_id: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/product/inbox/${note_id}/snooze`, { params: opts.params });
  }

  ssoLoginNexoraApiV1AuthSsoSlugLoginGet(slug: string) {
    return this.request("GET", `/nexora-api/v1/auth/sso/${slug}/login`);
  }

  ssoOidcCallbackNexoraApiV1AuthSsoSlugCallbackGet(slug: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/auth/sso/${slug}/callback`, { params: opts.params });
  }

  ssoSamlAcsNexoraApiV1AuthSsoSlugAcsPost(slug: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/auth/sso/${slug}/acs`, { body: opts.body });
  }

  ssoSamlMetadataNexoraApiV1AuthSsoSlugMetadataGet(slug: string) {
    return this.request("GET", `/nexora-api/v1/auth/sso/${slug}/metadata`);
  }

  stagedRolloutNexoraApiV1GaReleaseRolloutFeaturePost(feature: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/ga/release/rollout/${feature}`, { params: opts.params });
  }

  startAgentNexoraApiV1AiAgentsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/agents`, { body: opts.body });
  }

  startCommanderNexoraApiV1SreCommanderStartPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sre/commander/start`, { body: opts.body });
  }

  startMajorIncidentNexoraApiV1IncidentsMajorPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/major`, { body: opts.body });
  }

  startOnboardingNexoraApiV1OnboardingStartPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/onboarding/start`, { body: opts.body });
  }

  startOnboardingPathNexoraApiV1PilotOnboardingPathsPathIdStartPost(path_id: string) {
    return this.request("POST", `/nexora-api/v1/pilot/onboarding-paths/${path_id}/start`);
  }

  startProvisionNexoraApiV1PlatformEngineeringProvisionsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform-engineering/provisions`, { body: opts.body });
  }

  startTourNexoraApiV1ProductToursStartPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product-tours/start`, { body: opts.body });
  }

  startupzStartupzGet() {
    return this.request("GET", `/startupz`);
  }

  storeCredentialsNexoraApiV1OnboardingIntegrationsSessionsSessionIdCredentialsPost(session_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/credentials`, { body: opts.body });
  }

  streamNexoraApiV1AiStreamPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/stream`, { body: opts.body });
  }

  stripeWebhookNexoraApiV1BillingWebhooksStripePost() {
    return this.request("POST", `/nexora-api/v1/billing/webhooks/stripe`);
  }

  submitChangeRequestNexoraApiV1ChangeRequestsRunIdSubmitPost(run_id: string) {
    return this.request("POST", `/nexora-api/v1/change-requests/${run_id}/submit`);
  }

  submitExecutionNexoraApiV1PlatformExecutionsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/executions`, { body: opts.body });
  }

  submitRequirementNexoraApiV1RequirementsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/requirements`, { body: opts.body });
  }

  successPlaybookNexoraApiV1CustomerSuccessSuccessPlaybooksKeyGet(key: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/success-playbooks/${key}`);
  }

  successPlaybooksNexoraApiV1CustomerSuccessSuccessPlaybooksGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/success-playbooks`);
  }

  suggestedQuestionsNexoraApiV1CopilotSuggestedQuestionsGet() {
    return this.request("GET", `/nexora-api/v1/copilot/suggested-questions`);
  }

  supportBundleNexoraApiV1OpsSupportBundleGet() {
    return this.request("GET", `/nexora-api/v1/ops/support-bundle`);
  }

  suspendOrgNexoraApiV1BillingAdminOrgsOrgIdSuspendPost(org_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/admin/orgs/${org_id}/suspend`, { body: opts.body });
  }

  switchOrganizationNexoraApiV1OrganizationsOrganizationIdSwitchPost(organization_id: string) {
    return this.request("POST", `/nexora-api/v1/organizations/${organization_id}/switch`);
  }

  syncArtifactsNexoraApiV1DeliveryArtifactsSyncPost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/artifacts/sync`, { params: opts.params });
  }

  syncCloudAccountNexoraApiV1ControlPlaneCloudAccountsAccountIdSyncPost(account_id: string) {
    return this.request("POST", `/nexora-api/v1/control-plane/cloud-accounts/${account_id}/sync`);
  }

  syncDiscoveryNexoraApiV1DiscoverySyncPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/discovery/sync`, { body: opts.body });
  }

  syncGitopsNexoraApiV1DeliveryGitopsSyncPost(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("POST", `/nexora-api/v1/delivery/gitops/sync`, { params: opts.params });
  }

  syncIntegrationConnectionNexoraApiV1IntegrationsConnectionsConnectionIdSyncPost(connection_id: string) {
    return this.request("POST", `/nexora-api/v1/integrations/connections/${connection_id}/sync`);
  }

  syncMcpServerNexoraApiV1AiMcpServersServerIdSyncPost(server_id: string) {
    return this.request("POST", `/nexora-api/v1/ai/mcp/servers/${server_id}/sync`);
  }

  syncPipelineRunsNexoraApiV1DeliveryPipelinesPipelineIdRunsSyncPost(pipeline_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/pipelines/${pipeline_id}/runs/sync`);
  }

  syncPipelinesNexoraApiV1DeliveryRepositoriesRepositoryIdPipelinesSyncPost(repository_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/repositories/${repository_id}/pipelines/sync`);
  }

  syncRepositoriesNexoraApiV1DeliverySourceConnectionsConnectionIdSyncPost(connection_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/source-connections/${connection_id}/sync`);
  }

  testIntegrationNotificationNexoraApiV1IntegrationsNotificationsTestPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/integrations/notifications/test`, { body: opts.body });
  }

  toggleFavoriteNexoraApiV1ProductPreferencesFavoritesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/preferences/favorites`, { body: opts.body });
  }

  topMetricsNexoraApiV1ObservabilityMetricsTopGet() {
    return this.request("GET", `/nexora-api/v1/observability/metrics/top`);
  }

  tourStateNexoraApiV1CustomerSuccessToursKeyStatePost(key: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/tours/${key}/state`, { body: opts.body });
  }

  toursForModuleNexoraApiV1CustomerSuccessToursByModuleModuleGet(module: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/tours/by-module/${module}`);
  }

  trackAnalyticsNexoraApiV1ProductAnalyticsTrackPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/analytics/track`, { body: opts.body });
  }

  trackRecentNexoraApiV1ProductPreferencesRecentPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/product/preferences/recent`, { body: opts.body });
  }

  transitionFindingNexoraApiV1SecurityFindingsFindingIdTransitionPost(finding_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/security/findings/${finding_id}/transition`, { body: opts.body });
  }

  transitionIncidentNexoraApiV1IncidentsInvestigationIdTransitionPost(investigation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/incidents/${investigation_id}/transition`, { body: opts.body });
  }

  ttvDashboardNexoraApiV1CustomerSuccessTimeToValueGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/time-to-value`, { params: opts.params });
  }

  ttvExperienceNexoraApiV1CustomerSuccessTimeToValueExperiencesKeyGet(key: string, opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/time-to-value/experiences/${key}`, { params: opts.params });
  }

  ttvExperienceProgressNexoraApiV1CustomerSuccessTimeToValueExperiencesKeyProgressPost(key: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/time-to-value/experiences/${key}/progress`, { body: opts.body });
  }

  ttvExperiencesNexoraApiV1CustomerSuccessTimeToValueExperiencesGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/time-to-value/experiences`, { params: opts.params });
  }

  ttvProgressNexoraApiV1CustomerSuccessTimeToValueProgressPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/customer-success/time-to-value/progress`, { body: opts.body });
  }

  unassignAgentNexoraApiV1AiAgentsAgentIdAssignmentsAssignmentIdDelete(agent_id: string, assignment_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-agents/${agent_id}/assignments/${assignment_id}`);
  }

  unassignAiTeamAgentToolNexoraApiV1AiTeamAgentsAgentIdToolsToolIdDelete(agent_id: string, tool_id: string) {
    return this.request("DELETE", `/nexora-api/v1/ai-team-agents/${agent_id}/tools/${tool_id}`);
  }

  unassignTeamNexoraApiV1StagesStageIdTeamsTeamIdDelete(stage_id: string, team_id: string) {
    return this.request("DELETE", `/nexora-api/v1/stages/${stage_id}/teams/${team_id}`);
  }

  unifiedInventoryNexoraApiV1ControlPlaneInventoryGet() {
    return this.request("GET", `/nexora-api/v1/control-plane/inventory`);
  }

  unifiedSearchNexoraApiV1OpsWorkspaceSearchGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/ops-workspace/search`, { params: opts.params });
  }

  uninstallPluginNexoraApiV1PlatformPluginsSlugDelete(slug: string) {
    return this.request("DELETE", `/nexora-api/v1/platform/plugins/${slug}`);
  }

  updateAgentInputNexoraApiV1AiAgentInputsInputIdPut(input_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-agent-inputs/${input_id}`, { body: opts.body });
  }

  updateAgentOutputNexoraApiV1AiAgentOutputsOutputIdPut(output_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-agent-outputs/${output_id}`, { body: opts.body });
  }

  updateAgentResponsibilityNexoraApiV1AiAgentResponsibilitiesResponsibilityIdPut(responsibility_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-agent-responsibilities/${responsibility_id}`, { body: opts.body });
  }

  updateAiAgentNexoraApiV1AiAgentsAgentIdPut(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-agents/${agent_id}`, { body: opts.body });
  }

  updateAiTeamAgentMemoryNexoraApiV1AiTeamAgentsMemoryMemoryIdPut(memory_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-team-agents/memory/${memory_id}`, { body: opts.body });
  }

  updateAiTeamAgentNexoraApiV1AiTeamAgentsAgentIdPut(agent_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-team-agents/${agent_id}`, { body: opts.body });
  }

  updateAiTeamNexoraApiV1AiTeamsTeamIdPut(team_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-teams/${team_id}`, { body: opts.body });
  }

  updateAiTeamWorkflowNexoraApiV1AiTeamWorkflowsWorkflowIdPut(workflow_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-team-workflows/${workflow_id}`, { body: opts.body });
  }

  updateAiToolNexoraApiV1AiToolsToolIdPut(tool_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-tools/${tool_id}`, { body: opts.body });
  }

  updateArticleNexoraApiV1DocsArticlesArticleIdPut(article_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/docs/articles/${article_id}`, { body: opts.body });
  }

  updateConnectionCredentialsNexoraApiV1IntegrationsConnectionsConnectionIdCredentialsPut(connection_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/integrations/connections/${connection_id}/credentials`, { body: opts.body });
  }

  updateConnectionNexoraApiV1AuthSsoConnectionsConnectionIdPatch(connection_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/auth/sso/connections/${connection_id}`, { body: opts.body });
  }

  updateContactsNexoraApiV1PilotContactsPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/contacts`, { body: opts.body });
  }

  updateCredentialNexoraApiV1CredentialsCredentialIdPut(credential_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/credentials/${credential_id}`, { body: opts.body });
  }

  updateDashboardWidgetsNexoraApiV1ProductDashboardsDashIdWidgetsPut(dash_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/product/dashboards/${dash_id}/widgets`, { body: opts.body });
  }

  updateEnvironmentNexoraApiV1OnboardingIntegrationsSessionsSessionIdEnvironmentPut(session_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/environment`, { body: opts.body });
  }

  updateIncidentTaskNexoraApiV1IncidentsInvestigationIdTasksTaskIdPatch(investigation_id: string, task_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/incidents/${investigation_id}/tasks/${task_id}`, { body: opts.body });
  }

  updateNotificationPreferencesNexoraApiV1CustomerPilotNotificationPreferencesPut(opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/customer-pilot/notification-preferences`, { body: opts.body });
  }

  updateOnboardingStepNexoraApiV1OnboardingSessionIdStepPost(session_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/onboarding/${session_id}/step`, { body: opts.body });
  }

  updateOrganizationNexoraApiV1OrganizationsOrganizationIdPut(organization_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/organizations/${organization_id}`, { body: opts.body });
  }

  updatePlanNexoraApiV1BillingAdminPlansPlanIdPatch(plan_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/billing/admin/plans/${plan_id}`, { body: opts.body });
  }

  updatePlaybookNexoraApiV1TestPlaybooksPlaybookIdPut(playbook_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/test-playbooks/${playbook_id}`, { body: opts.body });
  }

  updatePostmortemNexoraApiV1PostmortemsPostmortemIdPatch(postmortem_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/postmortems/${postmortem_id}`, { body: opts.body });
  }

  updateProjectNexoraApiV1ProjectsProjectIdPatch(project_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/projects/${project_id}`, { body: opts.body });
  }

  updateRequirementNexoraApiV1RequirementsRequirementIdPatch(requirement_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/requirements/${requirement_id}`, { body: opts.body });
  }

  updateResponsibilityNexoraApiV1ResponsibilitiesResponsibilityIdPut(responsibility_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/responsibilities/${responsibility_id}`, { body: opts.body });
  }

  updateRoutingNexoraApiV1AiRoutingPut(opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai/routing`, { body: opts.body });
  }

  updateRunbookNexoraApiV1RunbooksRunbookIdPut(runbook_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/runbooks/${runbook_id}`, { body: opts.body });
  }

  updateSecurityPolicyNexoraApiV1SecurityPolicyPut(opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/security-policy`, { body: opts.body });
  }

  updateServiceAccountNexoraApiV1ServiceAccountsSaIdPatch(sa_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/service-accounts/${sa_id}`, { body: opts.body });
  }

  updateServiceNexoraApiV1ServicesServiceIdPatch(service_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/services/${service_id}`, { body: opts.body });
  }

  updateServiceOwnerNexoraApiV1OncallServiceOwnersOwnerIdPatch(owner_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/oncall/service-owners/${owner_id}`, { body: opts.body });
  }

  updateStageNexoraApiV1StagesStageIdPut(stage_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/stages/${stage_id}`, { body: opts.body });
  }

  updateTeamNexoraApiV1TeamsTeamIdPut(team_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/teams/${team_id}`, { body: opts.body });
  }

  updateVariableNexoraApiV1OrgConfigVariablesVariableIdPut(variable_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/org-config/variables/${variable_id}`, { body: opts.body });
  }

  updateWorkflowNexoraApiV1WorkflowsWorkflowIdPut(workflow_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/workflows/${workflow_id}`, { body: opts.body });
  }

  updateWorkflowScheduleNexoraApiV1AiTeamWorkflowSchedulesScheduleIdPut(schedule_id: string, opts: { body?: unknown } = {}) {
    return this.request("PUT", `/nexora-api/v1/ai-team-workflow-schedules/${schedule_id}`, { body: opts.body });
  }

  updateWorkspaceNexoraApiV1WorkspacesWorkspaceIdPatch(workspace_id: string, opts: { body?: unknown } = {}) {
    return this.request("PATCH", `/nexora-api/v1/workspaces/${workspace_id}`, { body: opts.body });
  }

  upgradePostVerifyNexoraApiV1GaUpgradePostVerifyGet() {
    return this.request("GET", `/nexora-api/v1/ga/upgrade/post-verify`);
  }

  upgradePreCheckNexoraApiV1GaUpgradePreCheckGet() {
    return this.request("GET", `/nexora-api/v1/ga/upgrade/pre-check`);
  }

  uploadAiTeamDocumentNexoraApiV1AiTeamsTeamIdDocumentsPost(team_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai-teams/${team_id}/documents`, { body: opts.body });
  }

  upsertNotificationTemplateNexoraApiV1PlatformNotificationsTemplatesPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/platform/notifications/templates`, { body: opts.body });
  }

  usageDashboardNexoraApiV1BillingUsageGet() {
    return this.request("GET", `/nexora-api/v1/billing/usage`);
  }

  validateConnectionNexoraApiV1IntegrationsConnectionsConnectionIdValidatePost(connection_id: string) {
    return this.request("POST", `/nexora-api/v1/integrations/connections/${connection_id}/validate`);
  }

  validateCredentialForDeployNexoraApiV1CredentialsCredentialIdValidatePost(credential_id: string) {
    return this.request("POST", `/nexora-api/v1/credentials/${credential_id}/validate`);
  }

  validateLicenseNexoraApiV1BillingLicensesValidatePost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/billing/licenses/validate`, { body: opts.body });
  }

  validateProviderNexoraApiV1SecurityProvidersProviderIdValidatePost(provider_id: string) {
    return this.request("POST", `/nexora-api/v1/security/providers/${provider_id}/validate`);
  }

  validateSessionNexoraApiV1OnboardingIntegrationsSessionsSessionIdValidatePost(session_id: string) {
    return this.request("POST", `/nexora-api/v1/onboarding/integrations/sessions/${session_id}/validate`);
  }

  valuePropositionNexoraApiV1SalesValuePropositionPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/sales/value-proposition`, { body: opts.body });
  }

  verificationAuditNexoraApiV1CustomerSuccessVerificationAuditGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/verification-audit`);
  }

  verificationDashboardNexoraApiV1CustomerSuccessVerificationDashboardGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/verification-dashboard`);
  }

  verificationSummaryNexoraApiV1CustomerSuccessVerificationSummaryGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/verification-summary`);
  }

  verifyAiToolConnectionNexoraApiV1AiToolsToolIdVerifyPost(tool_id: string) {
    return this.request("POST", `/nexora-api/v1/ai-tools/${tool_id}/verify`);
  }

  verifyBackupNexoraApiV1GaBackupsBackupIdVerifyPost(backup_id: string) {
    return this.request("POST", `/nexora-api/v1/ga/backups/${backup_id}/verify`);
  }

  verifyCredentialNexoraApiV1CredentialsCredentialIdVerifyPost(credential_id: string) {
    return this.request("POST", `/nexora-api/v1/credentials/${credential_id}/verify`);
  }

  verifyIntegrationNexoraApiV1IntegrationsVerifyPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/integrations/verify`, { body: opts.body });
  }

  verifyLiveOperationNexoraApiV1PilotLiveOperationsOperationIdVerifyPost(operation_id: string, opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/pilot/live-operations/${operation_id}/verify`, { body: opts.body });
  }

  verifyNexoraApiV1AuditVerifyGet() {
    return this.request("GET", `/nexora-api/v1/audit/verify`);
  }

  verifyReleaseNexoraApiV1DeliveryReleaseReliabilityReliabilityIdVerifyPost(reliability_id: string) {
    return this.request("POST", `/nexora-api/v1/delivery/release-reliability/${reliability_id}/verify`);
  }

  videoLibraryNexoraApiV1CustomerSuccessVideosGet(opts: { params?: Record<string, unknown> } = {}) {
    return this.request("GET", `/nexora-api/v1/customer-success/videos`, { params: opts.params });
  }

  videosForModuleNexoraApiV1CustomerSuccessVideosByModuleModuleGet(module: string) {
    return this.request("GET", `/nexora-api/v1/customer-success/videos/by-module/${module}`);
  }

  visualCoverageNexoraApiV1CustomerSuccessVisualCoverageGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/visual-coverage`);
  }

  visualReadinessNexoraApiV1CustomerSuccessVisualReadinessGet() {
    return this.request("GET", `/nexora-api/v1/customer-success/visual-readiness`);
  }

  vulnerabilitiesNexoraApiV1SecurityVulnerabilitiesGet() {
    return this.request("GET", `/nexora-api/v1/security/vulnerabilities`);
  }

  whoamiNexoraApiV1IdentityWhoamiGet() {
    return this.request("GET", `/nexora-api/v1/identity/whoami`);
  }

  writeMemoryNexoraApiV1AiMemoryPost(opts: { body?: unknown } = {}) {
    return this.request("POST", `/nexora-api/v1/ai/memory`, { body: opts.body });
  }
}
