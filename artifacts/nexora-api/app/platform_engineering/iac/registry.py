"""Simulated IaC execution — provider-agnostic plan/apply engine.

In production this delegates to real CLI/SDK invocations in isolated runners.
The simulation produces deterministic, inspectable output for tests and demos.
"""

from __future__ import annotations

import hashlib
import json

from app.platform_engineering.iac.base import IaCPlanResult, IaCProvider, IaCRunResult
from app.platform_engineering.types import IaCProviderType, IaCRunKind


def _hash_key(provider: str, kind: str, variables: dict) -> str:
    raw = json.dumps({"p": provider, "k": kind, "v": variables}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


class SimulatedIaCProvider:
    """Base simulated provider shared by Terraform-compatible tools."""

    def __init__(self, provider_type: IaCProviderType, cli_name: str):
        self.provider_type = provider_type
        self.cli_name = cli_name

    def _plan_result(self, variables: dict) -> IaCPlanResult:
        h = _hash_key(self.cli_name, "plan", variables)
        return IaCPlanResult(
            add=2 + int(h[0], 16) % 3,
            change=1,
            destroy=0,
            output_preview=f"Plan: {self.cli_name} will create resources [{h}]",
            outputs={"cluster_endpoint": f"https://cluster-{h}.example.com"},
            drift_detected=False,
        )

    def validate(self, *, working_dir: str, variables: dict) -> IaCRunResult:
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} validate -chdir={working_dir}\nSuccess! Configuration is valid.",
        )

    def fmt(self, *, working_dir: str) -> IaCRunResult:
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} fmt -check {working_dir}\nNo formatting changes needed.",
        )

    def plan(self, *, working_dir: str, variables: dict) -> IaCRunResult:
        plan = self._plan_result(variables)
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} plan\n{plan.output_preview}",
            plan=plan,
            outputs=plan.outputs,
        )

    def apply(self, *, working_dir: str, variables: dict) -> IaCRunResult:
        plan = self._plan_result(variables)
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} apply -auto-approve\nApply complete! Resources: {plan.add} added.",
            plan=plan,
            outputs=plan.outputs,
            state_metadata={"serial": 1, "lineage": _hash_key(self.cli_name, "state", variables), "simulated": True},
            simulated=True,
        )

    def destroy(self, *, working_dir: str, variables: dict) -> IaCRunResult:
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} destroy -auto-approve\nDestroy complete!",
            state_metadata={"serial": 0, "simulated": True},
            simulated=True,
        )

    def refresh(self, *, working_dir: str, variables: dict) -> IaCRunResult:
        plan = self._plan_result(variables)
        plan.drift_detected = int(_hash_key(self.cli_name, "drift", variables)[0], 16) % 5 == 0
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} refresh\nDrift: {'yes' if plan.drift_detected else 'no'}",
            plan=plan,
        )

    def graph(self, *, working_dir: str) -> IaCRunResult:
        return IaCRunResult(
            success=True,
            logs=f"digraph G {{ provider -> module -> resource }}",
        )

    def import_resource(self, *, working_dir: str, variables: dict, resource_address: str) -> IaCRunResult:
        return IaCRunResult(
            success=True,
            logs=f"{self.cli_name} import {resource_address}\nImport successful.",
            outputs={"imported": resource_address},
        )


class CloudFormationProvider(SimulatedIaCProvider):
    def __init__(self):
        super().__init__(IaCProviderType.CLOUDFORMATION, "aws cloudformation")


class BicepProvider(SimulatedIaCProvider):
    def __init__(self):
        super().__init__(IaCProviderType.BICEP, "az bicep")


class PulumiProvider(SimulatedIaCProvider):
    def __init__(self):
        super().__init__(IaCProviderType.PULUMI, "pulumi")


_PROVIDERS: dict[IaCProviderType, IaCProvider] = {
    IaCProviderType.TERRAFORM: SimulatedIaCProvider(IaCProviderType.TERRAFORM, "terraform"),
    IaCProviderType.OPENTOFU: SimulatedIaCProvider(IaCProviderType.OPENTOFU, "tofu"),
    IaCProviderType.PULUMI: PulumiProvider(),
    IaCProviderType.CLOUDFORMATION: CloudFormationProvider(),
    IaCProviderType.BICEP: BicepProvider(),
}


def get_iac_provider(provider_type: IaCProviderType | str) -> IaCProvider:
    key = IaCProviderType(provider_type) if isinstance(provider_type, str) else provider_type
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise ValueError(f"Unsupported IaC provider: {provider_type}")
    return provider


def supported_iac_providers() -> list[str]:
    return [p.value for p in IaCProviderType]


def run_iac_operation(
    provider_type: IaCProviderType | str,
    kind: IaCRunKind | str,
    *,
    working_dir: str = "/tmp/iac",
    variables: dict | None = None,
    live_config: dict | None = None,
) -> IaCRunResult:
    variables = variables or {}
    kind = IaCRunKind(kind) if isinstance(kind, str) else kind
    provider_key = str(provider_type).upper()
    if provider_key == IaCProviderType.TERRAFORM.value and live_config:
        from app.platform_engineering.iac import terraform_cloud_live

        if kind == IaCRunKind.PLAN:
            return terraform_cloud_live.create_plan_run(
                live_config,
                workspace_id=variables.get("terraform_workspace_id") or variables.get("workspace_id"),
                variables=variables,
            )
    provider = get_iac_provider(provider_type)
    if kind == IaCRunKind.VALIDATE:
        return provider.validate(working_dir=working_dir, variables=variables)
    if kind == IaCRunKind.FMT:
        return provider.fmt(working_dir=working_dir)
    if kind == IaCRunKind.PLAN:
        return provider.plan(working_dir=working_dir, variables=variables)
    if kind == IaCRunKind.APPLY:
        return provider.apply(working_dir=working_dir, variables=variables)
    if kind == IaCRunKind.DESTROY:
        return provider.destroy(working_dir=working_dir, variables=variables)
    if kind == IaCRunKind.REFRESH:
        return provider.refresh(working_dir=working_dir, variables=variables)
    if kind == IaCRunKind.GRAPH:
        return provider.graph(working_dir=working_dir)
    if kind == IaCRunKind.IMPORT:
        addr = variables.get("resource_address", "module.example")
        return provider.import_resource(  # type: ignore[attr-defined]
            working_dir=working_dir, variables=variables, resource_address=addr,
        )
    return IaCRunResult(success=False, logs="", error=f"Unsupported operation: {kind}")
