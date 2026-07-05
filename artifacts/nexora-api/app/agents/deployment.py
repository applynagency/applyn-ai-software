import asyncio

from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.deployment.deployer import DeploymentDeployer
from app.schemas.deployment import DeploymentOutput

logger = get_logger(__name__)


class DeploymentAgent:
    """Deploys approved applications to cloud providers."""

    def __init__(self):
        self.deployer = DeploymentDeployer()

    async def run(
        self,
        *,
        fullstack_assembly_output: dict,
        approval_output: dict,
        app_name: str,
        environment: str,
        deployment_provider: str = "AZURE",
        deployment_target: dict | None = None,
    ) -> DeploymentOutput:
        logger.info(
            "deployment_agent_start",
            provider=deployment_provider,
            environment=environment,
        )

        if not fullstack_assembly_output:
            raise AgentError("Full Stack Assembly output is required")
        if not approval_output:
            raise AgentError("Approval output is required")

        try:
            # Real deploys perform blocking I/O (ACR build, Container Apps API,
            # health polling); run them in a worker thread so the event loop is
            # never blocked. The simulated fallback is instant either way.
            output = await asyncio.to_thread(
                self.deployer.deploy,
                provider=deployment_provider,
                fullstack_assembly_output=fullstack_assembly_output,
                approval_output=approval_output,
                app_name=app_name,
                environment=environment,
                deployment_target=deployment_target,
            )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(f"Deployment failed: {str(exc)}") from exc

        logger.info(
            "deployment_agent_complete",
            status=output.deployment_status,
            live_url=output.live_url,
        )
        return output
