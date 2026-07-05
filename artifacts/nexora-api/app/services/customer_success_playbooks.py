"""Sprint 56D.4 - Integration Success Playbooks (enterprise-grade detail).

Per-integration enrichment that turns the base PLAYBOOKS into enterprise-grade
integration guides a new customer can follow without contacting support.

Provides, per integration key:
* business_value        - why it matters commercially
* use_cases             - concrete scenarios it unlocks
* configuration_steps   - step-by-step configuration (title, action, expected)
* expected_screens      - what the customer should see
* faq                   - >=10 frequently asked questions
* annotations           - callouts for the annotated screenshot
* architecture_mermaid  - a Mermaid architecture diagram

Pure data with no imports from ``customer_success_content`` (which imports this
module and applies it), so there is no circular import.

Tuples:
* config step : (title, action, expected_result)
* faq         : (question, answer)
* annotation  : (target, note)
"""

from __future__ import annotations

# The app route whose screenshot represents the integration settings UI.
PLAYBOOK_ROUTE = "/integrations"

BUSINESS_VALUE: dict[str, str] = {}
USE_CASES: dict[str, list[str]] = {}
CONFIG_STEPS: dict[str, list[tuple[str, str, str]]] = {}
EXPECTED_SCREENS: dict[str, list[str]] = {}
PLAYBOOK_FAQ: dict[str, list[tuple[str, str]]] = {}
ANNOTATIONS: dict[str, list[tuple[str, str]]] = {}
ARCH_MERMAID: dict[str, str] = {}

# --------------------------------------------------------------------------- AWS
BUSINESS_VALUE["aws"] = (
    "Connecting AWS gives Nexora a read-only view of your largest infrastructure "
    "footprint, unlocking automatic discovery, unified monitoring, and cost attribution "
    "so you cut cloud waste and detect issues without standing up new tooling."
)
USE_CASES["aws"] = [
    "Automatically inventory EC2, RDS, and related resources across regions.",
    "Stream CloudWatch alerts into the unified monitoring view.",
    "Attribute spend and surface savings opportunities in Cost Optimization.",
    "Forecast capacity exhaustion from historical CloudWatch utilization.",
]
CONFIG_STEPS["aws"] = [
    ("Create a read-only IAM role", "In the AWS console, create an IAM role (or user) and attach ReadOnlyAccess or a scoped read policy for EC2, RDS, CloudWatch, and Cost Explorer.", "The role/user exists with read-only permissions."),
    ("Select AWS in Nexora", "Open Integrations (or Onboarding -> Provider Selection) and choose AWS.", "The AWS credential form is shown."),
    ("Enter credentials", "Provide the role ARN (preferred) or access keys in Credential Validation.", "Fields accept the values without format errors."),
    ("Validate connectivity", "Click Validate to test the credentials read-only.", "A 'valid' connectivity status is returned."),
    ("Run discovery", "Trigger Discovery for AWS.", "Resources are enumerated and counted per service."),
    ("Confirm signals", "Open Monitoring and Cost Optimization.", "CloudWatch alerts and cost data appear."),
]
EXPECTED_SCREENS["aws"] = ["Provider selection grid", "AWS credential form", "Validation 'valid' badge", "Discovery summary with counts", "Cost Optimization with AWS spend"]
ANNOTATIONS["aws"] = [
    ("Role ARN field", "Paste the read-only IAM role ARN here - never long-lived root keys."),
    ("Validate button", "Runs a read-only connectivity test; credentials are discarded after validation."),
    ("Region scope", "Confirm the regions you expect; empty discovery usually means wrong region scope."),
]
ARCH_MERMAID["aws"] = (
    "graph LR\n"
    "  AWS[AWS Account] -->|read-only IAM| Collector[Nexora Collector]\n"
    "  Collector --> Discovery\n"
    "  Collector --> CloudWatch[CloudWatch Alerts]\n"
    "  Collector --> Cost[Cost Explorer]\n"
    "  Discovery --> Platform[Nexora Platform]\n"
    "  CloudWatch --> Platform\n"
    "  Cost --> Platform"
)
PLAYBOOK_FAQ["aws"] = [
    ("Does Nexora store my AWS credentials?", "No. Credentials are validated read-only during setup and are not persisted."),
    ("Should I use a role or access keys?", "Prefer an assumable IAM role; access keys work but are long-lived and less secure."),
    ("What permissions are required?", "ReadOnlyAccess, or scoped read for EC2, RDS, CloudWatch, and Cost Explorer."),
    ("Why is discovery returning nothing?", "The role likely lacks read permission or you scoped the wrong region; re-run after fixing."),
    ("Why is there no cost data?", "Cost Explorer read access is required; enable it and re-validate."),
    ("Can I connect multiple AWS accounts?", "Yes - add one integration per account, ideally with a role per environment."),
    ("Does Nexora change anything in my account?", "No - access is strictly read-only; it never modifies resources."),
    ("How often is data refreshed?", "Discovery and signals refresh on a regular polling cadence and on demand."),
    ("Which regions are scanned?", "The regions covered by the role's scope; confirm the region scope during setup."),
    ("Can I scope down permissions later?", "Yes - start with ReadOnlyAccess to validate, then tighten to the scoped policy."),
    ("Is CloudTrail required?", "No - core discovery and monitoring work without it, though it can enrich change context."),
]

# ------------------------------------------------------------------------- Azure
BUSINESS_VALUE["azure"] = (
    "Connecting Azure gives Nexora read-only visibility into your subscriptions so you "
    "get automatic resource discovery and Azure Monitor signals in one place, reducing "
    "mean-time-to-detect without per-team tooling."
)
USE_CASES["azure"] = [
    "Discover Azure resources across subscriptions and resource groups.",
    "Ingest Azure Monitor metrics into unified monitoring.",
    "Map service dependencies spanning Azure workloads.",
    "Track reliability posture for Azure-hosted services.",
]
CONFIG_STEPS["azure"] = [
    ("Register a service principal", "Register an app (service principal) in Microsoft Entra ID, or use a managed identity.", "The app/identity exists with a client ID."),
    ("Assign the Reader role", "Assign the Reader role at the subscription or resource-group scope.", "Reader is granted at the correct scope."),
    ("Select Azure in Nexora", "Open Integrations and choose Azure.", "The Azure credential form appears."),
    ("Enter tenant/client/subscription", "Provide tenant ID, client ID, secret, and subscription in Credential Validation.", "Fields accept the values."),
    ("Validate connectivity", "Click Validate.", "A 'valid' status is returned."),
    ("Run discovery", "Trigger Discovery for Azure.", "Azure resources are discovered and counted."),
]
EXPECTED_SCREENS["azure"] = ["Provider selection grid", "Azure credential form", "Validation 'valid' badge", "Discovery summary", "Monitoring with Azure signals"]
ANNOTATIONS["azure"] = [
    ("Tenant/Client fields", "Use the service principal's tenant and client IDs from Entra ID."),
    ("Reader scope", "Assign Reader at the smallest scope that covers your resources."),
    ("Client secret", "Rotate regularly; Nexora does not store the secret."),
]
ARCH_MERMAID["azure"] = (
    "graph LR\n"
    "  Azure[Azure Subscription] -->|Reader role| Collector[Nexora Collector]\n"
    "  Collector --> Discovery\n"
    "  Collector --> Monitor[Azure Monitor]\n"
    "  Discovery --> Platform[Nexora Platform]\n"
    "  Monitor --> Platform"
)
PLAYBOOK_FAQ["azure"] = [
    ("Does Nexora store my Azure secret?", "No - the client secret is validated read-only and not persisted."),
    ("What role does Nexora need?", "The built-in Reader role at the subscription or resource-group scope."),
    ("Can I use a managed identity?", "Yes - managed identities are preferred over client secrets where available."),
    ("Why does validation fail with AuthorizationFailed?", "The Reader role is missing or assigned at the wrong scope; assign it correctly."),
    ("Why is discovery empty?", "Check that Reader covers the subscription/resource groups you expect."),
    ("Can I connect multiple subscriptions?", "Yes - add an integration per subscription or scope a single principal across them."),
    ("Does Nexora modify Azure resources?", "No - access is read-only."),
    ("How do I rotate the secret?", "Generate a new client secret in Entra ID and re-validate the integration."),
    ("Are management groups supported?", "Assign Reader at a scope that includes the subscriptions you want covered."),
    ("Is Azure Monitor required?", "It is needed for Azure metric signals in monitoring; discovery works without it."),
]

# -------------------------------------------------------------------- Kubernetes
BUSINESS_VALUE["kubernetes"] = (
    "Connecting Kubernetes lets Nexora discover workloads and reflect real-time service "
    "health, so platform teams see deployment and reliability signals for every cluster "
    "without bolting on extra agents."
)
USE_CASES["kubernetes"] = [
    "Discover deployments, pods, and services across namespaces.",
    "Reflect workload health in Service Health.",
    "Correlate cluster events with incidents.",
    "Track per-service reliability for containerized workloads.",
]
CONFIG_STEPS["kubernetes"] = [
    ("Create a read-only ServiceAccount", "Create a ServiceAccount and bind a read-only ClusterRole (get/list/watch on core + apps).", "The ServiceAccount and binding exist."),
    ("Obtain a token/kubeconfig", "Generate a token or kubeconfig for the ServiceAccount.", "A read-only token is available."),
    ("Select Kubernetes in Nexora", "Open Integrations and choose Kubernetes.", "The Kubernetes credential form appears."),
    ("Provide credentials", "Paste the kubeconfig/token in Credential Validation.", "Fields accept the values."),
    ("Validate connectivity", "Click Validate.", "A 'valid' status is returned."),
    ("Run discovery", "Trigger Discovery.", "Workloads are discovered and health begins reporting."),
]
EXPECTED_SCREENS["kubernetes"] = ["Provider selection grid", "Kubernetes credential form", "Validation 'valid' badge", "Discovery summary with workloads", "Service Health reflecting workloads"]
ANNOTATIONS["kubernetes"] = [
    ("Kubeconfig/token field", "Paste a read-only ServiceAccount token - avoid cluster-admin."),
    ("API server reachability", "The collector must reach the API server; timeouts indicate network/firewall issues."),
    ("Namespace scope", "Scope RBAC to the namespaces you need."),
]
ARCH_MERMAID["kubernetes"] = (
    "graph LR\n"
    "  K8s[Kubernetes Cluster] -->|read-only RBAC| Collector[Nexora Collector]\n"
    "  Collector --> Discovery[Workload Discovery]\n"
    "  Collector --> Health[Health Watch]\n"
    "  Discovery --> Platform[Nexora Platform]\n"
    "  Health --> Platform"
)
PLAYBOOK_FAQ["kubernetes"] = [
    ("Does Nexora need cluster-admin?", "No - read-only RBAC (get/list/watch on core and apps) is sufficient."),
    ("Are tokens stored?", "Tokens are validated read-only and not stored."),
    ("Why do I get Forbidden errors?", "The read-only ClusterRole is not bound to the ServiceAccount; bind it and re-validate."),
    ("Why does validation time out?", "The collector cannot reach the API server; check network/firewall rules."),
    ("Can I scope to specific namespaces?", "Yes - restrict RBAC to the namespaces you want discovered."),
    ("Does Nexora deploy anything into my cluster?", "No - it reads via the API server; it does not install workloads."),
    ("Can I connect multiple clusters?", "Yes - add an integration per cluster."),
    ("How is workload health derived?", "From pod/deployment status and related signals via the read-only watch."),
    ("Is a specific Kubernetes version required?", "Any current, supported version exposing the standard API works."),
    ("How do I rotate the token?", "Issue a new ServiceAccount token and re-validate the integration."),
]

# ---------------------------------------------------------------------- GitHub
BUSINESS_VALUE["github"] = (
    "Connecting GitHub feeds change intelligence and change-failure prediction with real "
    "deployment and commit history, so you can tie incidents to the changes that caused "
    "them and ship with measured confidence."
)
USE_CASES["github"] = [
    "Correlate commits, releases, and deploys to incidents.",
    "Power change-failure prediction with real change history.",
    "Attribute incidents to the responsible change and author.",
    "Improve postmortems with precise change context.",
]
CONFIG_STEPS["github"] = [
    ("Choose app or token", "Install the Nexora GitHub App (preferred) or create a fine-grained, read-only PAT.", "An app installation or PAT exists."),
    ("Grant read access", "Grant read access to repository contents, commits, and deployments.", "The required read scopes are granted."),
    ("Select GitHub in Nexora", "Open Integrations and choose GitHub.", "The GitHub credential form appears."),
    ("Provide the token", "Paste the token (or complete the app install) in Credential Validation.", "Fields accept the value."),
    ("Validate connectivity", "Click Validate.", "A 'valid' status is returned."),
    ("Confirm change intelligence", "Open an incident and review Change Intelligence.", "Commits/releases appear correlated to the incident."),
]
EXPECTED_SCREENS["github"] = ["Provider selection grid", "GitHub credential form", "Validation 'valid' badge", "Incident Change Intelligence populated", "Change Failure Prediction using history"]
ANNOTATIONS["github"] = [
    ("Token field", "Use a fine-grained, read-only PAT or the GitHub App - never an admin token."),
    ("Org-level install", "Install at the org level for full coverage across repositories."),
    ("Rate limits", "Use a GitHub App for higher rate limits on large orgs."),
]
ARCH_MERMAID["github"] = (
    "graph LR\n"
    "  GH[GitHub Org] -->|read-only app/PAT| Collector[Nexora Collector]\n"
    "  Collector --> Changes[Change Intelligence]\n"
    "  Changes --> Prediction[Change Failure Prediction]\n"
    "  Changes --> Platform[Nexora Platform]"
)
PLAYBOOK_FAQ["github"] = [
    ("App or personal access token?", "Prefer the GitHub App for higher rate limits and org-wide coverage; a fine-grained read-only PAT also works."),
    ("What scopes are needed?", "Read access to repository contents, commits, and deployments."),
    ("Are tokens stored?", "Tokens are validated and used read-only for change ingestion; treat them as secrets."),
    ("Why is Change Intelligence empty?", "The app/token lacks access to the repository; grant access and re-validate."),
    ("Why am I rate limited?", "Personal tokens have lower limits; switch to a GitHub App."),
    ("Can I limit which repos are read?", "Yes - scope the app/token to only the repositories you need."),
    ("Does Nexora write to my repos?", "No - access is read-only; it never pushes or opens PRs."),
    ("Does this support GitHub Enterprise?", "Yes - provide the enterprise endpoint when configuring the integration."),
    ("How fresh is change data?", "Changes are ingested on a regular cadence and when incidents are investigated."),
    ("Can multiple orgs be connected?", "Yes - install or add a token per org."),
    ("Is webhooks setup required?", "No - polling covers change history; webhooks can reduce latency where available."),
]

# ---------------------------------------------------------------------- GitLab
BUSINESS_VALUE["gitlab"] = (
    "Connecting GitLab brings merge requests, commits, and pipeline outcomes into change "
    "intelligence, so incidents are tied to the exact changes and deployments that "
    "triggered them."
)
USE_CASES["gitlab"] = [
    "Correlate merge requests, commits, and pipelines to incidents.",
    "Feed change-failure prediction with pipeline outcomes.",
    "Attribute incidents to the responsible change.",
    "Enrich postmortems with deployment context.",
]
CONFIG_STEPS["gitlab"] = [
    ("Create a read-only token", "Create a group or project access token with read_api and read_repository scopes.", "A read-only token exists."),
    ("Select GitLab in Nexora", "Open Integrations and choose GitLab.", "The GitLab credential form appears."),
    ("Provide the token", "Paste the token in Credential Validation.", "Fields accept the value."),
    ("Validate connectivity", "Click Validate.", "A 'valid' status is returned."),
    ("Confirm change intelligence", "Open an incident and review Change Intelligence.", "MRs/commits/pipelines appear correlated."),
    ("Verify predictions", "Open Change Failure Prediction.", "Predictions use the ingested change history."),
]
EXPECTED_SCREENS["gitlab"] = ["Provider selection grid", "GitLab credential form", "Validation 'valid' badge", "Incident Change Intelligence populated", "Change Failure Prediction using history"]
ANNOTATIONS["gitlab"] = [
    ("Token field", "Use a read-only group/project token with read_api and read_repository."),
    ("Token expiry", "Set a sensible expiry and rotate before it lapses."),
    ("Group vs project", "Use a group token for multi-project coverage."),
]
ARCH_MERMAID["gitlab"] = (
    "graph LR\n"
    "  GL[GitLab Group] -->|read-only token| Collector[Nexora Collector]\n"
    "  Collector --> Changes[Change Intelligence]\n"
    "  Changes --> Prediction[Change Failure Prediction]\n"
    "  Changes --> Platform[Nexora Platform]"
)
PLAYBOOK_FAQ["gitlab"] = [
    ("What token scopes are required?", "read_api and read_repository."),
    ("Group token or project token?", "Use a group token for multi-project coverage; a project token works for one project."),
    ("Are tokens stored?", "Tokens are used read-only for change ingestion; treat them as secrets and set an expiry."),
    ("Why do I get 401 Unauthorized?", "The token is invalid or expired; recreate it with read scopes and re-validate."),
    ("Why do I get 403 on a project?", "The token lacks access to that project; add it to the group/project."),
    ("Does Nexora write to GitLab?", "No - access is read-only."),
    ("Is self-managed GitLab supported?", "Yes - provide your instance URL during configuration."),
    ("Can I connect multiple groups?", "Yes - add a token per group."),
    ("How fresh is the data?", "Change data is ingested regularly and during incident investigation."),
    ("Do pipelines need to be enabled?", "Pipelines enrich change-failure signals but commits/MRs alone still provide value."),
]

# ----------------------------------------------------------------------- Slack
BUSINESS_VALUE["slack"] = (
    "Connecting Slack delivers alerts and incident updates straight to the channels your "
    "responders already live in, cutting acknowledgement time and keeping everyone aligned "
    "during an incident."
)
USE_CASES["slack"] = [
    "Post alerts and incident updates to on-call channels.",
    "Route notifications by severity to different channels.",
    "Keep stakeholders informed without leaving Slack.",
    "Reduce time-to-acknowledge with in-channel pings.",
]
CONFIG_STEPS["slack"] = [
    ("Install a Slack app", "Create/install a Slack app in your workspace and add it to target channels.", "The app is installed and present in the channels."),
    ("Grant chat:write", "Ensure the app has the chat:write scope.", "The scope is granted."),
    ("Provide token/webhook", "Paste the bot token or webhook into the integration settings.", "Fields accept the value."),
    ("Choose channels", "Select the channels to receive notifications.", "Target channels are saved."),
    ("Send a test notification", "Trigger a test notification.", "The message arrives in the channel."),
]
EXPECTED_SCREENS["slack"] = ["Integration settings form", "Channel selector", "Test notification button", "Delivered message in Slack"]
ANNOTATIONS["slack"] = [
    ("Bot token field", "Paste the bot token; grant only chat:write."),
    ("Channel selector", "Pick specific channels - avoid broad, noisy channels."),
    ("Test button", "Use it to confirm delivery before relying on it."),
]
ARCH_MERMAID["slack"] = (
    "graph LR\n"
    "  Platform[Nexora Platform] -->|notify| Slack[Slack Workspace]\n"
    "  Slack --> Channel[On-call Channel]"
)
PLAYBOOK_FAQ["slack"] = [
    ("What permission does the app need?", "Only chat:write to the target channels."),
    ("Token or webhook?", "Either works; a bot token enables richer routing across channels."),
    ("Are tokens stored?", "Slack tokens are stored encrypted server-side because delivery happens asynchronously."),
    ("Why does nothing post?", "The app is not in the channel; invite it and resend the test."),
    ("Why do I get invalid_auth?", "The token is stale; reinstall the app and refresh the token."),
    ("Can I route by severity?", "Yes - map severities to different channels to reduce noise."),
    ("Can I limit which channels are used?", "Yes - select specific channels in the integration settings."),
    ("Does Nexora read my Slack messages?", "No - the integration only posts notifications."),
    ("Can multiple workspaces be connected?", "Yes - add an integration per workspace."),
    ("How do I stop notifications temporarily?", "Disable the integration or remove the app from the channel."),
]

# -------------------------------------------------------------- Microsoft Teams
BUSINESS_VALUE["microsoft-teams"] = (
    "Connecting Microsoft Teams delivers alerts and incident updates to your Teams "
    "channels via an incoming webhook, keeping Microsoft-centric organizations aligned "
    "during incidents without new tooling."
)
USE_CASES["microsoft-teams"] = [
    "Post alerts and incident updates to Teams channels.",
    "Notify responders where they already collaborate.",
    "Separate channels per severity or team.",
    "Keep leadership informed during major incidents.",
]
CONFIG_STEPS["microsoft-teams"] = [
    ("Add an incoming webhook", "Add an Incoming Webhook connector to the target Teams channel.", "The connector is added to the channel."),
    ("Copy the webhook URL", "Copy the generated webhook URL.", "You have the webhook URL."),
    ("Provide the URL", "Paste the webhook URL into the integration settings.", "Fields accept the value."),
    ("Send a test message", "Trigger a test message.", "The message appears in the Teams channel."),
    ("Confirm formatting", "Check the delivered card renders correctly.", "The card displays as expected."),
]
EXPECTED_SCREENS["microsoft-teams"] = ["Integration settings form", "Webhook URL field", "Test message button", "Delivered card in Teams"]
ANNOTATIONS["microsoft-teams"] = [
    ("Webhook URL field", "Paste the channel's incoming webhook URL; treat it as a secret."),
    ("Test button", "Confirm delivery and card formatting before relying on it."),
    ("Per-channel connector", "Each channel needs its own connector/webhook."),
]
ARCH_MERMAID["microsoft-teams"] = (
    "graph LR\n"
    "  Platform[Nexora Platform] -->|notify| Teams[MS Teams]\n"
    "  Teams --> Channel[Team Channel]"
)
PLAYBOOK_FAQ["microsoft-teams"] = [
    ("How does Teams delivery work?", "Through an Incoming Webhook connector added to the target channel."),
    ("Is the webhook URL a secret?", "Yes - anyone with the URL can post; store it securely and rotate if exposed."),
    ("Is the webhook stored?", "It is stored encrypted server-side because delivery is asynchronous."),
    ("Why do messages 404?", "The connector was removed or the URL changed; recreate it and update the URL."),
    ("Why is a message not delivered?", "Verify the channel still has the connector and the URL is current."),
    ("Can I use multiple channels?", "Yes - add a connector per channel and configure separate integrations."),
    ("Does Nexora read Teams messages?", "No - the integration only posts notifications."),
    ("Can I route by severity?", "Yes - use separate channels/webhooks per severity."),
    ("What if formatting breaks?", "Check the connector status; recreate the webhook if needed."),
    ("How do I disable it?", "Remove the connector or disable the integration in settings."),
]

# ------------------------------------------------------------------------- Jira
BUSINESS_VALUE["jira"] = (
    "Connecting Jira turns incidents and postmortem action items into tracked tickets in "
    "your existing workflow, so reliability follow-ups actually get done and nothing falls "
    "through the cracks."
)
USE_CASES["jira"] = [
    "Create Jira issues from incidents and action items.",
    "Track postmortem follow-ups to completion.",
    "Link incidents to existing tickets.",
    "Map severity to issue priority automatically.",
]
CONFIG_STEPS["jira"] = [
    ("Create a service account", "Create (or choose) a service account that can create issues in the target project.", "The account exists with create permission."),
    ("Generate an API token", "Create an API token for the service account.", "An API token is available."),
    ("Provide connection details", "Enter the site URL, account email, and API token in integration settings.", "Fields accept the values."),
    ("Select project and issue type", "Choose the default project and issue type.", "Defaults are saved."),
    ("Create a test issue", "Create a test issue from an action item.", "The issue appears in the Jira project."),
]
EXPECTED_SCREENS["jira"] = ["Integration settings form", "Project and issue-type selectors", "Create test issue button", "Created issue in Jira"]
ANNOTATIONS["jira"] = [
    ("API token field", "Use a dedicated service account's API token, not a personal one."),
    ("Project key", "Confirm the project key; 'project not found' means a wrong key or missing permission."),
    ("Issue type", "Pick a default issue type that matches your workflow."),
]
ARCH_MERMAID["jira"] = (
    "graph LR\n"
    "  Platform[Nexora Platform] -->|create issues| Jira[Jira Project]\n"
    "  Jira --> Tracking[Action Item Tracking]"
)
PLAYBOOK_FAQ["jira"] = [
    ("What permission does Nexora need?", "Create Issues in the target project - least privilege."),
    ("Should I use a service account?", "Yes - a dedicated service account is safer and clearer than a personal account."),
    ("Is the API token stored?", "It is stored encrypted server-side to create issues on your behalf."),
    ("Why do I get 401 Unauthorized?", "The API token is invalid or expired; regenerate it and re-enter credentials."),
    ("Why is the project not found?", "The project key is wrong or the account lacks access; verify both."),
    ("Can I map severity to priority?", "Yes - configure severity-to-priority mapping for created issues."),
    ("Does Nexora read all my Jira data?", "No - it creates issues and can link tickets; it does not bulk-read your project."),
    ("Is Jira Server/Data Center supported?", "Yes - provide your instance URL and a compatible token/credentials."),
    ("Can postmortem actions auto-create issues?", "Yes - action items can be turned into Jira issues automatically."),
    ("Can I change the default project later?", "Yes - update the default project and issue type in settings."),
]

# === APPEND BELOW ===
