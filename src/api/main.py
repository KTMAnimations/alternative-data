"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.core.config import settings
from src.core.database import async_engine

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler."""
    logger.info("Starting Alternative Data Platform", version=settings.app_version)
    yield
    logger.info("Shutting down Alternative Data Platform")
    await async_engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Alternative Data Platform for investment decision-making",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.exception("Unhandled exception", path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


# Import and include routers
from src.api.routes import catalog, factors, alerts, backtest, geo, admin, auth, streaming

app.include_router(auth.router, prefix=f"{settings.api_prefix}/auth", tags=["Authentication"])
app.include_router(catalog.router, prefix=f"{settings.api_prefix}/catalog", tags=["Data Catalog"])
app.include_router(factors.router, prefix=f"{settings.api_prefix}/factors", tags=["Factors"])
app.include_router(alerts.router, prefix=f"{settings.api_prefix}/alerts", tags=["Alerts"])
app.include_router(backtest.router, prefix=f"{settings.api_prefix}/backtest", tags=["Backtesting"])
app.include_router(geo.router, prefix=f"{settings.api_prefix}/geo", tags=["Geographic"])
app.include_router(admin.router, prefix=f"{settings.api_prefix}/admin", tags=["Admin"])
app.include_router(streaming.router, prefix=f"{settings.api_prefix}/stream", tags=["Streaming"])
