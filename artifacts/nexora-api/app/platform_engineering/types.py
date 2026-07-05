"""Shared types for Platform Engineering (Sprint 64A)."""

from __future__ import annotations

import enum


class IaCProviderType(str, enum.Enum):
    TERRAFORM = "TERRAFORM"
    OPENTOFU = "OPENTOFU"
    PULUMI = "PULUMI"
    CLOUDFORMATION = "CLOUDFORMATION"
    BICEP = "BICEP"


class IaCRunKind(str, enum.Enum):
    VALIDATE = "VALIDATE"
    FMT = "FMT"
    PLAN = "PLAN"
    APPLY = "APPLY"
    DESTROY = "DESTROY"
    IMPORT = "IMPORT"
    REFRESH = "REFRESH"
    GRAPH = "GRAPH"


APPROVAL_REQUIRED_IAC = frozenset({
    IaCRunKind.APPLY,
    IaCRunKind.DESTROY,
    IaCRunKind.IMPORT,
})


class IaCRunStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PlatformTemplateKind(str, enum.Enum):
    AKS = "AKS"
    EKS = "EKS"
    GKE = "GKE"
    K3S = "K3S"
    OPENSHIFT = "OPENSHIFT"
    DEV_ENV = "DEV_ENV"
    QA_ENV = "QA_ENV"
    STAGING_ENV = "STAGING_ENV"
    PRODUCTION_ENV = "PRODUCTION_ENV"


class EnvironmentTier(str, enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    QA = "QA"
    STAGING = "STAGING"
    PERFORMANCE = "PERFORMANCE"
    PRODUCTION = "PRODUCTION"


class ProvisionStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROVISIONING = "PROVISIONING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"


class DriftSource(str, enum.Enum):
    TERRAFORM = "TERRAFORM"
    CLOUD = "CLOUD"
    KUBERNETES = "KUBERNETES"
    GITOPS = "GITOPS"
    CONFIGURATION = "CONFIGURATION"


class SecretBackendType(str, enum.Enum):
    VAULT = "VAULT"
    AWS_SECRETS_MANAGER = "AWS_SECRETS_MANAGER"
    AZURE_KEY_VAULT = "AZURE_KEY_VAULT"
    GCP_SECRET_MANAGER = "GCP_SECRET_MANAGER"
    KUBERNETES = "KUBERNETES"


class CatalogItemKind(str, enum.Enum):
    CLUSTER = "CLUSTER"
    DATABASE = "DATABASE"
    REDIS = "REDIS"
    STORAGE = "STORAGE"
    INGRESS = "INGRESS"
    DNS = "DNS"
    CERTIFICATE = "CERTIFICATE"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"
    OBJECT_STORAGE = "OBJECT_STORAGE"


class CatalogRequestStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROVISIONING = "PROVISIONING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GoldenTemplateKind(str, enum.Enum):
    MICROSERVICE = "MICROSERVICE"
    BACKEND_API = "BACKEND_API"
    FRONTEND = "FRONTEND"
    WORKER = "WORKER"
    CRON = "CRON"
    AI_SERVICE = "AI_SERVICE"
    BATCH_JOB = "BATCH_JOB"


DEFAULT_PLATFORM_TEMPLATES = [
    (PlatformTemplateKind.AKS, "Azure AKS Cluster", "AKS"),
    (PlatformTemplateKind.EKS, "AWS EKS Cluster", "EKS"),
    (PlatformTemplateKind.GKE, "Google GKE Cluster", "GKE"),
    (PlatformTemplateKind.K3S, "Lightweight K3s", "K3S"),
    (PlatformTemplateKind.OPENSHIFT, "OpenShift Cluster", "OPENSHIFT"),
    (PlatformTemplateKind.DEV_ENV, "Development Environment", "DEVELOPMENT"),
    (PlatformTemplateKind.QA_ENV, "QA Environment", "QA"),
    (PlatformTemplateKind.STAGING_ENV, "Staging Environment", "STAGING"),
    (PlatformTemplateKind.PRODUCTION_ENV, "Production Environment", "PRODUCTION"),
]

DEFAULT_CATALOG_ITEMS = [
    (CatalogItemKind.CLUSTER, "Kubernetes Cluster", "Managed K8s cluster"),
    (CatalogItemKind.DATABASE, "Managed Database", "PostgreSQL or MySQL"),
    (CatalogItemKind.REDIS, "Redis Cache", "Managed Redis instance"),
    (CatalogItemKind.STORAGE, "Block Storage", "Persistent volume storage"),
    (CatalogItemKind.INGRESS, "Ingress Controller", "NGINX or Traefik ingress"),
    (CatalogItemKind.DNS, "DNS Zone", "Managed DNS records"),
    (CatalogItemKind.CERTIFICATE, "TLS Certificate", "Managed certificate"),
    (CatalogItemKind.MESSAGE_QUEUE, "Message Queue", "Kafka or RabbitMQ"),
    (CatalogItemKind.OBJECT_STORAGE, "Object Storage", "S3-compatible bucket"),
]
