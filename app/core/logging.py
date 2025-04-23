"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.stdlib import BoundLogger

from app.core.config import settings


def configure_logging() -> None:
    """Configure structured logging with JSON output."""
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO if not settings.debug else logging.DEBUG,
    )

    # Set log levels for third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def enrich_with_request_id(logger: BoundLogger, request_id: str) -> BoundLogger:
    """Enrich logger with request ID."""
    return logger.bind(request_id=request_id)


def enrich_with_user_id(logger: BoundLogger, user_id: str) -> BoundLogger:
    """Enrich logger with user ID."""
    return logger.bind(user_id=user_id)


def enrich_with_context(logger: BoundLogger, request_id: str = None, user_id: str = None) -> BoundLogger:
    """Enrich logger with request and user context."""
    enriched_logger = logger
    if request_id:
        enriched_logger = enriched_logger.bind(request_id=request_id)
    if user_id:
        enriched_logger = enriched_logger.bind(user_id=user_id)
    return enriched_logger


def log_request(logger: BoundLogger, method: str, path: str, status_code: int, 
                duration: float, request_id: str, user_id: str = None) -> None:
    """Log HTTP request details with enhanced context."""
    logger.info(
        "HTTP request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration * 1000, 2),
        request_id=request_id,
        user_id=user_id
    )


def log_error(logger: BoundLogger, error: Exception, request_id: str = None, 
              user_id: str = None, context: dict[str, Any] = None) -> None:
    """Log error with enhanced context."""
    logger.error(
        "Application error",
        error=str(error),
        error_type=type(error).__name__,
        request_id=request_id,
        user_id=user_id,
        context=context or {}
    )
