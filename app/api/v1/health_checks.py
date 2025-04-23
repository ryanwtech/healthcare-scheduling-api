"""Comprehensive health check endpoints for production monitoring."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from redis import Redis
import psutil

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.core.performance import resource_monitor

logger = get_logger(__name__)

router = APIRouter()


class HealthStatus(str, Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class HealthCheck:
    """Individual health check component."""
    
    def __init__(self, name: str, critical: bool = True):
        self.name = name
        self.critical = critical
        self.status = HealthStatus.HEALTHY
        self.message = ""
        self.details = {}
        self.response_time = 0.0
    
    async def check(self) -> None:
        """Override this method to implement specific health checks."""
        pass


class DatabaseHealthCheck(HealthCheck):
    """Database connectivity health check."""
    
    def __init__(self, db: Session):
        super().__init__("database", critical=True)
        self.db = db
    
    async def check(self) -> None:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            result = self.db.execute("SELECT 1").scalar()
            if result != 1:
                raise Exception("Database query returned unexpected result")
            
            # Test connection pool
            pool = self.db.bind.pool
            self.details.update({
                "pool_size": pool.size(),
                "checked_out": pool.checkedout(),
                "checked_in": pool.checkedin(),
                "overflow": pool.overflow()
            })
            
            # Check for long-running queries
            long_queries = self.db.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes'
            """).scalar()
            
            if long_queries > 0:
                self.status = HealthStatus.DEGRADED
                self.message = f"{long_queries} long-running queries detected"
            
            self.response_time = time.time() - start_time
            
        except Exception as e:
            self.status = HealthStatus.CRITICAL
            self.message = f"Database connection failed: {str(e)}"
            self.response_time = time.time() - start_time


class RedisHealthCheck(HealthCheck):
    """Redis connectivity health check."""
    
    def __init__(self, redis_client: Redis):
        super().__init__("redis", critical=True)
        self.redis_client = redis_client
    
    async def check(self) -> None:
        """Check Redis connectivity and performance."""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            result = self.redis_client.ping()
            if not result:
                raise Exception("Redis ping failed")
            
            # Get Redis info
            info = self.redis_client.info()
            self.details.update({
                "version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory": info.get("used_memory_human"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0)
            })
            
            # Calculate hit rate
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            self.details["hit_rate"] = f"{hit_rate:.2f}%"
            
            # Check memory usage
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)
            if max_memory > 0:
                memory_usage = (used_memory / max_memory) * 100
                self.details["memory_usage_percent"] = f"{memory_usage:.2f}%"
                
                if memory_usage > 90:
                    self.status = HealthStatus.CRITICAL
                    self.message = "Redis memory usage critical"
                elif memory_usage > 80:
                    self.status = HealthStatus.DEGRADED
                    self.message = "Redis memory usage high"
            
            self.response_time = time.time() - start_time
            
        except Exception as e:
            self.status = HealthStatus.CRITICAL
            self.message = f"Redis connection failed: {str(e)}"
            self.response_time = time.time() - start_time


class CeleryHealthCheck(HealthCheck):
    """Celery worker health check."""
    
    def __init__(self, redis_client: Redis):
        super().__init__("celery", critical=False)
        self.redis_client = redis_client
    
    async def check(self) -> None:
        """Check Celery worker status."""
        start_time = time.time()
        
        try:
            # Check if Celery workers are registered
            workers = self.redis_client.smembers("celery")
            if not workers:
                self.status = HealthStatus.UNHEALTHY
                self.message = "No Celery workers registered"
                return
            
            self.details["active_workers"] = len(workers)
            self.details["worker_list"] = list(workers)
            
            # Check worker heartbeats
            active_workers = 0
            for worker in workers:
                worker_key = f"celery-worker-heartbeat-{worker.decode()}"
                heartbeat = self.redis_client.get(worker_key)
                if heartbeat:
                    heartbeat_time = float(heartbeat)
                    if time.time() - heartbeat_time < 60:  # 1 minute threshold
                        active_workers += 1
            
            if active_workers == 0:
                self.status = HealthStatus.UNHEALTHY
                self.message = "No active Celery workers"
            elif active_workers < len(workers) / 2:
                self.status = HealthStatus.DEGRADED
                self.message = f"Only {active_workers}/{len(workers)} workers active"
            
            self.response_time = time.time() - start_time
            
        except Exception as e:
            self.status = HealthStatus.UNHEALTHY
            self.message = f"Celery health check failed: {str(e)}"
            self.response_time = time.time() - start_time


class SystemHealthCheck(HealthCheck):
    """System resource health check."""
    
    def __init__(self):
        super().__init__("system", critical=True)
    
    async def check(self) -> None:
        """Check system resources."""
        start_time = time.time()
        
        try:
            # Get system metrics
            metrics = resource_monitor.get_system_metrics()
            
            # CPU usage
            cpu_usage = metrics.get("cpu_usage", 0)
            self.details["cpu_usage"] = f"{cpu_usage:.1f}%"
            
            if cpu_usage > 95:
                self.status = HealthStatus.CRITICAL
                self.message = f"CPU usage critical: {cpu_usage:.1f}%"
            elif cpu_usage > 80:
                self.status = HealthStatus.DEGRADED
                self.message = f"CPU usage high: {cpu_usage:.1f}%"
            
            # Memory usage
            memory_usage = metrics.get("memory_usage", 0)
            self.details["memory_usage"] = f"{memory_usage:.1f}%"
            
            if memory_usage > 95:
                self.status = HealthStatus.CRITICAL
                self.message = f"Memory usage critical: {memory_usage:.1f}%"
            elif memory_usage > 80:
                self.status = HealthStatus.DEGRADED
                self.message = f"Memory usage high: {memory_usage:.1f}%"
            
            # Disk usage
            disk_usage = metrics.get("disk_usage", 0)
            self.details["disk_usage"] = f"{disk_usage:.1f}%"
            
            if disk_usage > 95:
                self.status = HealthStatus.CRITICAL
                self.message = f"Disk usage critical: {disk_usage:.1f}%"
            elif disk_usage > 80:
                self.status = HealthStatus.DEGRADED
                self.message = f"Disk usage high: {disk_usage:.1f}%"
            
            self.response_time = time.time() - start_time
            
        except Exception as e:
            self.status = HealthStatus.UNHEALTHY
            self.message = f"System health check failed: {str(e)}"
            self.response_time = time.time() - start_time


class HealthChecker:
    """Main health checker coordinator."""
    
    def __init__(self, db: Session, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client
        self.checks = [
            DatabaseHealthCheck(db),
            RedisHealthCheck(redis_client),
            CeleryHealthCheck(redis_client),
            SystemHealthCheck()
        ]
    
    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        start_time = time.time()
        
        # Run all checks concurrently
        await asyncio.gather(*[check.check() for check in self.checks])
        
        # Determine overall status
        critical_failures = [c for c in self.checks if c.status == HealthStatus.CRITICAL]
        degraded_checks = [c for c in self.checks if c.status == HealthStatus.DEGRADED]
        unhealthy_checks = [c for c in self.checks if c.status == HealthStatus.UNHEALTHY]
        
        if critical_failures:
            overall_status = HealthStatus.CRITICAL
        elif unhealthy_checks:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_checks:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Build response
        response = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time": time.time() - start_time,
            "version": "2.0.0",
            "environment": settings.environment,
            "checks": {}
        }
        
        for check in self.checks:
            response["checks"][check.name] = {
                "status": check.status,
                "message": check.message,
                "response_time": check.response_time,
                "critical": check.critical,
                "details": check.details
            }
        
        return response


@router.get("/health", summary="Basic health check")
async def basic_health_check():
    """Basic health check endpoint for load balancers."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@router.get("/health/detailed", summary="Detailed health check")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with all system components."""
    try:
        # Get Redis client (you'll need to implement this)
        from app.core.rate_limit import redis_client
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis not available"
            )
        
        health_checker = HealthChecker(db, redis_client)
        result = await health_checker.run_checks()
        
        # Set appropriate HTTP status code
        if result["status"] == HealthStatus.CRITICAL:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result
            )
        elif result["status"] == HealthStatus.UNHEALTHY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result
            )
        elif result["status"] == HealthStatus.DEGRADED:
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail=result
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": HealthStatus.CRITICAL,
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/health/readiness", summary="Readiness probe")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe endpoint."""
    try:
        # Check critical components only
        from app.core.rate_limit import redis_client
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis not available"
            )
        
        # Quick database check
        db.execute("SELECT 1").scalar()
        
        # Quick Redis check
        redis_client.ping()
        
        return {"status": "ready"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Not ready: {str(e)}"
        )


@router.get("/health/liveness", summary="Liveness probe")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive"}


@router.get("/health/metrics", summary="Health metrics")
async def health_metrics():
    """Health check metrics for monitoring."""
    try:
        metrics = resource_monitor.get_system_metrics()
        health_status = resource_monitor.check_health()
        
        return {
            "system_metrics": metrics,
            "health_status": health_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Health metrics failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health metrics failed: {str(e)}"
        )
