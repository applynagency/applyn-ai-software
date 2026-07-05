from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backend_v1 import BackendV1Artifact, BackendV1Run
from app.repositories._staged import StagedArtifactRepository, StagedRunRepository


class BackendV1RunRepository(StagedRunRepository[BackendV1Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendV1Run, session)


class BackendV1ArtifactRepository(StagedArtifactRepository[BackendV1Artifact]):
    run_model = BackendV1Run

    def __init__(self, session: AsyncSession):
        super().__init__(BackendV1Artifact, session)
