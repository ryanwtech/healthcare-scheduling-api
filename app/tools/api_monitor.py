"""API monitoring and debugging tools for better developer experience."""

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque

import httpx
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RequestMetrics:
    """Request metrics container."""
    method: str
    path: str
    status_code: int
    response_time: float
    timestamp: datetime
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class APIMetrics:
    """API metrics container."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    requests_per_minute: float = 0.0
    error_rate: float = 0.0
    status_codes: Dict[int, int] = field(default_factory=dict)
    endpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    recent_requests: deque = field(default_factory=lambda: deque(maxlen=100))


class APIMonitor:
    """API monitoring utility."""
    
    def __init__(self, max_history: int = 1000):
        self.metrics = APIMetrics()
        self.request_history: deque = deque(maxlen=max_history)
        self.start_time = datetime.now(timezone.utc)
        self.monitoring_enabled = True
    
    def record_request(self, metrics: RequestMetrics):
        """Record a request metric."""
        if not self.monitoring_enabled:
            return
        
        self.request_history.append(metrics)
        self._update_metrics(metrics)
    
    def _update_metrics(self, metrics: RequestMetrics):
        """Update aggregated metrics."""
        self.metrics.total_requests += 1
        
        if 200 <= metrics.status_code < 400:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        # Update status code counts
        self.metrics.status_codes[metrics.status_code] = self.metrics.status_codes.get(metrics.status_code, 0) + 1
        
        # Update endpoint metrics
        endpoint_key = f"{metrics.method} {metrics.path}"
        if endpoint_key not in self.metrics.endpoints:
            self.metrics.endpoints[endpoint_key] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_response_time": 0.0,
                "average_response_time": 0.0,
                "last_request": None
            }
        
        endpoint_metrics = self.metrics.endpoints[endpoint_key]
        endpoint_metrics["total_requests"] += 1
        endpoint_metrics["total_response_time"] += metrics.response_time
        endpoint_metrics["average_response_time"] = endpoint_metrics["total_response_time"] / endpoint_metrics["total_requests"]
        endpoint_metrics["last_request"] = metrics.timestamp
        
        if 200 <= metrics.status_code < 400:
            endpoint_metrics["successful_requests"] += 1
        else:
            endpoint_metrics["failed_requests"] += 1
        
        # Update global metrics
        self._calculate_global_metrics()
    
    def _calculate_global_metrics(self):
        """Calculate global metrics."""
        if self.metrics.total_requests == 0:
            return
        
        # Calculate average response time
        total_response_time = sum(r.response_time for r in self.request_history)
        self.metrics.average_response_time = total_response_time / len(self.request_history)
        
        # Calculate success rate
        self.metrics.error_rate = (self.metrics.failed_requests / self.metrics.total_requests) * 100
        
        # Calculate requests per minute
        now = datetime.now(timezone.utc)
        time_diff = (now - self.start_time).total_seconds() / 60
        self.metrics.requests_per_minute = self.metrics.total_requests / time_diff if time_diff > 0 else 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "average_response_time": round(self.metrics.average_response_time, 3),
            "requests_per_minute": round(self.metrics.requests_per_minute, 2),
            "error_rate": round(self.metrics.error_rate, 2),
            "status_codes": dict(self.metrics.status_codes),
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            "endpoints": {
                endpoint: {
                    **metrics,
                    "average_response_time": round(metrics["average_response_time"], 3)
                }
                for endpoint, metrics in self.metrics.endpoints.items()
            }
        }
    
    def get_recent_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent requests."""
        return [
            {
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "response_time": round(r.response_time, 3),
                "timestamp": r.timestamp.isoformat(),
                "user_id": r.user_id,
                "request_id": r.request_id,
                "error_message": r.error_message
            }
            for r in list(self.request_history)[-limit:]
        ]
    
    def get_error_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error requests."""
        error_requests = [r for r in self.request_history if r.status_code >= 400]
        return [
            {
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "response_time": round(r.response_time, 3),
                "timestamp": r.timestamp.isoformat(),
                "user_id": r.user_id,
                "request_id": r.request_id,
                "error_message": r.error_message
            }
            for r in error_requests[-limit:]
        ]
    
    def get_slow_requests(self, threshold: float = 1.0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get slow requests."""
        slow_requests = [r for r in self.request_history if r.response_time > threshold]
        return [
            {
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "response_time": round(r.response_time, 3),
                "timestamp": r.timestamp.isoformat(),
                "user_id": r.user_id,
                "request_id": r.request_id
            }
            for r in slow_requests[-limit:]
        ]
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = APIMetrics()
        self.request_history.clear()
        self.start_time = datetime.now(timezone.utc)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring API requests."""
    
    def __init__(self, app, monitor: APIMonitor):
        super().__init__(app)
        self.monitor = monitor
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract request information
        method = request.method
        path = request.url.path
        user_id = getattr(request.state, 'user_id', None)
        request_id = getattr(request.state, 'request_id', None)
        
        # Process request
        try:
            response = await call_next(request)
            response_time = time.time() - start_time
            
            # Record metrics
            metrics = RequestMetrics(
                method=method,
                path=path,
                status_code=response.status_code,
                response_time=response_time,
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                request_id=request_id
            )
            
            self.monitor.record_request(metrics)
            
            return response
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # Record error metrics
            metrics = RequestMetrics(
                method=method,
                path=path,
                status_code=500,
                response_time=response_time,
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                request_id=request_id,
                error_message=str(e)
            )
            
            self.monitor.record_request(metrics)
            
            raise


class APIDebugger:
    """API debugging utility."""
    
    def __init__(self, monitor: APIMonitor):
        self.monitor = monitor
        self.debug_mode = False
        self.debug_requests: List[Dict[str, Any]] = []
    
    def enable_debug_mode(self):
        """Enable debug mode."""
        self.debug_mode = True
        logger.info("API debug mode enabled")
    
    def disable_debug_mode(self):
        """Disable debug mode."""
        self.debug_mode = False
        logger.info("API debug mode disabled")
    
    def debug_request(self, request: Request, response: Response, response_time: float):
        """Debug a request."""
        if not self.debug_mode:
            return
        
        debug_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "status_code": response.status_code,
            "response_time": response_time,
            "user_id": getattr(request.state, 'user_id', None),
            "request_id": getattr(request.state, 'request_id', None)
        }
        
        self.debug_requests.append(debug_info)
        
        # Log debug information
        logger.debug(f"Request debug: {json.dumps(debug_info, indent=2)}")
    
    def get_debug_info(self, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get debug information."""
        if request_id:
            return [req for req in self.debug_requests if req.get('request_id') == request_id]
        return self.debug_requests[-50:]  # Return last 50 requests
    
    def clear_debug_info(self):
        """Clear debug information."""
        self.debug_requests.clear()


class HealthChecker:
    """Health check utility."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=5.0)
    
    async def check_health(self) -> Dict[str, Any]:
        """Check API health."""
        try:
            start_time = time.time()
            response = await self.client.get(f"{self.base_url}/api/v1/health")
            response_time = time.time() - start_time
            
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time": round(response_time, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def check_dependencies(self) -> Dict[str, Any]:
        """Check API dependencies."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/health")
            if response.status_code == 200:
                data = response.json()
                return data.get("dependencies", {})
            return {"error": "Health check failed"}
        except Exception as e:
            return {"error": str(e)}
    
    async def check_endpoints(self, endpoints: List[str]) -> Dict[str, Any]:
        """Check multiple endpoints."""
        results = {}
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = await self.client.get(f"{self.base_url}{endpoint}")
                response_time = time.time() - start_time
                
                results[endpoint] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "response_time": round(response_time, 3)
                }
            except Exception as e:
                results[endpoint] = {
                    "status": "unreachable",
                    "error": str(e)
                }
        
        return results
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class PerformanceAnalyzer:
    """Performance analysis utility."""
    
    def __init__(self, monitor: APIMonitor):
        self.monitor = monitor
    
    def analyze_performance(self, time_window: int = 60) -> Dict[str, Any]:
        """Analyze performance over time window."""
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(seconds=time_window)
        
        # Filter requests within time window
        recent_requests = [
            r for r in self.monitor.request_history
            if r.timestamp >= cutoff_time
        ]
        
        if not recent_requests:
            return {"error": "No requests in time window"}
        
        # Calculate metrics
        total_requests = len(recent_requests)
        successful_requests = len([r for r in recent_requests if 200 <= r.status_code < 400])
        failed_requests = total_requests - successful_requests
        
        response_times = [r.response_time for r in recent_requests]
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Calculate percentiles
        sorted_response_times = sorted(response_times)
        p50 = sorted_response_times[int(len(sorted_response_times) * 0.5)]
        p90 = sorted_response_times[int(len(sorted_response_times) * 0.9)]
        p95 = sorted_response_times[int(len(sorted_response_times) * 0.95)]
        p99 = sorted_response_times[int(len(sorted_response_times) * 0.99)]
        
        # Group by endpoint
        endpoint_stats = defaultdict(list)
        for r in recent_requests:
            endpoint_key = f"{r.method} {r.path}"
            endpoint_stats[endpoint_key].append(r.response_time)
        
        endpoint_analysis = {}
        for endpoint, times in endpoint_stats.items():
            endpoint_analysis[endpoint] = {
                "request_count": len(times),
                "average_response_time": round(sum(times) / len(times), 3),
                "min_response_time": round(min(times), 3),
                "max_response_time": round(max(times), 3)
            }
        
        return {
            "time_window_seconds": time_window,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": round((successful_requests / total_requests) * 100, 2),
            "response_times": {
                "average": round(avg_response_time, 3),
                "min": round(min_response_time, 3),
                "max": round(max_response_time, 3),
                "p50": round(p50, 3),
                "p90": round(p90, 3),
                "p95": round(p95, 3),
                "p99": round(p99, 3)
            },
            "endpoints": endpoint_analysis
        }
    
    def get_slow_endpoints(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """Get slow endpoints."""
        endpoint_times = defaultdict(list)
        
        for r in self.monitor.request_history:
            endpoint_key = f"{r.method} {r.path}"
            endpoint_times[endpoint_key].append(r.response_time)
        
        slow_endpoints = []
        for endpoint, times in endpoint_times.items():
            avg_time = sum(times) / len(times)
            if avg_time > threshold:
                slow_endpoints.append({
                    "endpoint": endpoint,
                    "average_response_time": round(avg_time, 3),
                    "request_count": len(times),
                    "max_response_time": round(max(times), 3)
                })
        
        return sorted(slow_endpoints, key=lambda x: x["average_response_time"], reverse=True)
    
    def get_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns."""
        error_requests = [r for r in self.monitor.request_history if r.status_code >= 400]
        
        if not error_requests:
            return {"error": "No error requests found"}
        
        # Group by status code
        status_code_counts = defaultdict(int)
        for r in error_requests:
            status_code_counts[r.status_code] += 1
        
        # Group by endpoint
        endpoint_errors = defaultdict(int)
        for r in error_requests:
            endpoint_key = f"{r.method} {r.path}"
            endpoint_errors[endpoint_key] += 1
        
        # Group by error message
        error_messages = defaultdict(int)
        for r in error_requests:
            if r.error_message:
                error_messages[r.error_message] += 1
        
        return {
            "total_errors": len(error_requests),
            "status_codes": dict(status_code_counts),
            "endpoints": dict(endpoint_errors),
            "error_messages": dict(error_messages)
        }


# Global monitor instance
api_monitor = APIMonitor()
api_debugger = APIDebugger(api_monitor)
performance_analyzer = PerformanceAnalyzer(api_monitor)
