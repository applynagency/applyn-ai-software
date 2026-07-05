from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import NexoraException, ValidationError
from app.core.logging import get_logger
from app.lifecycle.customer_messages import translate_customer_error

logger = get_logger(__name__)


def _is_customer_lifecycle_path(path: str) -> bool:
    normalized = path.split("?")[0]
    if normalized.startswith("/nexora-api"):
        normalized = normalized[len("/nexora-api") :]
    customer_prefixes = (
        "/v1/agents/deployment",
        "/v1/change-requests",
        "/v1/regeneration",
        "/v1/releases",
        "/v1/agents/approval",
        "/v1/agents/fullstack-assembly",
    )
    return any(normalized.startswith(prefix) for prefix in customer_prefixes)


async def nexora_exception_handler(request: Request, exc: NexoraException) -> JSONResponse:
    message = exc.message
    if isinstance(exc, ValidationError) and _is_customer_lifecycle_path(request.url.path):
        message = translate_customer_error(exc.message)

    logger.warning(
        "handled_exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        message=exc.message,
    )
    content: dict = {"detail": message, "error_type": type(exc).__name__}
    if exc.details:
        content["details"] = exc.details
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:]) if len(error["loc"]) > 1 else "body"
        errors.append({"field": field, "message": error["msg"], "type": error["type"]})

    logger.warning(
        "validation_error",
        path=request.url.path,
        method=request.method,
        errors=errors,
    )

    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"},
    )
