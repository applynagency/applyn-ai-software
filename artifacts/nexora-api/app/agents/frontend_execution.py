from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.frontend_execution.executor import FrontendExecutionExecutor
from app.schemas.frontend_execution import FrontendExecutionOutput

logger = get_logger(__name__)


class FrontendExecutionAgent:
    """Runs frontend build pipeline validation against generated code."""

    def __init__(self):
        self.executor = FrontendExecutionExecutor()

    async def run(
        self,
        *,
        frontend_v3_output: dict,
        frontend_code_review_output: dict,
    ) -> FrontendExecutionOutput:
        logger.info(
            "frontend_execution_agent_start",
            file_count=len(frontend_v3_output.get("generated_files") or []),
            review_approval=frontend_code_review_output.get("approval_status"),
        )

        if not frontend_v3_output.get("generated_files"):
            raise AgentError("Frontend V3 output has no generated files to execute")

        try:
            output = await self.executor.execute(
                frontend_v3_output=frontend_v3_output,
                frontend_code_review_output=frontend_code_review_output,
            )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(f"Frontend execution failed: {str(exc)}") from exc

        logger.info(
            "frontend_execution_agent_complete",
            build_status=output.build_status,
            validation_status=output.validation_status,
            approval_status=output.approval_status,
        )
        return output
