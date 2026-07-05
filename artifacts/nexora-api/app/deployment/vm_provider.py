"""Sprint 34A — VM (SSH) deployment provider.

Deploys a generated application directly onto a customer-owned Linux VM over
SSH:

1. Connects via SSH (host / port / username / private_key).
2. Uploads the application package (source + ``.env`` + ``docker-compose.yml``)
   over SFTP into a timestamped release directory.
3. Runs ``docker compose pull`` + ``docker compose up -d`` remotely.
4. Verifies health by polling ``http://<host>:<app_port>/health``.
5. Keeps the previous release on disk and supports rollback to it via a
   ``current`` symlink swap + ``docker compose up -d``.

Security: the SSH ``private_key`` is used only to establish the transient
session and is **never** persisted. Only non-secret metadata (server_ip,
deployment_path, container_name, health_url, release ids) is stored.

``paramiko`` and ``httpx`` are imported lazily so importing this module never
fails when paramiko is absent. The SSH session factory and HTTP health checker
are injectable to enable testing without a real VM.
"""

from __future__ import annotations

import os
import re
import shlex
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.deployment.deployer import BaseDeploymentProvider
from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput

logger = get_logger(__name__)

_DEFAULT_CONTAINER_PORT = 8000


def _slugify(app_name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", (app_name or "application").lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "application"


class _ParamikoSession:
    """Default SSH session backed by paramiko (lazy import)."""

    def __init__(self, target: dict) -> None:
        import io

        import paramiko

        pkey = self._load_key(paramiko, io, target.get("private_key", ""))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=target["host"],
            port=int(target.get("port", 22)),
            username=target["username"],
            pkey=pkey,
            timeout=30,
            banner_timeout=30,
            auth_timeout=30,
        )
        self._client = client
        self._sftp = client.open_sftp()

    @staticmethod
    def _load_key(paramiko, io, key_str: str):
        if not key_str:
            raise ValueError("SSH private_key is required")
        for loader in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                return loader.from_private_key(io.StringIO(key_str))
            except Exception:  # noqa: BLE001 — try the next key type
                continue
        raise ValueError("Unsupported or invalid SSH private key")

    def run(self, command: str) -> tuple[int, str, str]:
        _, stdout, stderr = self._client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return exit_code, out, err

    def put_file(self, remote_path: str, content: str) -> None:
        self.run(f"mkdir -p {shlex.quote(os.path.dirname(remote_path))}")
        with self._sftp.open(remote_path, "w") as handle:
            handle.write(content)

    def makedirs(self, remote_path: str) -> None:
        self.run(f"mkdir -p {shlex.quote(remote_path)}")

    def close(self) -> None:
        try:
            self._sftp.close()
        finally:
            self._client.close()


class VMDeploymentProvider(BaseDeploymentProvider):
    """Deploys applications to a customer Linux VM over SSH + Docker Compose."""

    def __init__(
        self,
        ssh_session_factory: Callable[[dict], Any] | None = None,
        http_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self._ssh_session_factory = ssh_session_factory
        self._http_checker = http_checker

    # ------------------------------------------------------------------ #
    # Contract
    # ------------------------------------------------------------------ #
    def deploy(
        self,
        *,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
        deployment_target: dict | None = None,
    ) -> DeploymentOutput:
        target = self._validate_target(deployment_target, require_key=True)

        slug = _slugify(app_name)
        host = target["host"]
        app_port = int(target.get("app_port") or _DEFAULT_CONTAINER_PORT)
        container_port = self._container_port(fullstack_assembly_output)
        deployment_path = target.get("deployment_path") or f"/opt/applyn/{slug}"
        container_name = target.get("container_name") or slug
        health_url = f"http://{host}:{app_port}/health"
        live_url = f"http://{host}:{app_port}"

        release_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        release_dir = f"{deployment_path}/releases/{release_id}"
        package = self._build_package(
            fullstack_assembly_output, container_name, app_port, container_port
        )

        logs: list[str] = [
            f"Connecting to {target['username']}@{host}:{target.get('port', 22)}",
            f"Environment: {environment}",
            f"Deployment path: {deployment_path}",
            f"Preparing release {release_id} ({len(package)} files)",
        ]

        previous_release = ""
        try:
            session = self._connect(target)
            try:
                previous_release = self._current_release(session, deployment_path)
                if previous_release:
                    logs.append(f"Current release detected: {previous_release}")

                session.makedirs(release_dir)
                for path, content in package.items():
                    session.put_file(f"{release_dir}/{path}", content)
                logs.append("Uploaded application package, .env and docker-compose.yml")

                session.run(f"ln -sfn {shlex.quote(release_dir)} {shlex.quote(deployment_path)}/current")
                logs.append("Pointed 'current' symlink to new release")

                self._compose(session, deployment_path, "pull", logs, check=False)
                rc, out, err = self._compose(session, deployment_path, "up -d", logs, check=True)
                logs.append("docker compose up -d completed")
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001 — surfaced as a FAILED deployment
            logger.error("vm_deploy_failed", host=host, error=str(exc))
            logs.append(f"Deployment failed: {exc}")
            return DeploymentOutput(
                deployment_provider=DeploymentProvider.VM.value,
                deployment_status=DeploymentStatus.FAILED.value,
                live_url="",
                deployment_logs=logs,
                rollback_available=False,
                deployment_metadata={
                    "provider": DeploymentProvider.VM.value,
                    "server_ip": host,
                    "deployment_path": deployment_path,
                    "container_name": container_name,
                    "health_url": health_url,
                    "error": str(exc),
                },
            )

        logs.append(f"Polling health endpoint {health_url}")
        healthy = self._check_health(health_url)
        status = (
            DeploymentStatus.DEPLOYED.value if healthy else DeploymentStatus.FAILED.value
        )
        logs.append(
            f"Health check {'passed — ' + live_url if healthy else 'failed (no HTTP 200)'}"
        )

        return DeploymentOutput(
            deployment_provider=DeploymentProvider.VM.value,
            deployment_status=status,
            live_url=live_url if healthy else "",
            deployment_logs=logs,
            rollback_available=healthy and bool(previous_release),
            deployment_metadata={
                "provider": DeploymentProvider.VM.value,
                "server_ip": host,
                "deployment_path": deployment_path,
                "container_name": container_name,
                "health_url": health_url,
                "app_port": app_port,
                "container_port": container_port,
                "current_release": release_id,
                # Aliased to previous/target so the existing rollback metadata
                # builder (shared with Azure) captures them too.
                "previous_release": previous_release,
                "previous_revision": previous_release,
                "target_revision": release_id,
            },
        )

    def rollback(
        self,
        *,
        app_name: str,
        rollback_metadata: dict,
        environment: str,
        deployment_target: dict | None = None,
    ) -> tuple[DeploymentOutput, list[str]]:
        deployment_path = rollback_metadata.get("deployment_path")
        previous_release = (
            rollback_metadata.get("previous_release")
            or rollback_metadata.get("previous_revision")
        )
        health_url = rollback_metadata.get("health_url")
        server_ip = rollback_metadata.get("server_ip")

        if not deployment_path:
            raise ValueError("deployment_path missing from rollback metadata")
        if not previous_release:
            raise ValueError("No previous release available to roll back to")

        target = self._validate_target(
            {**(deployment_target or {}), "host": (deployment_target or {}).get("host") or server_ip},
            require_key=True,
        )

        prev_dir = f"{deployment_path}/releases/{previous_release}"
        logs: list[str] = [
            f"Connecting to {target['username']}@{target['host']} for rollback",
            f"Rolling back to release {previous_release}",
        ]

        session = self._connect(target)
        try:
            session.run(f"ln -sfn {shlex.quote(prev_dir)} {shlex.quote(deployment_path)}/current")
            logs.append("Repointed 'current' symlink to previous release")
            self._compose(session, deployment_path, "up -d", logs, check=True)
            logs.append("docker compose up -d completed on previous release")
        finally:
            session.close()

        healthy = self._check_health(health_url) if health_url else True
        live_url = health_url[: -len("/health")] if health_url and health_url.endswith("/health") else ""
        logs.append(f"Rollback health check {'passed' if healthy else 'failed'}")

        output = DeploymentOutput(
            deployment_provider=DeploymentProvider.VM.value,
            deployment_status=DeploymentStatus.ROLLED_BACK.value,
            live_url=live_url,
            deployment_logs=logs,
            rollback_available=False,
            deployment_metadata={
                "provider": DeploymentProvider.VM.value,
                "rollback_completed": True,
                "restored_release": previous_release,
                "deployment_path": deployment_path,
                "server_ip": target["host"],
            },
        )
        return output, logs

    # ------------------------------------------------------------------ #
    # Sprint 41C — approval-gated remediation operations over SSH.
    # ------------------------------------------------------------------ #
    def restart_stack(self, *, deployment_target: dict | None = None) -> tuple[str, dict]:
        target = self._validate_target(deployment_target, require_key=True)
        deployment_path = target.get("deployment_path") or "/opt/applyn"
        logs: list[str] = []
        session = self._connect(target)
        try:
            self._compose(session, deployment_path, "restart", logs, check=True)
        finally:
            session.close()
        return (
            f"Docker Compose stack restarted at {deployment_path} on {target['host']}.",
            {"deployment_path": deployment_path, "server_ip": target["host"]},
        )

    def restart_service(
        self, *, service_name: str, deployment_target: dict | None = None
    ) -> tuple[str, dict]:
        if not service_name:
            raise ValueError("service_name is required to restart a service")
        target = self._validate_target(deployment_target, require_key=True)
        session = self._connect(target)
        try:
            rc, out, err = session.run(f"sudo systemctl restart {shlex.quote(service_name)}")
            if rc != 0:
                raise RuntimeError(
                    f"systemctl restart {service_name} failed: {err.strip() or out.strip()}"
                )
        finally:
            session.close()
        return (
            f"Service {service_name} restarted on {target['host']}.",
            {"service_name": service_name, "server_ip": target["host"]},
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _validate_target(self, deployment_target: dict | None, *, require_key: bool) -> dict:
        target = dict(deployment_target or {})
        if not target.get("host"):
            raise ValueError("deployment_target.host is required for VM deployment")
        if not target.get("username"):
            raise ValueError("deployment_target.username is required for VM deployment")
        if require_key and not target.get("private_key"):
            raise ValueError("deployment_target.private_key is required for VM deployment")
        return target

    def _connect(self, target: dict):
        if self._ssh_session_factory is not None:
            return self._ssh_session_factory(target)
        return _ParamikoSession(target)

    def _current_release(self, session, deployment_path: str) -> str:
        rc, out, _ = session.run(f"readlink {shlex.quote(deployment_path)}/current")
        if rc == 0 and out.strip():
            return os.path.basename(out.strip())
        return ""

    def _compose(
        self, session, deployment_path: str, action: str, logs: list[str], *, check: bool
    ) -> tuple[int, str, str]:
        command = f"cd {shlex.quote(deployment_path)}/current && docker compose {action}"
        rc, out, err = session.run(command)
        logs.append(f"$ docker compose {action} (exit {rc})")
        if check and rc != 0:
            raise RuntimeError(f"'docker compose {action}' failed: {err.strip() or out.strip()}")
        return rc, out, err

    def _container_port(self, fsa_output: dict) -> int:
        docker_cfg = (
            (fsa_output.get("docker_assets") or {}).get("docker_configuration") or {}
        ).get("backend") or {}
        startup_cfg = (fsa_output.get("startup_configuration") or {}).get("backend") or {}
        health_cfg = (fsa_output.get("health_checks") or {}).get("backend") or {}
        return int(
            docker_cfg.get("port")
            or startup_cfg.get("port")
            or health_cfg.get("port")
            or _DEFAULT_CONTAINER_PORT
        )

    def _build_package(
        self, fsa_output: dict, container_name: str, app_port: int, container_port: int
    ) -> dict[str, str]:
        backend_pkg = fsa_output.get("backend_package") or {}
        files: dict[str, str] = {}
        for item in backend_pkg.get("generated_files") or []:
            if isinstance(item, dict) and item.get("path"):
                files[item["path"]] = item.get("content", "")

        if "requirements.txt" not in files and backend_pkg.get("requirements_txt"):
            files["requirements.txt"] = backend_pkg["requirements_txt"]
        if "Dockerfile" not in files:
            files["Dockerfile"] = self._default_dockerfile(container_port)

        files[".env"] = self._build_env(fsa_output, container_port)
        files["docker-compose.yml"] = self._compose_file(
            container_name, app_port, container_port
        )
        return files

    def _build_env(self, fsa_output: dict, container_port: int) -> str:
        lines = [f"PORT={container_port}"]
        for item in fsa_output.get("environment_variables") or []:
            name = item.get("name") if isinstance(item, dict) else None
            if name:
                value = item.get("value", "") if isinstance(item, dict) else ""
                lines.append(f"{name}={value}")
        return "\n".join(lines) + "\n"

    def _compose_file(self, container_name: str, app_port: int, container_port: int) -> str:
        return (
            "services:\n"
            f"  {container_name}:\n"
            "    build: .\n"
            f"    image: {container_name}:latest\n"
            f"    container_name: {container_name}\n"
            "    restart: unless-stopped\n"
            "    env_file:\n"
            "      - .env\n"
            "    ports:\n"
            f'      - "{app_port}:{container_port}"\n'
        )

    def _default_dockerfile(self, container_port: int) -> str:
        return (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY . .\n"
            f"EXPOSE {container_port}\n"
            f'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{container_port}"]\n'
        )

    def _check_health(self, health_url: str) -> bool:
        if self._http_checker is not None:
            return self._http_checker(health_url)
        return self._poll_http(health_url)

    def _poll_http(self, health_url: str) -> bool:
        import httpx

        if not health_url:
            return False
        timeout = settings.DEPLOYMENT_TIMEOUT_SECONDS
        interval = max(1, settings.DEPLOYMENT_HEALTH_POLL_INTERVAL_SECONDS)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = httpx.get(health_url, timeout=10, follow_redirects=True)
                if response.status_code == 200:
                    return True
            except Exception:  # noqa: BLE001 — app still starting up
                pass
            time.sleep(interval)
        return False
