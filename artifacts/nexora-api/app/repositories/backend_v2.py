from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backend_v2 import BackendV2Artifact, BackendV2Run
from app.repositories._staged import StagedArtifactRepository, StagedRunRepository


class BackendV2RunRepository(StagedRunRepository[BackendV2Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendV2Run, session)


class BackendV2ArtifactRepository(StagedArtifactRepository[BackendV2Artifact]):
    run_model = BackendV2Run

    def __init__(self, session: AsyncSession):
        super().__init__(BackendV2Artifact, session)
