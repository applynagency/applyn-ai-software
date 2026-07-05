from app.approval_workflow.processor import ApprovalWorkflowProcessor
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.approval import ApprovalWorkflowOutput

logger = get_logger(__name__)


class ApprovalWorkflowAgent:
    """Generates approval packages and readiness reports for human review."""

    def __init__(self):
        self.processor = ApprovalWorkflowProcessor()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_execution_output: dict,
        frontend_code_review_output: dict,
        fullstack_assembly_output: dict,
    ) -> ApprovalWorkflowOutput:
        logger.info("approval_workflow_agent_start")

        if not frontend_execution_output:
            raise AgentError("Frontend execution output is required")
        if not frontend_code_review_output:
            raise AgentError("Frontend code review output is required")
        if not fullstack_assembly_output:
            raise AgentError("Full Stack Assembly output is required")

        try:
            output = self.processor.process(
                frontend_execution_output=frontend_execution_output,
                frontend_code_review_output=frontend_code_review_output,
                fullstack_assembly_output=fullstack_assembly_output,
                requirement_text=requirement_text,
            )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(f"Approval workflow processing failed: {str(exc)}") from exc

        logger.info(
            "approval_workflow_agent_complete",
            recommendation=output.recommendation,
            approval_status=output.approval_status,
        )
        return output
