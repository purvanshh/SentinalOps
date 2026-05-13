import structlog
from core.config import get_settings
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def permission_exception_handler(_: Request, exc: PermissionError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    content: dict = {"detail": "Internal server error"}
    if not get_settings().is_production:
        content["error"] = str(exc)
    return JSONResponse(status_code=500, content=content)
