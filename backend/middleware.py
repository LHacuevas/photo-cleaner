"""
Custom middleware and error handling
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response format"""
    
    @staticmethod
    def to_dict(message: str, code: str = "INTERNAL_ERROR", details: dict = None):
        response = {
            "error": True,
            "code": code,
            "message": message
        }
        if details:
            response["details"] = details
        return response


async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally"""
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse.to_dict(
            "An unexpected error occurred",
            code="INTERNAL_SERVER_ERROR",
            details={"path": str(request.url)}
        )
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Validation error on {request.url}: {errors}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse.to_dict(
            "Validation error",
            code="VALIDATION_ERROR",
            details={"errors": errors}
        )
    )


class LoggingMiddleware:
    """Middleware to log all requests and responses"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only handle HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Log request
        path = scope.get("path", "")
        method = scope.get("method", "")
        logger.info(f"{method} {path}")

        # Process the request
        await self.app(scope, receive, send)
