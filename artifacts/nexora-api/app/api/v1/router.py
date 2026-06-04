from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.workspaces import router as workspace_router
from app.api.v1.projects import router as project_router
from app.api.v1.requirements import router as requirement_router
from app.api.v1.agents import router as agent_router

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth_router)
api_router.include_router(workspace_router)
api_router.include_router(project_router)
api_router.include_router(requirement_router)
api_router.include_router(agent_router)
