"""Admin-only API routes for system management and testing."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.logging import get_logger
from app.core.security import get_current_user, role_required
from app.db.models import User, UserRole

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/admin/log-test",
    summary="Test structured logging",
    description="Emit sample structured logs for verification (admin only)."
)
async def test_structured_logging(
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> dict:
    """
    Test structured logging by emitting various log levels with context.
    
    This endpoint helps verify that:
    - All logs are JSON formatted
    - Logs include level, msg, ts, request_id
    - User context is properly included
    - Different log levels work correctly
    """
    test_id = str(uuid.uuid4())
    
    # Test different log levels with structured data
    logger.debug(
        "Admin log test - debug level",
        test_id=test_id,
        action="log_test",
        level="debug",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    logger.info(
        "Admin log test - info level",
        test_id=test_id,
        action="log_test",
        level="info",
        user_email=current_user.email,
        user_role=current_user.role.value if hasattr(current_user, 'role') else 'unknown',
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    logger.warning(
        "Admin log test - warning level",
        test_id=test_id,
        action="log_test",
        level="warning",
        warning_type="test_warning",
        message="This is a test warning message",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    logger.error(
        "Admin log test - error level",
        test_id=test_id,
        action="log_test",
        level="error",
        error_type="test_error",
        error_message="This is a test error message",
        error_code="TEST_ERROR_001",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    # Test with nested context
    logger.info(
        "Admin log test - nested context",
        test_id=test_id,
        action="log_test",
        level="info",
        context={
            "nested_data": {
                "key1": "value1",
                "key2": "value2",
                "numbers": [1, 2, 3, 4, 5],
                "boolean": True,
                "null_value": None
            },
            "array_data": ["item1", "item2", "item3"],
            "metadata": {
                "version": "1.0.0",
                "environment": "test"
            }
        },
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    # Test performance logging
    import time
    start_time = time.time()
    time.sleep(0.1)  # Simulate some work
    duration = time.time() - start_time
    
    logger.info(
        "Admin log test - performance metrics",
        test_id=test_id,
        action="log_test",
        level="info",
        performance={
            "duration_seconds": round(duration, 4),
            "duration_ms": round(duration * 1000, 2),
            "operation": "test_operation"
        },
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    return {
        "message": "Structured logging test completed",
        "test_id": test_id,
        "logs_emitted": 6,
        "log_levels": ["debug", "info", "warning", "error"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": str(current_user.id),
        "user_email": current_user.email
    }


@router.get(
    "/admin/system-info",
    summary="Get system information",
    description="Get system information and health status (admin only)."
)
async def get_system_info(
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> dict:
    """Get system information for monitoring and debugging."""
    import os
    import platform
    import sys
    
    logger.info(
        "System info requested",
        user_id=str(current_user.id),
        user_email=current_user.email
    )
    
    return {
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "architecture": platform.architecture()[0],
            "processor": platform.processor()
        },
        "application": {
            "name": "Healthcare Scheduling API",
            "version": "0.1.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timezone": os.getenv("TZ", "UTC")
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
