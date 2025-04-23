"""Production configuration and environment management."""

import os
from typing import Dict, List, Optional
from pydantic import BaseSettings, Field, validator
from app.core.config import Settings


class ProductionSettings(Settings):
    """Production-specific settings with enhanced security and monitoring."""
    
    # Environment
    environment: str = Field(default="production", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Security
    secret_key: str = Field(..., alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    database_pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=30, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=3600, alias="DATABASE_POOL_RECYCLE")
    
    # Redis
    redis_url: str = Field(..., alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: int = Field(default=5, alias="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: int = Field(default=5, alias="REDIS_SOCKET_CONNECT_TIMEOUT")
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    
    # Performance
    worker_processes: int = Field(default=4, alias="WORKER_PROCESSES")
    worker_connections: int = Field(default=1000, alias="WORKER_CONNECTIONS")
    max_requests: int = Field(default=1000, alias="MAX_REQUESTS")
    max_requests_jitter: int = Field(default=100, alias="MAX_REQUESTS_JITTER")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")
    
    # CORS
    cors_origins: List[str] = Field(default=[], alias="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    
    # SSL/TLS
    ssl_cert_path: Optional[str] = Field(default=None, alias="SSL_CERT_PATH")
    ssl_key_path: Optional[str] = Field(default=None, alias="SSL_KEY_PATH")
    
    # Backup
    backup_enabled: bool = Field(default=True, alias="BACKUP_ENABLED")
    backup_schedule: str = Field(default="0 2 * * *", alias="BACKUP_SCHEDULE")  # Daily at 2 AM
    backup_retention_days: int = Field(default=30, alias="BACKUP_RETENTION_DAYS")
    
    # Health Checks
    health_check_interval: int = Field(default=30, alias="HEALTH_CHECK_INTERVAL")
    health_check_timeout: int = Field(default=10, alias="HEALTH_CHECK_TIMEOUT")
    
    # API Versioning
    api_version: str = Field(default="v1", alias="API_VERSION")
    api_prefix: str = Field(default="/api", alias="API_PREFIX")
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"
    
    def get_database_config(self) -> Dict[str, any]:
        """Get database configuration for SQLAlchemy."""
        return {
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "pool_timeout": self.database_pool_timeout,
            "pool_recycle": self.database_pool_recycle,
            "pool_pre_ping": True,
        }
    
    def get_redis_config(self) -> Dict[str, any]:
        """Get Redis configuration."""
        return {
            "max_connections": self.redis_max_connections,
            "socket_timeout": self.redis_socket_timeout,
            "socket_connect_timeout": self.redis_socket_connect_timeout,
            "retry_on_timeout": True,
            "health_check_interval": 30,
        }


class EnvironmentManager:
    """Manage environment-specific configurations."""
    
    def __init__(self):
        self.environments = {
            "development": "app.core.config",
            "testing": "app.core.config", 
            "staging": "app.core.production_config",
            "production": "app.core.production_config",
        }
    
    def get_settings(self, environment: Optional[str] = None) -> Settings:
        """Get settings for the specified environment."""
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")
        
        if environment not in self.environments:
            raise ValueError(f"Unknown environment: {environment}")
        
        if environment in ["staging", "production"]:
            return ProductionSettings()
        else:
            from app.core.config import Settings
            return Settings()
    
    def validate_environment(self, environment: str) -> bool:
        """Validate that all required environment variables are set."""
        try:
            settings = self.get_settings(environment)
            if environment in ["staging", "production"]:
                # Check required production variables
                required_vars = [
                    "SECRET_KEY",
                    "DATABASE_URL", 
                    "REDIS_URL",
                ]
                missing_vars = []
                for var in required_vars:
                    if not os.getenv(var):
                        missing_vars.append(var)
                
                if missing_vars:
                    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
            return True
        except Exception as e:
            print(f"Environment validation failed: {e}")
            return False


# Global environment manager
env_manager = EnvironmentManager()


def get_production_settings() -> ProductionSettings:
    """Get production settings."""
    return ProductionSettings()


def validate_production_environment() -> bool:
    """Validate production environment configuration."""
    return env_manager.validate_environment("production")
