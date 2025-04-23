"""Prometheus metrics configuration and middleware."""

import time
from collections.abc import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code", "status_class"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_class"]
)

ACTIVE_CONNECTIONS = Gauge(
    "http_active_connections",
    "Number of active HTTP connections"
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics with enhanced observability."""

    def __init__(self, app, app_name: str = "healthcare_api"):
        super().__init__(app)
        self.app_name = app_name

    def _get_endpoint_label(self, path: str) -> str:
        """Normalize endpoint path for metrics labels."""
        # Remove UUIDs and IDs from paths for better aggregation
        import re
        # Replace UUIDs with {id}
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        # Replace other numeric IDs with {id}
        path = re.sub(r'/\d+', '/{id}', path)
        return path

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics with enhanced observability."""
        if not settings.prometheus_enabled:
            return await call_next(request)

        # Increment active connections
        ACTIVE_CONNECTIONS.inc()

        # Get request details
        method = request.method
        path = request.url.path
        endpoint = self._get_endpoint_label(path)
        
        # Get request ID from state (set by RequestIDMiddleware)
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Start timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics with enhanced labels
            status_code = str(response.status_code)
            duration = time.time() - start_time
            
            # Determine status class for better aggregation
            status_class = f"{status_code[0]}xx" if len(status_code) >= 3 else "unknown"
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                status_class=status_class
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                status_class=status_class
            ).observe(duration)
            
            # Enhanced structured logging
            logger.info(
                "HTTP request completed",
                method=method,
                path=path,
                endpoint=endpoint,
                status_code=status_code,
                status_class=status_class,
                duration_seconds=round(duration, 4),
                duration_ms=round(duration * 1000, 2),
                request_id=request_id
            )
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            status_code = "500"
            status_class = "5xx"
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                status_class=status_class
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                status_class=status_class
            ).observe(duration)
            
            # Enhanced error logging
            logger.error(
                "HTTP request failed",
                method=method,
                path=path,
                endpoint=endpoint,
                status_code=status_code,
                status_class=status_class,
                duration_seconds=round(duration, 4),
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                error_type=type(e).__name__,
                request_id=request_id
            )
            
            raise
            
        finally:
            # Decrement active connections
            ACTIVE_CONNECTIONS.dec()


def get_metrics() -> str:
    """Get Prometheus metrics in text format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST