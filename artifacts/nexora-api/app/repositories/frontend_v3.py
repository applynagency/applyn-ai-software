from sqlalchemy.ext.asyncio import AsyncSession

from app.models.frontend_v3 import FrontendV3Artifact, FrontendV3Run
from app.repositories._staged import StagedArtifactRepository, StagedRunRepository


class FrontendV3RunRepository(StagedRunRepository[FrontendV3Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendV3Run, session)


class FrontendV3ArtifactRepository(StagedArtifactRepository[FrontendV3Artifact]):
    run_model = FrontendV3Run

    def __init__(self, session: AsyncSession):
        super().__init__(FrontendV3Artifact, session)
