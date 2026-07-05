from app.backend_execution.executor import BackendExecutionExecutor
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.backend_execution import BackendExecutionOutput

logger = get_logger(__name__)


class BackendExecutionAgent:
    """Runs backend build and validation pipeline against generated code."""

    def __init__(self):
        self.executor = BackendExecutionExecutor()

    async def run(
        self,
        *,
        backend_v3_output: dict,
        backend_code_review_output: dict,
    ) -> BackendExecutionOutput:
        logger.info(
            "backend_execution_agent_start",
            file_count=len(backend_v3_output.get("generated_files") or []),
            review_approval=backend_code_review_output.get("approval_status"),
        )

        if not backend_v3_output.get("generated_files"):
            raise AgentError("Backend V3 output has no generated files to execute")

        try:
            output = await self.executor.execute(
                backend_v3_output=backend_v3_output,
                backend_code_review_output=backend_code_review_output,
            )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(f"Backend execution failed: {str(exc)}") from exc

        logger.info(
            "backend_execution_agent_complete",
            build_status=output.build_status,
            validation_status=output.validation_status,
            approval_status=output.approval_status,
        )
        return output
