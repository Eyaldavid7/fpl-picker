"""Application middleware for error handling and request logging.

Provides:
- Global exception handler that catches unhandled exceptions and returns
  proper JSON error responses with appropriate HTTP status codes.
- Request logging middleware that logs method, path, status code, and
  response time for every incoming request.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application.

    Args:
        app: The FastAPI application instance to register handlers on.
    """

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle ValueError exceptions as 422 Unprocessable Entity.

        Args:
            request: The incoming HTTP request.
            exc: The ValueError that was raised.

        Returns:
            A JSON response with the error detail and a 422 status code.
        """
        logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "type": "validation_error"},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions as 500 Internal Server Error.

        Args:
            request: The incoming HTTP request.
            exc: The unhandled exception.

        Returns:
            A JSON response with a generic error message and a 500 status code.
        """
        logger.exception(
            "Unhandled exception on %s %s: %s",
            request.method,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "type": "internal_error",
            },
        )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every HTTP request with timing information.

    Logs the HTTP method, path, response status code, and elapsed time
    in milliseconds for each request processed by the application.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request, measure timing, and log the result.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler in the chain.

        Returns:
            The HTTP response from downstream handlers.
        """
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "%s %s - 500 (%.1fms) [unhandled exception]",
                method,
                path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "%s %s - %d (%.1fms)",
            method,
            path,
            response.status_code,
            elapsed_ms,
        )
        return response
