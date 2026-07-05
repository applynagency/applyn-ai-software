from sqlalchemy.ext.asyncio import AsyncSession

from app.models.frontend_v2 import FrontendV2Artifact, FrontendV2Run
from app.repositories._staged import StagedArtifactRepository, StagedRunRepository


class FrontendV2RunRepository(StagedRunRepository[FrontendV2Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendV2Run, session)


class FrontendV2ArtifactRepository(StagedArtifactRepository[FrontendV2Artifact]):
    run_model = FrontendV2Run

    def __init__(self, session: AsyncSession):
        super().__init__(FrontendV2Artifact, session)
