"""Frontend Developer V3 service.

Thin configuration over :class:`app.services._staged_agent.StagedAgentService`;
see ``backend_v1.py`` for the rationale behind keeping module-level symbols.
"""

from app.agents.frontend_v3 import FrontendDeveloperV3Agent
from app.core.logging import get_logger
from app.frontend_v3.markdown import output_to_markdown
from app.frontend_v3.prompt_builder import FrontendDeveloperV3PromptBuilder
from app.frontend_v3.validator import FrontendDeveloperV3Validator
from app.models.frontend_v2 import FrontendV2RunStatus
from app.models.frontend_v3 import FrontendV3RunStatus
from app.repositories.frontend_v2 import FrontendV2RunRepository
from app.repositories.frontend_v3 import FrontendV3ArtifactRepository, FrontendV3RunRepository
from app.schemas.frontend_v3 import (
    FrontendV3ArtifactResponse,
    FrontendV3RunListResponse,
    FrontendV3RunResponse,
)
from app.services._staged_agent import PreviousStageConfig, StageConfig, StagedAgentService
from app.tenancy.guards import get_frontend_v3_run_for_org

logger = get_logger(__name__)


FRONTEND_V3_CONFIG = StageConfig(
    stage="frontend_v3",
    self_label="Frontend Developer V3",
    run_status_enum=FrontendV3RunStatus,
    run_repo_cls=FrontendV3RunRepository,
    artifact_repo_cls=FrontendV3ArtifactRepository,
    response_cls=FrontendV3RunResponse,
    artifact_response_cls=FrontendV3ArtifactResponse,
    list_response_cls=FrontendV3RunListResponse,
    artifact_model_name="FrontendV3Artifact",
    agent_cls=FrontendDeveloperV3Agent,
    validator_cls=FrontendDeveloperV3Validator,
    prompt_builder_cls=FrontendDeveloperV3PromptBuilder,
    to_markdown=output_to_markdown,
    get_run_for_org=get_frontend_v3_run_for_org,
    previous=PreviousStageConfig(
        label="Frontend Developer V2",
        model_name="FrontendV2Run",
        repo_cls=FrontendV2RunRepository,
        status_enum=FrontendV2RunStatus,
        run_id_field="frontend_v2_run_id",
        agent_output_kwarg="frontend_v2_output",
    ),
)


class FrontendDeveloperV3Service(StagedAgentService):
    config = FRONTEND_V3_CONFIG
