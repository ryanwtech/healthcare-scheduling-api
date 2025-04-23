"""Performance optimization utilities for production deployment."""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from redis import Redis

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring and optimization."""
    
    def __init__(self, app, max_response_time: float = 5.0):
        super().__init__(app)
        self.max_response_time = max_response_time
        self.slow_requests = []
    
    async def dispatch(self, request: Request, call_next):
        """Monitor request performance."""
        start_time = time.time()
        
        # Add performance headers
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
        
        # Log slow requests
        if process_time > self.max_response_time:
            logger.warning(
                "Slow request detected",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "process_time": process_time,
                    "max_time": self.max_response_time,
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            )
            self.slow_requests.append({
                "path": request.url.path,
                "method": request.method,
                "process_time": process_time,
                "timestamp": time.time()
            })
        
        return response


class DatabaseConnectionPool:
    """Database connection pool manager for optimal performance."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.pool_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "overflow_connections": 0
        }
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get current pool statistics."""
        if hasattr(self.db_session.bind, 'pool'):
            pool = self.db_session.bind.pool
            self.pool_stats.update({
                "total_connections": pool.size(),
                "active_connections": pool.checkedout(),
                "idle_connections": pool.checkedin(),
                "overflow_connections": pool.overflow()
            })
        return self.pool_stats
    
    def optimize_pool(self) -> None:
        """Optimize connection pool settings."""
        if hasattr(self.db_session.bind, 'pool'):
            pool = self.db_session.bind.pool
            # Adjust pool size based on current load
            current_size = pool.size()
            active = pool.checkedout()
            
            if active > current_size * 0.8:
                # Increase pool size if heavily utilized
                new_size = min(current_size * 1.5, settings.database_pool_size)
                logger.info(f"Increasing pool size from {current_size} to {new_size}")
            elif active < current_size * 0.3:
                # Decrease pool size if underutilized
                new_size = max(current_size * 0.8, 5)
                logger.info(f"Decreasing pool size from {current_size} to {new_size}")


class RedisConnectionManager:
    """Redis connection manager for optimal performance."""
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0
        }
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get Redis connection statistics."""
        try:
            info = self.redis_client.info()
            self.connection_stats.update({
                "total_connections": info.get("total_connections_received", 0),
                "active_connections": info.get("connected_clients", 0),
                "idle_connections": info.get("idle_connections", 0)
            })
        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
        
        return self.connection_stats
    
    def optimize_connections(self) -> None:
        """Optimize Redis connections."""
        try:
            # Set optimal connection parameters
            self.redis_client.connection_pool.connection_kwargs.update({
                "socket_timeout": settings.redis_socket_timeout,
                "socket_connect_timeout": settings.redis_socket_connect_timeout,
                "retry_on_timeout": True,
                "health_check_interval": 30
            })
        except Exception as e:
            logger.error(f"Failed to optimize Redis connections: {e}")


class CacheManager:
    """Advanced caching manager for performance optimization."""
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
    
    async def get_or_set(
        self, 
        key: str, 
        factory: Callable, 
        ttl: int = 3600,
        *args, 
        **kwargs
    ) -> Any:
        """Get from cache or set using factory function."""
        try:
            # Try to get from cache
            cached_value = self.redis_client.get(key)
            if cached_value is not None:
                self.cache_stats["hits"] += 1
                return cached_value
            
            # Cache miss - call factory
            self.cache_stats["misses"] += 1
            value = await factory(*args, **kwargs) if asyncio.iscoroutinefunction(factory) else factory(*args, **kwargs)
            
            # Set in cache
            self.redis_client.setex(key, ttl, value)
            self.cache_stats["sets"] += 1
            
            return value
        except Exception as e:
            logger.error(f"Cache operation failed for key {key}: {e}")
            # Fallback to factory function
            return await factory(*args, **kwargs) if asyncio.iscoroutinefunction(factory) else factory(*args, **kwargs)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                self.cache_stats["deletes"] += deleted
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Failed to invalidate pattern {pattern}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


class QueryOptimizer:
    """Database query optimization utilities."""
    
    @staticmethod
    def optimize_query(query, eager_loads: List[str] = None):
        """Optimize SQLAlchemy query with eager loading."""
        if eager_loads:
            for relation in eager_loads:
                query = query.options(joinedload(relation))
        return query
    
    @staticmethod
    def add_query_hints(query, hints: Dict[str, Any]):
        """Add database-specific query hints."""
        # This would be database-specific implementation
        return query


def performance_monitor(func: Callable) -> Callable:
    """Decorator to monitor function performance."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"Function {func.__name__} executed in {execution_time:.4f}s",
                extra={
                    "function": func.__name__,
                    "execution_time": execution_time,
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                }
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Function {func.__name__} failed after {execution_time:.4f}s: {e}",
                extra={
                    "function": func.__name__,
                    "execution_time": execution_time,
                    "error": str(e)
                }
            )
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"Function {func.__name__} executed in {execution_time:.4f}s",
                extra={
                    "function": func.__name__,
                    "execution_time": execution_time,
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                }
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Function {func.__name__} failed after {execution_time:.4f}s: {e}",
                extra={
                    "function": func.__name__,
                    "execution_time": execution_time,
                    "error": str(e)
                }
            )
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


@asynccontextmanager
async def database_transaction(db: Session):
    """Context manager for database transactions with performance monitoring."""
    start_time = time.time()
    try:
        yield db
        db.commit()
        execution_time = time.time() - start_time
        logger.info(f"Database transaction completed in {execution_time:.4f}s")
    except Exception as e:
        db.rollback()
        execution_time = time.time() - start_time
        logger.error(f"Database transaction failed after {execution_time:.4f}s: {e}")
        raise


class ResourceMonitor:
    """Monitor system resources and performance metrics."""
    
    def __init__(self):
        self.metrics = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "active_connections": 0,
            "request_rate": 0.0,
            "error_rate": 0.0
        }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        try:
            import psutil
            
            # CPU usage
            self.metrics["cpu_usage"] = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics["memory_usage"] = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.metrics["disk_usage"] = (disk.used / disk.total) * 100
            
            return self.metrics
        except ImportError:
            logger.warning("psutil not available for system monitoring")
            return self.metrics
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return self.metrics
    
    def check_health(self) -> Dict[str, Any]:
        """Check system health and return status."""
        metrics = self.get_system_metrics()
        
        health_status = {
            "status": "healthy",
            "warnings": [],
            "critical": [],
            "metrics": metrics
        }
        
        # Check CPU usage
        if metrics["cpu_usage"] > 80:
            health_status["warnings"].append(f"High CPU usage: {metrics['cpu_usage']:.1f}%")
        if metrics["cpu_usage"] > 95:
            health_status["critical"].append(f"Critical CPU usage: {metrics['cpu_usage']:.1f}%")
            health_status["status"] = "critical"
        
        # Check memory usage
        if metrics["memory_usage"] > 80:
            health_status["warnings"].append(f"High memory usage: {metrics['memory_usage']:.1f}%")
        if metrics["memory_usage"] > 95:
            health_status["critical"].append(f"Critical memory usage: {metrics['memory_usage']:.1f}%")
            health_status["status"] = "critical"
        
        # Check disk usage
        if metrics["disk_usage"] > 80:
            health_status["warnings"].append(f"High disk usage: {metrics['disk_usage']:.1f}%")
        if metrics["disk_usage"] > 95:
            health_status["critical"].append(f"Critical disk usage: {metrics['disk_usage']:.1f}%")
            health_status["status"] = "critical"
        
        return health_status


# Global instances
resource_monitor = ResourceMonitor()
