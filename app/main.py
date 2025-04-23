"""Main FastAPI application."""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1 import api_router
from app.api.v1.health_checks import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, log_error
from app.core.openapi import custom_openapi, add_enhanced_docs_routes
from app.core.performance import PerformanceMiddleware, resource_monitor
from app.core.exceptions import (
    api_exception_handler,
    validation_exception_handler,
    pydantic_validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
)
from app.core.versioning import VersionMiddleware
from app.observability.metrics import PrometheusMiddleware, get_metrics_content_type
from app.security.headers import (
    HIPAAComplianceMiddleware,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
)
from app.tools.api_monitor import MonitoringMiddleware, api_monitor

# Set timezone to UTC
os.environ["TZ"] = "UTC"

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Track application start time
app_start_time = time.time()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to requests."""

    async def dispatch(self, request: Request, call_next):
        """Add request ID to request and response headers."""
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            import uuid
            request_id = str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to enrich logs with request context."""

    async def dispatch(self, request: Request, call_next):
        """Enrich logs with request_id and user_id context."""
        from app.core.logging import structlog
        
        # Get request ID from state
        request_id = getattr(request.state, 'request_id', None)
        
        # Set up context variables for this request
        context_vars = {}
        if request_id:
            context_vars['request_id'] = request_id
        
        # Try to get user_id from request state (set by auth middleware)
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            context_vars['user_id'] = str(user_id)
        
        # Bind context to structlog for this request
        with structlog.contextvars.bound_contextvars(**context_vars):
            response = await call_next(request)
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Healthcare Scheduling API", version="0.1.0")
    yield
    # Shutdown
    logger.info("Shutting down Healthcare Scheduling API")


# Create FastAPI application
app = FastAPI(
    title="Healthcare Scheduling API",
    version="2.0.0",
    description="A comprehensive API for healthcare appointment scheduling and management",
    openapi_url="/openapi.json",
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    lifespan=lifespan,
)

# Set custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)

# Add monitoring middleware
app.add_middleware(MonitoringMiddleware, monitor=api_monitor)

# Add versioning middleware
app.add_middleware(VersionMiddleware)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware, app_name="healthcare_api")
app.add_middleware(HIPAAComplianceMiddleware)

# Add performance monitoring middleware
app.add_middleware(PerformanceMiddleware, max_response_time=5.0)

# Add HTTPS redirect in production
if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)

# Add Prometheus metrics middleware if enabled
if settings.prometheus_enabled:
    app.add_middleware(PrometheusMiddleware, app_name="healthcare_api")

# Add exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValueError, general_exception_handler)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Include health check router
app.include_router(health_router, prefix="/api/v1", tags=["health"])

# Add enhanced documentation routes
add_enhanced_docs_routes(app)


@app.get("/health")
async def health_check():
    """Health check endpoint with uptime."""
    uptime = time.time() - app_start_time
    return {
        "status": "ok",
        "message": "Healthcare Scheduling API is running",
        "uptime_seconds": round(uptime, 2),
        "version": "0.1.0",
        "environment": settings.env,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.prometheus_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics not enabled"
        )
    
    from prometheus_client import generate_latest
    return Response(
        content=generate_latest(),
        media_type=get_metrics_content_type()
    )


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured logging."""
    request_id = getattr(request.state, "request_id", None)
    
    log_error(
        logger,
        exc,
        request_id,
        {
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    request_id = getattr(request.state, "request_id", None)
    
    log_error(
        logger,
        exc,
        request_id,
        {
            "validation_errors": exc.errors(),
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Validation error",
                "details": exc.errors(),
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    request_id = getattr(request.state, "request_id", None)
    
    log_error(
        logger,
        exc,
        request_id,
        {
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
