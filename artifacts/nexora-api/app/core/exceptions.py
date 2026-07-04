from fastapi import HTTPException, status


class NexoraException(Exception):
    def __init__(self, message: str, status_code: int = 500, details: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(NexoraException):
    def __init__(self, resource: str, resource_id: str = ""):
        msg = f"{resource} not found"
        if resource_id:
            msg = f"{resource} with id '{resource_id}' not found"
        super().__init__(msg, status_code=404)


class ConflictError(NexoraException):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class UnauthorizedError(NexoraException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class ForbiddenError(NexoraException):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403)


class ValidationError(NexoraException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class AgentError(NexoraException):
    def __init__(self, message: str):
        super().__init__(f"Agent execution failed: {message}", status_code=500)


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
