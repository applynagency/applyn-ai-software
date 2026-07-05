from sqlalchemy.ext.asyncio import AsyncSession

from app.models.frontend_v1 import FrontendV1Artifact, FrontendV1Run
from app.repositories._staged import StagedArtifactRepository, StagedRunRepository


class FrontendV1RunRepository(StagedRunRepository[FrontendV1Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendV1Run, session)


class FrontendV1ArtifactRepository(StagedArtifactRepository[FrontendV1Artifact]):
    run_model = FrontendV1Run

    def __init__(self, session: AsyncSession):
        super().__init__(FrontendV1Artifact, session)
