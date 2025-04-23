"""Redis-based rate limiting with sliding window algorithm."""

import time

import redis
from fastapi import HTTPException, Request, status
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Redis connection with graceful fallback
try:
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()  # Test connection
    REDIS_AVAILABLE = True
    logger.info("Rate limiter Redis connection established")
except Exception as e:
    redis_client = None
    REDIS_AVAILABLE = False
    logger.warning(f"Rate limiter Redis unavailable, rate limiting disabled: {e}")


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, reset_time: int, limit: int, window: int):
        self.reset_time = reset_time
        self.limit = limit
        self.window = window
        
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {limit} requests per {window} seconds",
                "retry_after": max(0, reset_time - int(time.time())),
                "limit": limit,
                "window": window
            }
        )


def get_rate_limit_key(identifier: str, endpoint: str) -> str:
    """Generate Redis key for rate limiting."""
    return f"rate_limit:{endpoint}:{identifier}"


# Retry configuration for Redis operations
redis_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.1, max=1.0),
    retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError, redis.RedisError)),
    reraise=True
)


@redis_retry
def check_rate_limit(identifier: str, limit: int, window_seconds: int, endpoint: str = "default") -> None:
    """
    Check if request is within rate limit using sliding window algorithm.
    
    Args:
        identifier: Unique identifier for the user/IP
        limit: Maximum number of requests allowed
        window_seconds: Time window in seconds
        endpoint: Endpoint name for different rate limits
        
    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    if not REDIS_AVAILABLE:
        logger.debug("Rate limiting disabled - Redis unavailable")
        return

    try:
        key = get_rate_limit_key(identifier, endpoint)
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Use Redis pipeline for atomic operations
        pipe = redis_client.pipeline()
        
        # Remove expired entries (older than window)
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiration for the key
        pipe.expire(key, window_seconds)
        
        # Execute pipeline
        results = pipe.execute()
        current_count = results[1]
        
        if current_count >= limit:
            # Get the oldest request in the window to calculate reset time
            oldest_requests = redis_client.zrange(key, 0, 0, withscores=True)
            if oldest_requests:
                oldest_time = int(oldest_requests[0][1])
                reset_time = oldest_time + window_seconds
            else:
                reset_time = current_time + window_seconds
                
            logger.warning(f"Rate limit exceeded for {identifier} on {endpoint}: {current_count}/{limit}")
            raise RateLimitExceeded(reset_time, limit, window_seconds)
        
        logger.debug(f"Rate limit check passed for {identifier}: {current_count + 1}/{limit}")
        
    except RateLimitExceeded:
        raise
    except Exception as e:
        logger.error(f"Rate limit check failed for {identifier}: {e}")
        # Don't block requests if rate limiting fails
        return


@redis_retry
def get_rate_limit_info(identifier: str, limit: int, window_seconds: int, endpoint: str = "default") -> dict:
    """
    Get current rate limit information without incrementing the counter.
    
    Returns:
        dict: Rate limit information including current count and reset time
    """
    if not REDIS_AVAILABLE:
        return {
            "limit": limit,
            "window": window_seconds,
            "current": 0,
            "remaining": limit,
            "reset_time": int(time.time()) + window_seconds
        }

    try:
        key = get_rate_limit_key(identifier, endpoint)
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Clean up expired entries
        redis_client.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        current_count = redis_client.zcard(key)
        
        # Get reset time (when oldest request expires)
        oldest_requests = redis_client.zrange(key, 0, 0, withscores=True)
        if oldest_requests:
            oldest_time = int(oldest_requests[0][1])
            reset_time = oldest_time + window_seconds
        else:
            reset_time = current_time + window_seconds
        
        return {
            "limit": limit,
            "window": window_seconds,
            "current": current_count,
            "remaining": max(0, limit - current_count),
            "reset_time": reset_time
        }
        
    except Exception as e:
        logger.error(f"Failed to get rate limit info for {identifier}: {e}")
        return {
            "limit": limit,
            "window": window_seconds,
            "current": 0,
            "remaining": limit,
            "reset_time": int(time.time()) + window_seconds
        }


def rate_limit_dependency(limit: int = 5, window_seconds: int = 60, endpoint: str = "default"):
    """
    FastAPI dependency factory for rate limiting.
    
    Args:
        limit: Maximum requests per window
        window_seconds: Window size in seconds
        endpoint: Endpoint identifier
        
    Returns:
        FastAPI dependency function
    """
    def _rate_limit(request: Request) -> None:
        # Use client IP as identifier (could be enhanced with user ID when available)
        client_ip = request.client.host if request.client else "unknown"
        check_rate_limit(client_ip, limit, window_seconds, endpoint)
    
    return _rate_limit


def user_rate_limit_dependency(limit: int = 5, window_seconds: int = 60, endpoint: str = "default"):
    """
    FastAPI dependency factory for user-based rate limiting.
    Requires current_user to be available in the dependency chain.
    
    Args:
        limit: Maximum requests per window
        window_seconds: Window size in seconds
        endpoint: Endpoint identifier
        
    Returns:
        FastAPI dependency function
    """
    def _user_rate_limit(request: Request, current_user) -> None:
        # Use user ID as identifier
        user_id = str(current_user.id)
        check_rate_limit(user_id, limit, window_seconds, endpoint)
    
    return _user_rate_limit
