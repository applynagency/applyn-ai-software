"""Backend Developer V1 service.

Thin configuration over :class:`app.services._staged_agent.StagedAgentService`.
The orchestration logic is shared; only the stage-specific models, repositories,
schemas, agent and labels live here. Module-level symbols (notably
``BackendDeveloperV1Agent``) are imported here so existing ``patch`` targets such
as ``app.services.backend_v1.BackendDeveloperV1Agent.run`` keep resolving.
"""

from app.agents.backend_v1 import BackendDeveloperV1Agent
from app.backend_v1.markdown import output_to_markdown
from app.backend_v1.prompt_builder import BackendDeveloperV1PromptBuilder
from app.backend_v1.validator import BackendDeveloperV1Validator
from app.core.logging import get_logger
from app.models.backend_architect import BackendArchitectRunStatus
from app.models.backend_v1 import BackendV1RunStatus
from app.repositories.backend_architect import BackendArchitectRunRepository
from app.repositories.backend_v1 import BackendV1ArtifactRepository, BackendV1RunRepository
from app.schemas.backend_v1 import (
    BackendV1ArtifactResponse,
    BackendV1RunListResponse,
    BackendV1RunResponse,
)
from app.services._staged_agent import PreviousStageConfig, StageConfig, StagedAgentService
from app.tenancy.guards import get_backend_v1_run_for_org

logger = get_logger(__name__)


BACKEND_V1_CONFIG = StageConfig(
    stage="backend_v1",
    self_label="Backend Developer V1",
    run_status_enum=BackendV1RunStatus,
    run_repo_cls=BackendV1RunRepository,
    artifact_repo_cls=BackendV1ArtifactRepository,
    response_cls=BackendV1RunResponse,
    artifact_response_cls=BackendV1ArtifactResponse,
    list_response_cls=BackendV1RunListResponse,
    artifact_model_name="BackendV1Artifact",
    agent_cls=BackendDeveloperV1Agent,
    validator_cls=BackendDeveloperV1Validator,
    prompt_builder_cls=BackendDeveloperV1PromptBuilder,
    to_markdown=output_to_markdown,
    get_run_for_org=get_backend_v1_run_for_org,
    previous=PreviousStageConfig(
        label="Backend Architect",
        model_name="BackendArchitectRun",
        repo_cls=BackendArchitectRunRepository,
        status_enum=BackendArchitectRunStatus,
        run_id_field="backend_architect_run_id",
        agent_output_kwarg="backend_architect_output",
    ),
)


class BackendDeveloperV1Service(StagedAgentService):
    config = BACKEND_V1_CONFIG
