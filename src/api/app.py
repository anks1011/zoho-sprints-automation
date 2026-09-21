"""FastAPI application factory and middleware configuration."""

from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.auth import router as auth_router
from src.api.routes.executions import router as executions_router
from src.api.routes.plans import router as plans_router
from src.api.routes.stories import router as stories_router
from src.config import get_settings
from src.logging_config import setup_logging

# Ensure logging and secret-masking filters are active
settings = get_settings()
setup_logging(log_level=settings.log_level)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zoho Sprints AI Task Automation API",
    description="Backend REST API powering the Zoho Sprints AI Task Automation Web UI.",
    version="0.1.0",
)

# Configure CORS for Next.js frontend (default ports 3000, 3001)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stories_router, prefix="/api/v1")
app.include_router(plans_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
def health_check() -> dict:
    """Service health check."""
    return {
        "status": "healthy",
        "service": "zoho-sprints-automation-api",
        "version": "0.1.0",
    }
