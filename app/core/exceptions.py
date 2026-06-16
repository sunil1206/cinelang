"""Custom exceptions and FastAPI exception handlers."""
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


# ── Domain exceptions ─────────────────────────────────────────────────────────

class CineLangError(Exception):
    """Base error — carries an HTTP status code and structured detail."""
    status_code: int = 500
    code:        str = "internal_error"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class AuthError(CineLangError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code        = "auth_error"


class ForbiddenError(CineLangError):
    status_code = status.HTTP_403_FORBIDDEN
    code        = "forbidden"


class NotFoundError(CineLangError):
    status_code = status.HTTP_404_NOT_FOUND
    code        = "not_found"


class ConflictError(CineLangError):
    status_code = status.HTTP_409_CONFLICT
    code        = "conflict"


class ServiceUnavailableError(CineLangError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code        = "service_unavailable"


class BadGatewayError(CineLangError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code        = "bad_gateway"


# ── Error envelope ────────────────────────────────────────────────────────────

def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


# ── Handlers ──────────────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(CineLangError)
    async def cinelang_error_handler(request: Request, exc: CineLangError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(f"http_{exc.status_code}", exc.detail or ""),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "validation_error",
                "Request validation failed",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "An unexpected error occurred"),
        )
