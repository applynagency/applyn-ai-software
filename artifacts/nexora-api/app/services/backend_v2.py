"""Backend Developer V2 service.

Thin configuration over :class:`app.services._staged_agent.StagedAgentService`;
see ``backend_v1.py`` for the rationale behind keeping module-level symbols.
"""

from app.agents.backend_v2 import BackendDeveloperV2Agent
from app.backend_v2.markdown import output_to_markdown
from app.backend_v2.prompt_builder import BackendDeveloperV2PromptBuilder
from app.backend_v2.validator import BackendDeveloperV2Validator
from app.core.logging import get_logger
from app.models.backend_v1 import BackendV1RunStatus
from app.models.backend_v2 import BackendV2RunStatus
from app.repositories.backend_v1 import BackendV1RunRepository
from app.repositories.backend_v2 import BackendV2ArtifactRepository, BackendV2RunRepository
from app.schemas.backend_v2 import (
    BackendV2ArtifactResponse,
    BackendV2RunListResponse,
    BackendV2RunResponse,
)
from app.services._staged_agent import PreviousStageConfig, StageConfig, StagedAgentService
from app.tenancy.guards import get_backend_v2_run_for_org

logger = get_logger(__name__)


BACKEND_V2_CONFIG = StageConfig(
    stage="backend_v2",
    self_label="Backend Developer V2",
    run_status_enum=BackendV2RunStatus,
    run_repo_cls=BackendV2RunRepository,
    artifact_repo_cls=BackendV2ArtifactRepository,
    response_cls=BackendV2RunResponse,
    artifact_response_cls=BackendV2ArtifactResponse,
    list_response_cls=BackendV2RunListResponse,
    artifact_model_name="BackendV2Artifact",
    agent_cls=BackendDeveloperV2Agent,
    validator_cls=BackendDeveloperV2Validator,
    prompt_builder_cls=BackendDeveloperV2PromptBuilder,
    to_markdown=output_to_markdown,
    get_run_for_org=get_backend_v2_run_for_org,
    previous=PreviousStageConfig(
        label="Backend Developer V1",
        model_name="BackendV1Run",
        repo_cls=BackendV1RunRepository,
        status_enum=BackendV1RunStatus,
        run_id_field="backend_v1_run_id",
        agent_output_kwarg="backend_v1_output",
    ),
)


class BackendDeveloperV2Service(StagedAgentService):
    config = BACKEND_V2_CONFIG
