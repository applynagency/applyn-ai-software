"""Frontend Developer V1 service.

Thin configuration over :class:`app.services._staged_agent.StagedAgentService`;
see ``backend_v1.py`` for the rationale behind keeping module-level symbols.
"""

from app.agents.frontend_v1 import FrontendDeveloperV1Agent
from app.core.logging import get_logger
from app.frontend_v1.markdown import output_to_markdown
from app.frontend_v1.prompt_builder import FrontendDeveloperV1PromptBuilder
from app.frontend_v1.validator import FrontendDeveloperV1Validator
from app.models.frontend_architect import FrontendArchitectRunStatus
from app.models.frontend_v1 import FrontendV1RunStatus
from app.repositories.frontend_architect import FrontendArchitectRunRepository
from app.repositories.frontend_v1 import FrontendV1ArtifactRepository, FrontendV1RunRepository
from app.schemas.frontend_v1 import (
    FrontendV1ArtifactResponse,
    FrontendV1RunListResponse,
    FrontendV1RunResponse,
)
from app.services._staged_agent import PreviousStageConfig, StageConfig, StagedAgentService
from app.tenancy.guards import get_frontend_v1_run_for_org

logger = get_logger(__name__)


FRONTEND_V1_CONFIG = StageConfig(
    stage="frontend_v1",
    self_label="Frontend Developer V1",
    run_status_enum=FrontendV1RunStatus,
    run_repo_cls=FrontendV1RunRepository,
    artifact_repo_cls=FrontendV1ArtifactRepository,
    response_cls=FrontendV1RunResponse,
    artifact_response_cls=FrontendV1ArtifactResponse,
    list_response_cls=FrontendV1RunListResponse,
    artifact_model_name="FrontendV1Artifact",
    agent_cls=FrontendDeveloperV1Agent,
    validator_cls=FrontendDeveloperV1Validator,
    prompt_builder_cls=FrontendDeveloperV1PromptBuilder,
    to_markdown=output_to_markdown,
    get_run_for_org=get_frontend_v1_run_for_org,
    previous=PreviousStageConfig(
        label="Frontend Architect",
        model_name="FrontendArchitectRun",
        repo_cls=FrontendArchitectRunRepository,
        status_enum=FrontendArchitectRunStatus,
        run_id_field="frontend_architect_run_id",
        agent_output_kwarg="frontend_architect_output",
    ),
)


class FrontendDeveloperV1Service(StagedAgentService):
    config = FRONTEND_V1_CONFIG
