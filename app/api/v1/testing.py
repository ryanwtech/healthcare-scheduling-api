"""API testing and debugging endpoints for developers."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.security import get_current_user, role_required
from app.db.base import get_db
from app.db.models import User, UserRole
from app.tools.api_monitor import api_monitor, api_debugger, performance_analyzer
from app.tools.api_testing import APITestSuite, create_comprehensive_test_suite, create_smoke_test_suite
from app.tools.sdk_generator import SDKGenerator

router = APIRouter()


class TestRequest(BaseModel):
    """Test execution request."""
    test_type: str = "smoke"  # smoke, comprehensive, load
    base_url: str = "http://localhost:8000"
    concurrent_users: Optional[int] = 10
    requests_per_user: Optional[int] = 10


class TestResponse(BaseModel):
    """Test execution response."""
    test_id: str
    test_type: str
    status: str
    results: Dict
    timestamp: datetime


@router.get("/metrics")
async def get_api_metrics(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get API metrics (admin only)."""
    try:
        metrics = api_monitor.get_metrics()
        return {
            "success": True,
            "data": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/metrics/recent-requests")
async def get_recent_requests(
    limit: int = 50,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get recent API requests (admin only)."""
    try:
        recent_requests = api_monitor.get_recent_requests(limit)
        return {
            "success": True,
            "data": recent_requests,
            "count": len(recent_requests),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent requests: {str(e)}"
        )


@router.get("/metrics/error-requests")
async def get_error_requests(
    limit: int = 50,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get recent error requests (admin only)."""
    try:
        error_requests = api_monitor.get_error_requests(limit)
        return {
            "success": True,
            "data": error_requests,
            "count": len(error_requests),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get error requests: {str(e)}"
        )


@router.get("/metrics/slow-requests")
async def get_slow_requests(
    threshold: float = 1.0,
    limit: int = 50,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get slow requests (admin only)."""
    try:
        slow_requests = api_monitor.get_slow_requests(threshold, limit)
        return {
            "success": True,
            "data": slow_requests,
            "count": len(slow_requests),
            "threshold": threshold,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get slow requests: {str(e)}"
        )


@router.get("/performance/analysis")
async def get_performance_analysis(
    time_window: int = 60,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get performance analysis (admin only)."""
    try:
        analysis = performance_analyzer.analyze_performance(time_window)
        return {
            "success": True,
            "data": analysis,
            "time_window_seconds": time_window,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance analysis: {str(e)}"
        )


@router.get("/performance/slow-endpoints")
async def get_slow_endpoints(
    threshold: float = 1.0,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get slow endpoints (admin only)."""
    try:
        slow_endpoints = performance_analyzer.get_slow_endpoints(threshold)
        return {
            "success": True,
            "data": slow_endpoints,
            "threshold": threshold,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get slow endpoints: {str(e)}"
        )


@router.get("/performance/error-patterns")
async def get_error_patterns(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get error patterns analysis (admin only)."""
    try:
        error_patterns = performance_analyzer.get_error_patterns()
        return {
            "success": True,
            "data": error_patterns,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get error patterns: {str(e)}"
        )


@router.post("/debug/enable")
async def enable_debug_mode(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Enable debug mode (admin only)."""
    try:
        api_debugger.enable_debug_mode()
        return {
            "success": True,
            "message": "Debug mode enabled",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable debug mode: {str(e)}"
        )


@router.post("/debug/disable")
async def disable_debug_mode(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Disable debug mode (admin only)."""
    try:
        api_debugger.disable_debug_mode()
        return {
            "success": True,
            "message": "Debug mode disabled",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable debug mode: {str(e)}"
        )


@router.get("/debug/info")
async def get_debug_info(
    request_id: Optional[str] = None,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get debug information (admin only)."""
    try:
        debug_info = api_debugger.get_debug_info(request_id)
        return {
            "success": True,
            "data": debug_info,
            "count": len(debug_info),
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get debug info: {str(e)}"
        )


@router.post("/debug/clear")
async def clear_debug_info(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Clear debug information (admin only)."""
    try:
        api_debugger.clear_debug_info()
        return {
            "success": True,
            "message": "Debug information cleared",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear debug info: {str(e)}"
        )


@router.post("/tests/run")
async def run_api_tests(
    test_request: TestRequest,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Run API tests (admin only)."""
    try:
        # Create test suite based on type
        if test_request.test_type == "comprehensive":
            suite = create_comprehensive_test_suite(test_request.base_url)
        elif test_request.test_type == "smoke":
            suite = create_smoke_test_suite(test_request.base_url)
        elif test_request.test_type == "load":
            from app.tools.api_testing import create_load_test_suite
            suite = create_load_test_suite(
                test_request.base_url,
                test_request.concurrent_users or 10,
                test_request.requests_per_user or 10
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid test type: {test_request.test_type}"
            )
        
        # Run tests asynchronously
        async with suite:
            await suite.run_all_tests()
            summary = suite.get_summary()
        
        test_id = f"test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        return TestResponse(
            test_id=test_id,
            test_type=test_request.test_type,
            status="completed",
            results=summary,
            timestamp=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run tests: {str(e)}"
        )


@router.get("/sdk/generate")
async def generate_sdk(
    language: str = "python",
    base_url: str = "https://api.healthcare.example.com",
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Generate client SDK (admin only)."""
    try:
        generator = SDKGenerator(base_url)
        
        if language == "python":
            generator.generate_python_sdk()
            message = "Python SDK generated successfully"
        elif language == "javascript":
            generator.generate_javascript_sdk()
            message = "JavaScript SDK generated successfully"
        elif language == "curl":
            generator.generate_curl_examples()
            message = "cURL examples generated successfully"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language: {language}"
            )
        
        return {
            "success": True,
            "message": message,
            "language": language,
            "base_url": base_url,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SDK: {str(e)}"
        )


@router.get("/health/detailed")
async def detailed_health_check(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get detailed health check (admin only)."""
    try:
        from app.tools.api_monitor import HealthChecker
        
        async with HealthChecker() as health_checker:
            health_status = await health_checker.check_health()
            dependencies = await health_checker.check_dependencies()
            
            # Check key endpoints
            key_endpoints = [
                "/api/v2/health",
                "/api/v2/users/me",
                "/api/v2/appointments",
                "/api/v2/notifications"
            ]
            endpoint_status = await health_checker.check_endpoints(key_endpoints)
        
        return {
            "success": True,
            "data": {
                "api_status": health_status,
                "dependencies": dependencies,
                "endpoints": endpoint_status,
                "metrics": api_monitor.get_metrics()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detailed health check: {str(e)}"
        )


@router.get("/status")
async def get_api_status(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    request: Request = None
):
    """Get comprehensive API status (admin only)."""
    try:
        metrics = api_monitor.get_metrics()
        recent_requests = api_monitor.get_recent_requests(10)
        error_requests = api_monitor.get_error_requests(10)
        
        return {
            "success": True,
            "data": {
                "api_status": "operational",
                "metrics": metrics,
                "recent_activity": {
                    "recent_requests": recent_requests,
                    "error_requests": error_requests
                },
                "debug_mode": api_debugger.debug_mode,
                "monitoring_enabled": api_monitor.monitoring_enabled
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get API status: {str(e)}"
        )
