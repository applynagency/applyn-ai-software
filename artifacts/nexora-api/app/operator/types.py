"""Shared types for the AI Platform Operator (Sprint 64B)."""

from __future__ import annotations

import enum


class OperatorMode(str, enum.Enum):
    OBSERVATION = "OBSERVATION"
    RECOMMEND = "RECOMMEND"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FULLY_AUTOMATIC = "FULLY_AUTOMATIC"


class RecommendationKind(str, enum.Enum):
    SCALE_DEPLOYMENT = "SCALE_DEPLOYMENT"
    RESIZE_NODE_POOL = "RESIZE_NODE_POOL"
    UPGRADE_KUBERNETES = "UPGRADE_KUBERNETES"
    ROTATE_CERTIFICATE = "ROTATE_CERTIFICATE"
    ROTATE_SECRET = "ROTATE_SECRET"
    INCREASE_REPLICAS = "INCREASE_REPLICAS"
    REDUCE_REPLICAS = "REDUCE_REPLICAS"
    DELETE_UNUSED = "DELETE_UNUSED"
    MERGE_ALERTS = "MERGE_ALERTS"
    OPTIMIZE_TERRAFORM = "OPTIMIZE_TERRAFORM"
    IMPROVE_PIPELINE = "IMPROVE_PIPELINE"
    REDUCE_COST = "REDUCE_COST"
    RESTART_DEPLOYMENT = "RESTART_DEPLOYMENT"
    RUN_RUNBOOK = "RUN_RUNBOOK"


class RecommendationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ActionProposalStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TimelineEventKind(str, enum.Enum):
    ANALYSIS = "ANALYSIS"
    RECOMMENDATION = "RECOMMENDATION"
    SIMULATION = "SIMULATION"
    APPROVAL = "APPROVAL"
    EXECUTION = "EXECUTION"
    OUTCOME = "OUTCOME"
    ROLLBACK = "ROLLBACK"
    LEARNING = "LEARNING"


class GoalMetric(str, enum.Enum):
    COST_REDUCTION = "COST_REDUCTION"
    AVAILABILITY = "AVAILABILITY"
    CPU_UTILIZATION = "CPU_UTILIZATION"
    MTTR = "MTTR"
    DEPLOYMENT_SUCCESS = "DEPLOYMENT_SUCCESS"
    PIPELINE_SUCCESS = "PIPELINE_SUCCESS"
    IDLE_RESOURCES = "IDLE_RESOURCES"


DEFAULT_POLICIES = [
    {
        "name": "Production safety",
        "rules": {
            "never_restart_production_automatically": True,
            "allowed_environments": ["DEVELOPMENT", "QA", "STAGING"],
            "business_hours_only": False,
            "max_autonomous_cost_usd": 500,
        },
    },
]

DEFAULT_GOALS = [
    (GoalMetric.COST_REDUCTION, "Reduce cloud spend by 20%", 20.0, "%"),
    (GoalMetric.AVAILABILITY, "Keep availability above 99.95%", 99.95, "%"),
    (GoalMetric.CPU_UTILIZATION, "Maintain CPU below 70%", 70.0, "%"),
    (GoalMetric.MTTR, "Reduce MTTR", 30.0, "minutes"),
]
