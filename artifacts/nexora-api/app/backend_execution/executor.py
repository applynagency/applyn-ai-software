import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.backend_execution import (
    CRITICAL_STEPS,
    EXECUTION_STEPS,
    EXECUTOR_VERSION,
    STEP_RESULT_FIELDS,
)
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.models.backend_execution import BackendExecutionApprovalStatus
from app.schemas.backend_execution import BackendExecutionOutput

logger = get_logger(__name__)


class BackendExecutionExecutor:
    """Executes backend build and validation pipelines in a temporary workspace."""

    def _write_generated_files(self, workspace: Path, backend_v3_output: dict) -> None:
        generated_files = backend_v3_output.get("generated_files") or []
        if not generated_files:
            raise AgentError("Backend V3 output contains no generated files")

        for file_item in generated_files:
            path = file_item.get("path") if isinstance(file_item, dict) else None
            content = file_item.get("content") if isinstance(file_item, dict) else None
            if not path:
                continue
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content or "", encoding="utf-8")

    def _python_bin(self) -> str:
        return sys.executable

    def _venv_python(self, workspace: Path) -> str:
        venv_python = workspace / ".venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        return self._python_bin()

    def _should_skip_step(self, workspace: Path, step_name: str) -> bool:
        if step_name == "pip_install":
            return not (workspace / "requirements.txt").exists()
        if step_name == "alembic":
            return not (workspace / "alembic.ini").exists()
        if step_name == "pytest":
            tests_dir = workspace / "tests"
            return not tests_dir.exists() or not any(tests_dir.glob("test_*.py"))
        if step_name in ("ruff", "mypy"):
            return not (workspace / "app").exists()
        if step_name == "environment":
            config_path = workspace / "app" / "core" / "config.py"
            return not config_path.exists()
        return False

    def _resolve_command(self, command: str, workspace: Path) -> str:
        if command.startswith("python "):
            return command.replace("python ", f"{self._python_bin()} ", 1)
        if command.startswith(".venv/bin/"):
            venv_bin = workspace / ".venv" / "bin"
            return command.replace(".venv/bin/", f"{venv_bin}/", 1)
        return command

    def _run_command(self, command: str, workspace: Path) -> dict[str, Any]:
        resolved = self._resolve_command(command, workspace)
        start = time.monotonic()
        try:
            result = subprocess.run(
                resolved,
                shell=True,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "CI": "true", "PYTHONDONTWRITEBYTECODE": "1"},
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            status = "success" if result.returncode == 0 else "failed"
            return {
                "status": status,
                "exit_code": result.returncode,
                "stdout": result.stdout[-8000:] if result.stdout else "",
                "stderr": result.stderr[-8000:] if result.stderr else "",
                "duration_ms": duration_ms,
                "command": resolved,
            }
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "failed",
                "exit_code": -1,
                "stdout": (exc.stdout or b"").decode("utf-8", errors="replace")[-8000:],
                "stderr": (exc.stderr or b"").decode("utf-8", errors="replace")[-8000:]
                or "Command timed out",
                "duration_ms": duration_ms,
                "command": resolved,
            }
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "failed",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "duration_ms": duration_ms,
                "command": resolved,
            }

    def _derive_approval_status(
        self,
        *,
        build_status: str,
        validation_status: str,
        backend_code_review_output: dict,
    ) -> str:
        review_approval = backend_code_review_output.get("approval_status", "NEEDS_REVIEW")
        if hasattr(review_approval, "value"):
            review_approval = review_approval.value
        if isinstance(review_approval, dict):
            review_approval = review_approval.get("value", "NEEDS_REVIEW")

        if build_status != "success" or validation_status == "failed":
            return BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value

        if review_approval in ("REJECTED", "NEEDS_REVIEW"):
            return BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value

        if validation_status == "warnings" or review_approval == "APPROVED_WITH_WARNINGS":
            return BackendExecutionApprovalStatus.BACKEND_APPROVED_WITH_WARNINGS.value

        return BackendExecutionApprovalStatus.BACKEND_APPROVED.value

    def _derive_validation_status(self, step_results: dict[str, dict[str, Any]]) -> str:
        failed = [name for name, result in step_results.items() if result.get("status") == "failed"]
        if not failed:
            return "passed"
        if any(step in CRITICAL_STEPS for step in failed):
            return "failed"
        return "warnings"

    def _derive_build_status(self, step_results: dict[str, dict[str, Any]]) -> str:
        for step in ("startup", "pip_install", "import_validation"):
            result = step_results.get(step)
            if result and result.get("status") == "failed":
                return "failed"
        if step_results.get("syntax_validation", {}).get("status") == "failed":
            return "failed"
        return "success"

    def _map_step_results(self, step_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        skipped = {
            "status": "skipped",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "duration_ms": 0,
            "command": "",
        }
        mapped: dict[str, dict[str, Any]] = {}
        for step_name, field_name in STEP_RESULT_FIELDS.items():
            mapped[field_name] = step_results.get(step_name, dict(skipped))
        return mapped

    def execute_sync(
        self,
        *,
        backend_v3_output: dict,
        backend_code_review_output: dict,
    ) -> BackendExecutionOutput:
        logs: list[str] = []
        step_results: dict[str, dict[str, Any]] = {}

        with tempfile.TemporaryDirectory(prefix="backend-exec-") as tmp_dir:
            workspace = Path(tmp_dir)
            logs.append(f"Created temporary workspace at {workspace}")

            self._write_generated_files(workspace, backend_v3_output)
            logs.append(
                f"Wrote {len(backend_v3_output.get('generated_files') or [])} generated files"
            )

            for command, step_name in EXECUTION_STEPS:
                if self._should_skip_step(workspace, step_name):
                    skipped = {
                        "status": "skipped",
                        "exit_code": 0,
                        "stdout": "",
                        "stderr": "",
                        "duration_ms": 0,
                        "command": command,
                    }
                    step_results[step_name] = skipped
                    logs.append(f"{step_name}: skipped (prerequisite files missing)")
                    continue

                logs.append(f"Running: {command}")
                result = self._run_command(command, workspace)
                step_results[step_name] = result
                logs.append(
                    f"{step_name}: {result['status']} (exit {result['exit_code']}, "
                    f"{result.get('duration_ms', 0)}ms)"
                )
                if step_name in CRITICAL_STEPS and result["status"] == "failed":
                    break

        validation_status = self._derive_validation_status(step_results)
        build_status = self._derive_build_status(step_results)
        approval_status = self._derive_approval_status(
            build_status=build_status,
            validation_status=validation_status,
            backend_code_review_output=backend_code_review_output,
        )
        mapped = self._map_step_results(step_results)

        return BackendExecutionOutput(
            build_status=build_status,
            validation_status=validation_status,
            execution_logs=logs,
            approval_status=approval_status,
            **mapped,
        )

    async def execute(
        self,
        *,
        backend_v3_output: dict,
        backend_code_review_output: dict,
    ) -> BackendExecutionOutput:
        return await asyncio.to_thread(
            self.execute_sync,
            backend_v3_output=backend_v3_output,
            backend_code_review_output=backend_code_review_output,
        )

    @staticmethod
    def get_executor_version() -> str:
        return EXECUTOR_VERSION
