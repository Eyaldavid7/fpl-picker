"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.middleware import RequestLoggingMiddleware, register_exception_handlers
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown events.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the application after startup completes.
    """
    settings = get_settings()
    # Startup: ensure cache directory exists
    os.makedirs(settings.cache_dir, exist_ok=True)
    yield
    # Shutdown: cleanup resources if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured FastAPI application instance with middleware,
        exception handlers, and API routes registered.
    """
    settings = get_settings()

    # Configure structured logging before anything else
    setup_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FPL Team Picker - ML-powered Fantasy Premier League assistant",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Global exception handlers
    register_exception_handlers(app)

    # Include API router
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
