"""Shared enums for the DevOps delivery platform."""

from __future__ import annotations

import enum


class SourceProviderType(str, enum.Enum):
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    AZURE_DEVOPS = "AZURE_DEVOPS"
    BITBUCKET = "BITBUCKET"
    GITEA = "GITEA"


class PipelineProviderType(str, enum.Enum):
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    GITLAB_CI = "GITLAB_CI"
    AZURE_PIPELINES = "AZURE_PIPELINES"
    JENKINS = "JENKINS"
    CIRCLECI = "CIRCLECI"
    DRONE = "DRONE"
    ARGO_WORKFLOWS = "ARGO_WORKFLOWS"
    BITBUCKET_PIPELINES = "BITBUCKET_PIPELINES"


class ArtifactRegistryType(str, enum.Enum):
    DOCKER_HUB = "DOCKER_HUB"
    GHCR = "GHCR"
    ACR = "ACR"
    ECR = "ECR"
    GAR = "GAR"
    HARBOR = "HARBOR"


class EnvironmentTier(str, enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    QA = "QA"
    UAT = "UAT"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


DEFAULT_ENVIRONMENTS = [
    (EnvironmentTier.DEVELOPMENT, "development", 1),
    (EnvironmentTier.QA, "qa", 2),
    (EnvironmentTier.UAT, "uat", 3),
    (EnvironmentTier.STAGING, "staging", 4),
    (EnvironmentTier.PRODUCTION, "production", 5),
]


class DeploymentStrategy(str, enum.Enum):
    ROLLING = "ROLLING"
    RECREATE = "RECREATE"
    CANARY = "CANARY"
    BLUE_GREEN = "BLUE_GREEN"


class DeliveryStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class PipelineRunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReleaseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DEPLOYING = "DEPLOYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScanSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ScanTool(str, enum.Enum):
    TRIVY = "TRIVY"
    GRYPE = "GRYPE"
    SNYK = "SNYK"
    CODEQL = "CODEQL"
    OWASP = "OWASP"


class DeliveryOperationKind(str, enum.Enum):
    DEPLOY = "DEPLOY"
    PROMOTE = "PROMOTE"
    ROLLBACK = "ROLLBACK"
    CANARY_SHIFT = "CANARY_SHIFT"
    GITOPS_SYNC = "GITOPS_SYNC"
    GITOPS_ROLLBACK = "GITOPS_ROLLBACK"


APPROVAL_REQUIRED_OPS = frozenset({
    DeliveryOperationKind.DEPLOY,
    DeliveryOperationKind.PROMOTE,
    DeliveryOperationKind.ROLLBACK,
    DeliveryOperationKind.CANARY_SHIFT,
    DeliveryOperationKind.GITOPS_SYNC,
    DeliveryOperationKind.GITOPS_ROLLBACK,
})
