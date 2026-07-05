"""Sprint 47B - static catalogue of supported integrations.

Single source of truth for the marketplace. Each definition declares the
required secret fields (validated/encrypted by the 35A credential framework)
and the read-only capabilities granted on a verified connection.
"""

from app.models.integration import IntegrationCategory

# integration_key -> definition
INTEGRATION_DEFINITIONS: dict[str, dict] = {
    "AWS": {
        "name": "Amazon Web Services", "category": IntegrationCategory.CLOUD.value,
        "auth_type": "ACCESS_KEYS", "required_fields": ["access_key", "secret_key", "region"],
        "capabilities": ["Discover EC2/ECS/EKS", "Read CloudWatch metrics", "Read resource inventory"],
        "docs_url": "https://docs.aws.amazon.com/",
        "description": "Discover AWS infrastructure and read CloudWatch telemetry.",
    },
    "AZURE": {
        "name": "Microsoft Azure", "category": IntegrationCategory.CLOUD.value,
        "auth_type": "SERVICE_PRINCIPAL",
        "required_fields": ["subscription_id", "tenant_id", "client_id", "client_secret"],
        "capabilities": ["Discover resources", "Read Azure Monitor metrics", "Read container apps"],
        "docs_url": "https://learn.microsoft.com/azure/",
        "description": "Discover Azure resources and read Azure Monitor telemetry.",
    },
    "KUBERNETES": {
        "name": "Kubernetes", "category": IntegrationCategory.ORCHESTRATION.value,
        "auth_type": "KUBECONFIG", "required_fields": ["kubeconfig"],
        "capabilities": ["Discover workloads", "Read pod health", "Read deployments"],
        "docs_url": "https://kubernetes.io/docs/",
        "description": "Discover cluster workloads and read pod/deployment health.",
    },
    "GITHUB": {
        "name": "GitHub", "category": IntegrationCategory.SOURCE_CONTROL.value,
        "auth_type": "TOKEN", "required_fields": ["token"],
        "capabilities": ["Read repositories", "Read deployments", "Read commits"],
        "docs_url": "https://docs.github.com/",
        "description": "Read repositories, deployments and change history.",
    },
    "GITLAB": {
        "name": "GitLab", "category": IntegrationCategory.SOURCE_CONTROL.value,
        "auth_type": "TOKEN", "required_fields": ["token"],
        "capabilities": ["Read projects", "Read pipelines", "Read commits"],
        "docs_url": "https://docs.gitlab.com/",
        "description": "Read projects, pipelines and change history.",
    },
    "BITBUCKET": {
        "name": "Bitbucket", "category": IntegrationCategory.SOURCE_CONTROL.value,
        "auth_type": "APP_PASSWORD", "required_fields": ["username", "app_password"],
        "capabilities": ["Read repositories", "Read pipelines"],
        "docs_url": "https://support.atlassian.com/bitbucket-cloud/",
        "description": "Read repositories and pipeline history.",
    },
    "JIRA": {
        "name": "Jira", "category": IntegrationCategory.PROJECT.value,
        "auth_type": "API_TOKEN", "required_fields": ["base_url", "email", "api_token"],
        "capabilities": ["Read issues", "Read incidents", "Read projects"],
        "docs_url": "https://support.atlassian.com/jira-software-cloud/",
        "description": "Read issues, projects and linked incidents.",
    },
    "DATADOG": {
        "name": "Datadog", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "API_KEY", "required_fields": ["api_key", "app_key"],
        "capabilities": ["Read metrics", "Read monitors", "Read events"],
        "docs_url": "https://docs.datadoghq.com/",
        "description": "Read metrics, monitors and events.",
    },
    "PROMETHEUS": {
        "name": "Prometheus", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "ENDPOINT", "required_fields": ["endpoint"],
        "capabilities": ["Read metrics", "Read alert rules"],
        "docs_url": "https://prometheus.io/docs/",
        "description": "Read time-series metrics and alert rules.",
    },
    "GRAFANA": {
        "name": "Grafana", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "TOKEN", "required_fields": ["endpoint", "token"],
        "capabilities": ["Read dashboards", "Read alerts"],
        "docs_url": "https://grafana.com/docs/",
        "description": "Read dashboards and alert state.",
    },
    "NEW_RELIC": {
        "name": "New Relic", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "API_KEY", "required_fields": ["account_id", "api_key"],
        "capabilities": ["Read APM metrics", "Read alerts"],
        "docs_url": "https://docs.newrelic.com/",
        "description": "Read APM telemetry and alert policies.",
    },
    "PAGERDUTY": {
        "name": "PagerDuty", "category": IntegrationCategory.INCIDENT.value,
        "auth_type": "API_KEY", "required_fields": ["api_key"],
        "capabilities": ["Read incidents", "Read on-call schedules", "Read services"],
        "docs_url": "https://developer.pagerduty.com/",
        "description": "Read incidents, services and on-call schedules.",
    },
    "SLACK": {
        "name": "Slack", "category": IntegrationCategory.COMMUNICATION.value,
        "auth_type": "BOT_TOKEN", "required_fields": ["bot_token"],
        "capabilities": ["Read channels", "Verify notification delivery"],
        "docs_url": "https://api.slack.com/",
        "description": "Verify notification delivery and read channel metadata.",
    },
    "MICROSOFT_TEAMS": {
        # Sprint 58A.1 — Teams verification uses Microsoft Graph (app credentials),
        # not a fire-and-forget webhook, so connectivity/identity/scopes can be
        # genuinely confirmed against the tenant.
        "name": "Microsoft Teams", "category": IntegrationCategory.COMMUNICATION.value,
        "auth_type": "SERVICE_PRINCIPAL",
        "required_fields": ["tenant_id", "client_id", "client_secret"],
        "capabilities": ["Read organization", "Verify Graph access"],
        "docs_url": "https://learn.microsoft.com/graph/",
        "description": "Verify Microsoft Graph access and read tenant/organization metadata.",
    },
    "GCP": {
        "name": "Google Cloud Platform", "category": IntegrationCategory.CLOUD.value,
        "auth_type": "SERVICE_ACCOUNT",
        "required_fields": ["project_id", "service_account_json"],
        "capabilities": ["Discover GCE/GKE", "Read Cloud Monitoring", "Read asset inventory"],
        "docs_url": "https://cloud.google.com/docs",
        "description": "Discover GCP resources and read Cloud Monitoring telemetry.",
    },
    "CLOUDWATCH": {
        "name": "AWS CloudWatch", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "ACCESS_KEYS",
        "required_fields": ["access_key", "secret_key", "region"],
        "capabilities": ["Read metrics", "Read alarms", "Read log groups"],
        "docs_url": "https://docs.aws.amazon.com/cloudwatch/",
        "description": "Read CloudWatch metrics, alarms, and logs.",
    },
    "ARGOCD": {
        "name": "Argo CD", "category": IntegrationCategory.ORCHESTRATION.value,
        "auth_type": "TOKEN",
        "required_fields": ["endpoint", "token"],
        "capabilities": ["Read applications", "Read sync status", "Read GitOps health"],
        "docs_url": "https://argo-cd.readthedocs.io/",
        "description": "Read GitOps application state and deployment sync health.",
    },
    "TERRAFORM": {
        "name": "Terraform Cloud", "category": IntegrationCategory.CLOUD.value,
        "auth_type": "TOKEN",
        "required_fields": ["organization", "token"],
        "capabilities": ["Read workspaces", "Read runs", "Read state metadata"],
        "docs_url": "https://developer.hashicorp.com/terraform/cloud-docs",
        "description": "Read Terraform Cloud workspace and run metadata.",
    },
    "JENKINS": {
        "name": "Jenkins", "category": IntegrationCategory.PROJECT.value,
        "auth_type": "API_TOKEN",
        "required_fields": ["endpoint", "username", "api_token"],
        "capabilities": ["Read jobs", "Read builds", "Read pipeline status"],
        "docs_url": "https://www.jenkins.io/doc/",
        "description": "Read Jenkins jobs, builds, and pipeline status.",
    },
    "AZURE_DEVOPS": {
        "name": "Azure DevOps", "category": IntegrationCategory.PROJECT.value,
        "auth_type": "PAT",
        "required_fields": ["organization", "pat"],
        "capabilities": ["Read pipelines", "Read repos", "Read releases"],
        "docs_url": "https://learn.microsoft.com/azure/devops/",
        "description": "Read Azure DevOps pipelines, repos, and release history.",
    },
    "CIRCLECI": {
        "name": "CircleCI", "category": IntegrationCategory.PROJECT.value,
        "auth_type": "API_TOKEN",
        "required_fields": ["api_token"],
        "capabilities": ["Read projects", "Read pipelines", "Read workflows"],
        "docs_url": "https://circleci.com/docs/",
        "description": "Read CircleCI projects and pipeline workflows.",
    },
    "HASHICORP_VAULT": {
        "name": "HashiCorp Vault", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "TOKEN",
        "required_fields": ["endpoint", "token"],
        "capabilities": ["Verify seal status", "List secret engines (metadata)", "Read policies"],
        "docs_url": "https://developer.hashicorp.com/vault/docs",
        "description": "Verify Vault connectivity and read secret engine metadata.",
    },
    "LOKI": {
        "name": "Grafana Loki", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "ENDPOINT",
        "required_fields": ["endpoint"],
        "capabilities": ["Read log labels", "Query log streams"],
        "docs_url": "https://grafana.com/docs/loki/",
        "description": "Query log streams from Grafana Loki.",
    },
    "ELASTIC": {
        "name": "Elasticsearch", "category": IntegrationCategory.OBSERVABILITY.value,
        "auth_type": "API_KEY",
        "required_fields": ["endpoint", "api_key"],
        "capabilities": ["Read cluster health", "Search logs", "Read indices"],
        "docs_url": "https://www.elastic.co/guide/",
        "description": "Read Elasticsearch cluster health and search logs.",
    },
    "OPSGENIE": {
        "name": "Opsgenie", "category": IntegrationCategory.INCIDENT.value,
        "auth_type": "API_KEY",
        "required_fields": ["api_key"],
        "capabilities": ["Read alerts", "Read schedules", "Read teams"],
        "docs_url": "https://docs.opsgenie.com/",
        "description": "Read Opsgenie alerts, schedules, and on-call rotations.",
    },
    "SONARQUBE": {
        "name": "SonarQube", "category": IntegrationCategory.PROJECT.value,
        "auth_type": "TOKEN",
        "required_fields": ["endpoint", "token"],
        "capabilities": ["Read projects", "Read quality gates", "Read issues"],
        "docs_url": "https://docs.sonarqube.org/",
        "description": "Read SonarQube projects, quality gates, and issue summaries.",
    },
}

# Secret field names that must never be surfaced/logged (extends 35A set).
SENSITIVE_FIELDS = {
    "secret_key", "client_secret", "kubeconfig", "token", "app_password",
    "api_token", "api_key", "app_key", "bot_token", "webhook_url", "password",
    "service_account_json", "pat", "api_token",
}
