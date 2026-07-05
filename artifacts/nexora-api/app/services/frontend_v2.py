"""Frontend Developer V2 service.

Thin configuration over :class:`app.services._staged_agent.StagedAgentService`;
see ``backend_v1.py`` for the rationale behind keeping module-level symbols.
"""

from app.agents.frontend_v2 import FrontendDeveloperV2Agent
from app.core.logging import get_logger
from app.frontend_v2.markdown import output_to_markdown
from app.frontend_v2.prompt_builder import FrontendDeveloperV2PromptBuilder
from app.frontend_v2.validator import FrontendDeveloperV2Validator
from app.models.frontend_v1 import FrontendV1RunStatus
from app.models.frontend_v2 import FrontendV2RunStatus
from app.repositories.frontend_v1 import FrontendV1RunRepository
from app.repositories.frontend_v2 import FrontendV2ArtifactRepository, FrontendV2RunRepository
from app.schemas.frontend_v2 import (
    FrontendV2ArtifactResponse,
    FrontendV2RunListResponse,
    FrontendV2RunResponse,
)
from app.services._staged_agent import PreviousStageConfig, StageConfig, StagedAgentService
from app.tenancy.guards import get_frontend_v2_run_for_org

logger = get_logger(__name__)


FRONTEND_V2_CONFIG = StageConfig(
    stage="frontend_v2",
    self_label="Frontend Developer V2",
    run_status_enum=FrontendV2RunStatus,
    run_repo_cls=FrontendV2RunRepository,
    artifact_repo_cls=FrontendV2ArtifactRepository,
    response_cls=FrontendV2RunResponse,
    artifact_response_cls=FrontendV2ArtifactResponse,
    list_response_cls=FrontendV2RunListResponse,
    artifact_model_name="FrontendV2Artifact",
    agent_cls=FrontendDeveloperV2Agent,
    validator_cls=FrontendDeveloperV2Validator,
    prompt_builder_cls=FrontendDeveloperV2PromptBuilder,
    to_markdown=output_to_markdown,
    get_run_for_org=get_frontend_v2_run_for_org,
    previous=PreviousStageConfig(
        label="Frontend Developer V1",
        model_name="FrontendV1Run",
        repo_cls=FrontendV1RunRepository,
        status_enum=FrontendV1RunStatus,
        run_id_field="frontend_v1_run_id",
        agent_output_kwarg="frontend_v1_output",
    ),
)


class FrontendDeveloperV2Service(StagedAgentService):
    config = FRONTEND_V2_CONFIG
