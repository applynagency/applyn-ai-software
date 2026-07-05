"""Shared enums for the multi-cloud & Kubernetes control plane."""

from __future__ import annotations

import enum


class CloudProviderType(str, enum.Enum):
    AWS = "AWS"
    AZURE = "AZURE"
    GCP = "GCP"
    DIGITALOCEAN = "DIGITALOCEAN"
    ORACLE = "ORACLE"
    VMWARE = "VMWARE"


class ClusterDistribution(str, enum.Enum):
    AKS = "AKS"
    EKS = "EKS"
    GKE = "GKE"
    K3S = "K3S"
    RKE2 = "RKE2"
    OPENSHIFT = "OPENSHIFT"
    VANILLA = "VANILLA"


class ClusterHealth(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class OperationStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OperationKind(str, enum.Enum):
    # Kubernetes mutations (approval-gated)
    RESTART_DEPLOYMENT = "RESTART_DEPLOYMENT"
    SCALE_DEPLOYMENT = "SCALE_DEPLOYMENT"
    ROLLOUT_RESTART = "ROLLOUT_RESTART"
    ROLLBACK_DEPLOYMENT = "ROLLBACK_DEPLOYMENT"
    DELETE_POD = "DELETE_POD"
    RESTART_POD = "RESTART_POD"
    EVICT_POD = "EVICT_POD"
    CORDON_NODE = "CORDON_NODE"
    UNCORDON_NODE = "UNCORDON_NODE"
    DRAIN_NODE = "DRAIN_NODE"
    MAINTENANCE_NODE = "MAINTENANCE_NODE"
    PAUSE_ROLLOUT = "PAUSE_ROLLOUT"
    RESUME_ROLLOUT = "RESUME_ROLLOUT"
    UPDATE_IMAGE = "UPDATE_IMAGE"
    UPDATE_RESOURCES = "UPDATE_RESOURCES"
    CREATE_NAMESPACE = "CREATE_NAMESPACE"
    DELETE_NAMESPACE = "DELETE_NAMESPACE"
    EXPAND_PVC = "EXPAND_PVC"
    APPLY_NETWORK_POLICY = "APPLY_NETWORK_POLICY"
    HELM_UPGRADE = "HELM_UPGRADE"
    HELM_ROLLBACK = "HELM_ROLLBACK"


# Destructive operations require explicit human approval.
DESTRUCTIVE_OPERATIONS = frozenset({
    OperationKind.RESTART_DEPLOYMENT,
    OperationKind.SCALE_DEPLOYMENT,
    OperationKind.ROLLOUT_RESTART,
    OperationKind.ROLLBACK_DEPLOYMENT,
    OperationKind.DELETE_POD,
    OperationKind.RESTART_POD,
    OperationKind.EVICT_POD,
    OperationKind.CORDON_NODE,
    OperationKind.UNCORDON_NODE,
    OperationKind.DRAIN_NODE,
    OperationKind.MAINTENANCE_NODE,
    OperationKind.PAUSE_ROLLOUT,
    OperationKind.RESUME_ROLLOUT,
    OperationKind.UPDATE_IMAGE,
    OperationKind.UPDATE_RESOURCES,
    OperationKind.CREATE_NAMESPACE,
    OperationKind.DELETE_NAMESPACE,
    OperationKind.EXPAND_PVC,
    OperationKind.APPLY_NETWORK_POLICY,
    OperationKind.HELM_UPGRADE,
    OperationKind.HELM_ROLLBACK,
})

# Maps OperationKind → k8s write action name.
OPERATION_ACTION_MAP = {
    OperationKind.RESTART_DEPLOYMENT.value: "restart_deployment",
    OperationKind.SCALE_DEPLOYMENT.value: "scale_deployment",
    OperationKind.ROLLOUT_RESTART.value: "rollout_restart",
    OperationKind.ROLLBACK_DEPLOYMENT.value: "rollback_deployment",
    OperationKind.DELETE_POD.value: "delete_pod",
    OperationKind.RESTART_POD.value: "restart_pod",
    OperationKind.EVICT_POD.value: "evict_pod",
    OperationKind.CORDON_NODE.value: "cordon_node",
    OperationKind.UNCORDON_NODE.value: "uncordon_node",
    OperationKind.DRAIN_NODE.value: "drain_node",
    OperationKind.MAINTENANCE_NODE.value: "maintenance_node",
    OperationKind.PAUSE_ROLLOUT.value: "pause_rollout",
    OperationKind.RESUME_ROLLOUT.value: "resume_rollout",
    OperationKind.UPDATE_IMAGE.value: "update_image",
    OperationKind.UPDATE_RESOURCES.value: "update_resources",
    OperationKind.CREATE_NAMESPACE.value: "create_namespace",
    OperationKind.DELETE_NAMESPACE.value: "delete_namespace",
    OperationKind.EXPAND_PVC.value: "expand_pvc",
    OperationKind.APPLY_NETWORK_POLICY.value: "apply_network_policy",
}

# Event emitted per operation kind on successful execution.
OPERATION_EVENT_MAP = {
    OperationKind.RESTART_POD.value: "PodRestarted",
    OperationKind.DELETE_POD.value: "PodRestarted",
    OperationKind.SCALE_DEPLOYMENT.value: "DeploymentScaled",
    OperationKind.ROLLOUT_RESTART.value: "RolloutStarted",
    OperationKind.RESTART_DEPLOYMENT.value: "RolloutStarted",
    OperationKind.ROLLBACK_DEPLOYMENT.value: "RolloutCompleted",
    OperationKind.DRAIN_NODE.value: "NodeDrained",
    OperationKind.CORDON_NODE.value: "NodeDrained",
    OperationKind.CREATE_NAMESPACE.value: "NamespaceCreated",
    OperationKind.EXPAND_PVC.value: "PVCExpanded",
    OperationKind.APPLY_NETWORK_POLICY.value: "NetworkPolicyApplied",
}

# K8s resource kinds discovered live.
DISCOVERED_RESOURCE_KINDS = (
    "Namespace", "Deployment", "DaemonSet", "StatefulSet", "Pod", "Job", "CronJob",
    "ConfigMap", "Secret", "PersistentVolumeClaim", "StorageClass", "Ingress",
    "Service", "HorizontalPodAutoscaler", "NetworkPolicy", "Role", "RoleBinding",
    "ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition", "Event", "Node",
)
