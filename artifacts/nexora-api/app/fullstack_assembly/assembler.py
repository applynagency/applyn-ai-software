from app.models.fullstack_assembly import AssemblyStatus
from app.schemas.fullstack_assembly import FullstackAssemblyOutput

ASSEMBLER_VERSION = "2.0.0"

FRONTEND_APPROVED_STATUSES = {
    "FRONTEND_APPROVED",
    "FRONTEND_APPROVED_WITH_WARNINGS",
}
BACKEND_APPROVED_STATUSES = {
    "BACKEND_APPROVED",
    "BACKEND_APPROVED_WITH_WARNINGS",
}


class FullStackAssemblyAssembler:
    """Assembles deployable full-stack packages from validated execution artifacts."""

    def _derive_assembly_status(
        self,
        *,
        frontend_execution_output: dict,
        backend_execution_output: dict,
    ) -> str:
        fe_approval = frontend_execution_output.get("approval_status", "FRONTEND_NEEDS_REVIEW")
        fe_build = frontend_execution_output.get("build_status", "failed")
        be_approval = backend_execution_output.get("approval_status", "BACKEND_NEEDS_REVIEW")
        be_build = backend_execution_output.get("build_status", "failed")

        if fe_build != "success" or be_build != "success":
            return AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value
        if fe_approval not in FRONTEND_APPROVED_STATUSES:
            return AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value
        if be_approval not in BACKEND_APPROVED_STATUSES:
            return AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value
        if (
            fe_approval == "FRONTEND_APPROVED_WITH_WARNINGS"
            or be_approval == "BACKEND_APPROVED_WITH_WARNINGS"
        ):
            return AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value
        return AssemblyStatus.ASSEMBLY_APPROVED.value

    def _merge_environment_variables(
        self,
        *,
        frontend_v3_output: dict,
        backend_v3_output: dict,
    ) -> list[dict]:
        merged: dict[str, dict] = {}
        for source in (
            frontend_v3_output.get("environment_variables") or [],
            backend_v3_output.get("environment_variables") or [],
        ):
            for item in source:
                name = item.get("name")
                if name:
                    merged[name] = item
        return list(merged.values())

    def assemble(
        self,
        *,
        frontend_execution_output: dict,
        frontend_v3_output: dict,
        backend_execution_output: dict,
        backend_v3_output: dict,
        requirement_text: str = "",
    ) -> FullstackAssemblyOutput:
        frontend_files = frontend_v3_output.get("generated_files") or []
        backend_files = backend_v3_output.get("generated_files") or []
        package_json = frontend_v3_output.get("package_json") or {}
        app_name = package_json.get("name", "application")
        backend_framework = (backend_v3_output.get("project_structure") or {}).get(
            "framework", "fastapi"
        )

        frontend_package = {
            "name": app_name,
            "framework": "nextjs",
            "file_count": len(frontend_files),
            "generated_files": frontend_files,
            "execution_summary": {
                "build_status": frontend_execution_output.get("build_status"),
                "validation_status": frontend_execution_output.get("validation_status"),
                "approval_status": frontend_execution_output.get("approval_status"),
            },
        }

        backend_package = {
            "included": True,
            "name": f"{app_name}-api",
            "framework": backend_framework,
            "file_count": len(backend_files),
            "generated_files": backend_files,
            "execution_summary": {
                "build_status": backend_execution_output.get("build_status"),
                "validation_status": backend_execution_output.get("validation_status"),
                "approval_status": backend_execution_output.get("approval_status"),
            },
        }

        environment_variables = self._merge_environment_variables(
            frontend_v3_output=frontend_v3_output,
            backend_v3_output=backend_v3_output,
        )

        frontend_docker = next(
            (f for f in frontend_files if f.get("path", "").endswith("Dockerfile")),
            None,
        )
        backend_docker = next(
            (f for f in backend_files if f.get("path", "").endswith("Dockerfile")),
            None,
        )

        docker_assets = {
            "frontend_dockerfile": frontend_docker,
            "backend_dockerfile": backend_docker,
            "docker_configuration": {
                "frontend": frontend_v3_output.get("docker_configuration") or {},
                "backend": backend_v3_output.get("docker_configuration") or {},
            },
            "compose_file": {
                "path": "docker-compose.yml",
                "content": self._compose_content(
                    app_name=app_name,
                    environment_variables=environment_variables,
                ),
            },
        }

        deployment_assets = {
            "kubernetes": {
                "frontend_deployment": self._k8s_deployment_template(app_name, component="frontend"),
                "frontend_service": self._k8s_service_template(app_name, port=3000),
                "backend_deployment": self._k8s_deployment_template(
                    f"{app_name}-api", component="backend"
                ),
                "backend_service": self._k8s_service_template(f"{app_name}-api", port=8000),
            },
            "scripts": {
                "deploy.sh": "#!/bin/bash\ndocker compose up -d --build\n",
                "healthcheck.sh": (
                    "#!/bin/bash\n"
                    "curl -f http://localhost:8000/health || exit 1\n"
                    "curl -f http://localhost:3000 || exit 1\n"
                ),
            },
        }

        infrastructure_templates = {
            "terraform": {
                "main.tf": self._terraform_stub(app_name),
            },
            "helm": {
                "Chart.yaml": f"apiVersion: v2\nname: {app_name}\nversion: 1.0.0\n",
            },
        }

        health_checks = {
            "frontend": {
                "path": "/",
                "port": 3000,
                "interval_seconds": 30,
                "timeout_seconds": 5,
            },
            "backend": {
                "path": "/health",
                "port": 8000,
                "interval_seconds": 30,
                "timeout_seconds": 5,
            },
        }

        startup_configuration = {
            "order": ["backend", "frontend"],
            "backend": {
                "command": "uvicorn app.main:app --host 0.0.0.0 --port 8000",
                "port": 8000,
                "depends_on": [],
            },
            "frontend": {
                "command": "npm run start",
                "port": 3000,
                "depends_on": ["backend"],
            },
        }

        application_manifest = {
            "name": app_name,
            "version": package_json.get("version", "1.0.0"),
            "description": requirement_text[:500] if requirement_text else "Full-stack application",
            "components": {
                "frontend": {"included": True, "framework": "nextjs-15", "port": 3000},
                "backend": {"included": True, "framework": backend_framework, "port": 8000},
            },
            "deployment": {
                "strategy": "docker-compose",
                "ports": {"frontend": 3000, "backend": 8000},
            },
        }

        assembly_status = self._derive_assembly_status(
            frontend_execution_output=frontend_execution_output,
            backend_execution_output=backend_execution_output,
        )

        release_metadata = {
            "version": package_json.get("version", "1.0.0"),
            "assembler_version": ASSEMBLER_VERSION,
            "release_channel": "stable",
            "frontend_approval": frontend_execution_output.get("approval_status"),
            "backend_approval": backend_execution_output.get("approval_status"),
            "frontend_build_status": frontend_execution_output.get("build_status"),
            "backend_build_status": backend_execution_output.get("build_status"),
        }

        readme = self._build_readme(
            app_name=app_name,
            frontend_execution_output=frontend_execution_output,
            backend_execution_output=backend_execution_output,
        )

        package_metadata = {
            "assembler_version": ASSEMBLER_VERSION,
            "frontend_file_count": len(frontend_files),
            "backend_file_count": len(backend_files),
            "backend_included": True,
            "environment_variable_count": len(environment_variables),
        }

        return FullstackAssemblyOutput(
            application_manifest=application_manifest,
            frontend_package=frontend_package,
            backend_package=backend_package,
            deployment_assets=deployment_assets,
            environment_variables=environment_variables,
            docker_assets=docker_assets,
            infrastructure_templates=infrastructure_templates,
            health_checks=health_checks,
            startup_configuration=startup_configuration,
            release_metadata=release_metadata,
            readme=readme,
            assembly_status=assembly_status,
            package_metadata=package_metadata,
        )

    def _compose_content(self, app_name: str, environment_variables: list) -> str:
        env_lines = "\n".join(
            f"      - {item.get('name', 'VAR')}=${{{item.get('name', 'VAR')}}}"
            for item in environment_variables
            if item.get("name")
        )
        return (
            "services:\n"
            f"  {app_name}-api:\n"
            "    build:\n"
            "      context: ./backend\n"
            "    ports:\n"
            '      - "8000:8000"\n'
            "    environment:\n"
            f"{env_lines or '      - DATABASE_URL=${DATABASE_URL}'}\n"
            f"  {app_name}:\n"
            "    build:\n"
            "      context: ./frontend\n"
            "    ports:\n"
            '      - "3000:3000"\n'
            "    environment:\n"
            f"{env_lines or '      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}'}\n"
            f"    depends_on:\n"
            f"      - {app_name}-api\n"
        )

    def _k8s_deployment_template(self, name: str, *, component: str) -> str:
        return (
            f"apiVersion: apps/v1\n"
            f"kind: Deployment\n"
            f"metadata:\n"
            f"  name: {name}\n"
            f"  labels:\n"
            f"    component: {component}\n"
            f"spec:\n"
            f"  replicas: 1\n"
            f"  selector:\n"
            f"    matchLabels:\n"
            f"      app: {name}\n"
        )

    def _k8s_service_template(self, name: str, *, port: int) -> str:
        return (
            f"apiVersion: v1\n"
            f"kind: Service\n"
            f"metadata:\n"
            f"  name: {name}\n"
            f"spec:\n"
            f"  ports:\n"
            f"    - port: {port}\n"
            f"  selector:\n"
            f"    app: {name}\n"
        )

    def _terraform_stub(self, app_name: str) -> str:
        return (
            f'# Terraform stub for {app_name}\n'
            f'resource "null_resource" "{app_name.replace("-", "_")}" {{\n'
            f"  triggers = {{\n"
            f'    app = "{app_name}"\n'
            f"  }}\n"
            f"}}\n"
        )

    def _build_readme(
        self,
        *,
        app_name: str,
        frontend_execution_output: dict,
        backend_execution_output: dict,
    ) -> str:
        return (
            f"# {app_name} — Deployable Full-Stack Package\n\n"
            f"## Overview\n\n"
            f"This package was assembled from validated frontend and backend execution artifacts.\n\n"
            f"## Frontend Build Status\n\n"
            f"- Build: {frontend_execution_output.get('build_status', 'unknown')}\n"
            f"- Validation: {frontend_execution_output.get('validation_status', 'unknown')}\n"
            f"- Approval: {frontend_execution_output.get('approval_status', 'unknown')}\n\n"
            f"## Backend Build Status\n\n"
            f"- Build: {backend_execution_output.get('build_status', 'unknown')}\n"
            f"- Validation: {backend_execution_output.get('validation_status', 'unknown')}\n"
            f"- Approval: {backend_execution_output.get('approval_status', 'unknown')}\n\n"
            f"## Quick Start\n\n"
            f"```bash\n"
            f"docker compose up -d --build\n"
            f"```\n"
        )

    @staticmethod
    def get_assembler_version() -> str:
        return ASSEMBLER_VERSION
