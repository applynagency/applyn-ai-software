import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.exceptions import NexoraException
from app.database.session import create_tables
from app.api.v1.router import api_router
from app.middleware.error_handler import (
    nexora_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.middleware.audit import RequestLoggingMiddleware

configure_logging()
logger = get_logger(__name__)

BASE_PATH = os.environ.get("BASE_PATH", settings.BASE_PATH).rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nexora_startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    await create_tables()
    logger.info("nexora_ready")
    yield
    logger.info("nexora_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url=f"{BASE_PATH}/docs",
    redoc_url=f"{BASE_PATH}/redoc",
    openapi_url=f"{BASE_PATH}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(NexoraException, nexora_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix=BASE_PATH)


@app.get(f"{BASE_PATH}/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
