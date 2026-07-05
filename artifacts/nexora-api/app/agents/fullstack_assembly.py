from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.fullstack_assembly.assembler import FullStackAssemblyAssembler
from app.schemas.fullstack_assembly import FullstackAssemblyOutput

logger = get_logger(__name__)


class FullStackAssemblyAgent:
    """Assembles deployable application packages from validated execution artifacts."""

    def __init__(self):
        self.assembler = FullStackAssemblyAssembler()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_execution_output: dict,
        frontend_v3_output: dict,
        backend_execution_output: dict,
        backend_v3_output: dict,
    ) -> FullstackAssemblyOutput:
        logger.info("fullstack_assembly_agent_start", assembler_version="2.0.0")

        if not frontend_execution_output:
            raise AgentError("Frontend execution output is required")
        if not backend_execution_output:
            raise AgentError("Backend execution output is required")
        if not frontend_v3_output.get("generated_files"):
            raise AgentError("Frontend V3 generated files are required for assembly")
        if not backend_v3_output.get("generated_files"):
            raise AgentError("Backend V3 generated files are required for assembly")

        try:
            output = self.assembler.assemble(
                frontend_execution_output=frontend_execution_output,
                frontend_v3_output=frontend_v3_output,
                backend_execution_output=backend_execution_output,
                backend_v3_output=backend_v3_output,
                requirement_text=requirement_text,
            )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(f"Assembly failed: {str(exc)}") from exc

        logger.info(
            "fullstack_assembly_agent_complete",
            assembly_status=output.assembly_status,
        )
        return output
