from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backend_v3 import BackendV3Artifact, BackendV3Run
from app.repositories._staged import StagedArtifactRepository, StagedRunRepository


class BackendV3RunRepository(StagedRunRepository[BackendV3Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendV3Run, session)


class BackendV3ArtifactRepository(StagedArtifactRepository[BackendV3Artifact]):
    run_model = BackendV3Run

    def __init__(self, session: AsyncSession):
        super().__init__(BackendV3Artifact, session)
