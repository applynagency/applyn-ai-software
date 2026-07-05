"""Backend Developer V3 service.

Thin configuration over :class:`app.services._staged_agent.StagedAgentService`;
see ``backend_v1.py`` for the rationale behind keeping module-level symbols.
"""

from app.agents.backend_v3 import BackendDeveloperV3Agent
from app.backend_v3.markdown import output_to_markdown
from app.backend_v3.prompt_builder import BackendDeveloperV3PromptBuilder
from app.backend_v3.validator import BackendDeveloperV3Validator
from app.core.logging import get_logger
from app.models.backend_v2 import BackendV2RunStatus
from app.models.backend_v3 import BackendV3RunStatus
from app.repositories.backend_v2 import BackendV2RunRepository
from app.repositories.backend_v3 import BackendV3ArtifactRepository, BackendV3RunRepository
from app.schemas.backend_v3 import (
    BackendV3ArtifactResponse,
    BackendV3RunListResponse,
    BackendV3RunResponse,
)
from app.services._staged_agent import PreviousStageConfig, StageConfig, StagedAgentService
from app.tenancy.guards import get_backend_v3_run_for_org

logger = get_logger(__name__)


BACKEND_V3_CONFIG = StageConfig(
    stage="backend_v3",
    self_label="Backend Developer V3",
    run_status_enum=BackendV3RunStatus,
    run_repo_cls=BackendV3RunRepository,
    artifact_repo_cls=BackendV3ArtifactRepository,
    response_cls=BackendV3RunResponse,
    artifact_response_cls=BackendV3ArtifactResponse,
    list_response_cls=BackendV3RunListResponse,
    artifact_model_name="BackendV3Artifact",
    agent_cls=BackendDeveloperV3Agent,
    validator_cls=BackendDeveloperV3Validator,
    prompt_builder_cls=BackendDeveloperV3PromptBuilder,
    to_markdown=output_to_markdown,
    get_run_for_org=get_backend_v3_run_for_org,
    previous=PreviousStageConfig(
        label="Backend Developer V2",
        model_name="BackendV2Run",
        repo_cls=BackendV2RunRepository,
        status_enum=BackendV2RunStatus,
        run_id_field="backend_v2_run_id",
        agent_output_kwarg="backend_v2_output",
    ),
)


class BackendDeveloperV3Service(StagedAgentService):
    config = BACKEND_V3_CONFIG
