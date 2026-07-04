from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    data: Any | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    detail: str
    error_type: str | None = None
