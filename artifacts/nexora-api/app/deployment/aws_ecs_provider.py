"""Sprint 41C — AWS ECS remediation provider.

Real, approval-gated ECS remediation using the *customer's* AWS access keys
(resolved transiently from an encrypted deployment credential — never the
platform's). Read-only investigation for AWS already exists in
``tool_connectors``; this adds the two write operations needed for remediation:

* Rollback ECS deployment — point the service back at the previous task
  definition revision and force a new deployment.
* Restart ECS service — force a new deployment of the current task definition.

``boto3`` is imported lazily so importing this module never fails when boto3 is
absent. The session factory is injectable for testing without AWS.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _default_session(secret: dict):
    import boto3

    return boto3.session.Session(
        aws_access_key_id=secret["access_key"],
        aws_secret_access_key=secret["secret_key"],
        region_name=secret.get("region", "us-east-1"),
    )


class AWSEcsRemediationProvider:
    def __init__(self, session_factory: Callable[[dict], Any] | None = None) -> None:
        self._session_factory = session_factory or _default_session

    def _ecs(self, deployment_target: dict):
        if not deployment_target or not deployment_target.get("access_key"):
            raise ValueError("A customer AWS credential is required for remediation")
        return self._session_factory(deployment_target).client("ecs")

    def _split(self, deployment_target: dict) -> tuple[str, str]:
        cluster = (deployment_target or {}).get("cluster") or (deployment_target or {}).get(
            "namespace"
        )
        service = (deployment_target or {}).get("service") or (deployment_target or {}).get(
            "application"
        )
        if not cluster or not service:
            raise ValueError("ECS cluster and service are required for remediation")
        return cluster, service

    def rollback(self, *, deployment_target: dict | None = None) -> tuple[str, dict]:
        cluster, service = self._split(deployment_target or {})
        ecs = self._ecs(deployment_target or {})
        described = ecs.describe_services(cluster=cluster, services=[service])
        svc = (described.get("services") or [{}])[0]
        current_td = svc.get("taskDefinition")
        family = current_td.split("/")[-1].split(":")[0] if current_td else None
        if not family:
            raise ValueError("Could not determine the ECS task definition family")
        revisions = ecs.list_task_definitions(
            familyPrefix=family, sort="DESC", status="ACTIVE"
        ).get("taskDefinitionArns", [])
        previous = next((r for r in revisions if r != current_td), None)
        if not previous:
            raise ValueError("No previous task definition revision to roll back to")
        ecs.update_service(
            cluster=cluster, service=service, taskDefinition=previous, forceNewDeployment=True
        )
        return (
            f"ECS service {service} rolled back to task definition "
            f"{previous.split('/')[-1]}.",
            {"cluster": cluster, "service": service, "restored_task_definition": previous,
             "previous_task_definition": current_td},
        )

    def restart(self, *, deployment_target: dict | None = None) -> tuple[str, dict]:
        cluster, service = self._split(deployment_target or {})
        ecs = self._ecs(deployment_target or {})
        ecs.update_service(cluster=cluster, service=service, forceNewDeployment=True)
        return (
            f"ECS service {service} restarted (forced new deployment).",
            {"cluster": cluster, "service": service},
        )
