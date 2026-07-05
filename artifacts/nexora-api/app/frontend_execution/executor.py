import asyncio
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.frontend_execution import EXECUTION_STEPS, EXECUTOR_VERSION
from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.schemas.frontend_execution import FrontendExecutionOutput

logger = get_logger(__name__)


class FrontendExecutionExecutor:
    """Executes frontend build pipelines in a temporary workspace."""

    def _write_generated_files(self, workspace: Path, frontend_v3_output: dict) -> None:
        generated_files = frontend_v3_output.get("generated_files") or []
        if not generated_files:
            raise AgentError("Frontend V3 output contains no generated files")

        for file_item in generated_files:
            path = file_item.get("path") if isinstance(file_item, dict) else None
            content = file_item.get("content") if isinstance(file_item, dict) else None
            if not path:
                continue
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content or "", encoding="utf-8")

    def _run_command(self, command: str, workspace: Path) -> dict[str, Any]:
        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "CI": "true"},
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            status = "success" if result.returncode == 0 else "failed"
            return {
                "status": status,
                "exit_code": result.returncode,
                "stdout": result.stdout[-8000:] if result.stdout else "",
                "stderr": result.stderr[-8000:] if result.stderr else "",
                "duration_ms": duration_ms,
                "command": command,
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
                "command": command,
            }
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "failed",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "duration_ms": duration_ms,
                "command": command,
            }

    def _derive_approval_status(
        self,
        *,
        build_status: str,
        validation_status: str,
        frontend_code_review_output: dict,
    ) -> str:
        review_approval = frontend_code_review_output.get("approval_status", "NEEDS_REVIEW")
        if isinstance(review_approval, dict):
            review_approval = review_approval.get("value", "NEEDS_REVIEW")

        if build_status != "success" or validation_status == "failed":
            return FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value

        if review_approval in ("REJECTED", "NEEDS_REVIEW"):
            return FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value

        if validation_status == "warnings" or review_approval == "APPROVED_WITH_WARNINGS":
            return FrontendExecutionApprovalStatus.FRONTEND_APPROVED_WITH_WARNINGS.value

        return FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value

    def _derive_validation_status(self, step_results: dict[str, dict[str, Any]]) -> str:
        failed = [name for name, result in step_results.items() if result.get("status") == "failed"]
        if failed:
            critical = {"install", "build", "typecheck"}
            if any(step in critical for step in failed):
                return "failed"
            return "warnings"
        return "passed"

    def execute_sync(
        self,
        *,
        frontend_v3_output: dict,
        frontend_code_review_output: dict,
    ) -> FrontendExecutionOutput:
        logs: list[str] = []
        step_results: dict[str, dict[str, Any]] = {}

        with tempfile.TemporaryDirectory(prefix="frontend-exec-") as tmp_dir:
            workspace = Path(tmp_dir)
            logs.append(f"Created temporary workspace at {workspace}")

            self._write_generated_files(workspace, frontend_v3_output)
            logs.append(
                f"Wrote {len(frontend_v3_output.get('generated_files') or [])} generated files"
            )

            for command, step_name in EXECUTION_STEPS:
                logs.append(f"Running: {command}")
                result = self._run_command(command, workspace)
                step_results[step_name] = result
                logs.append(
                    f"{step_name}: {result['status']} (exit {result['exit_code']}, "
                    f"{result.get('duration_ms', 0)}ms)"
                )
                if step_name in ("install", "build") and result["status"] == "failed":
                    break

        validation_status = self._derive_validation_status(step_results)
        build_result = step_results.get("build", {})
        build_status = build_result.get("status", "failed")

        approval_status = self._derive_approval_status(
            build_status=build_status,
            validation_status=validation_status,
            frontend_code_review_output=frontend_code_review_output,
        )

        return FrontendExecutionOutput(
            build_status=build_status,
            validation_status=validation_status,
            lint_results=step_results.get("lint", {}),
            typecheck_results=step_results.get("typecheck", {}),
            test_results=step_results.get("test", {}),
            build_results=step_results.get("build", {}),
            install_results=step_results.get("install", {}),
            execution_logs=logs,
            approval_status=approval_status,
        )

    async def execute(
        self,
        *,
        frontend_v3_output: dict,
        frontend_code_review_output: dict,
    ) -> FrontendExecutionOutput:
        return await asyncio.to_thread(
            self.execute_sync,
            frontend_v3_output=frontend_v3_output,
            frontend_code_review_output=frontend_code_review_output,
        )

    @staticmethod
    def get_executor_version() -> str:
        return EXECUTOR_VERSION
