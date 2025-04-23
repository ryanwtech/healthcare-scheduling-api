"""Application configuration using Pydantic Settings."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = Field(default="Healthcare Scheduling API", alias="APP_NAME")
    env: str = Field(default="dev", alias="ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # Security
    secret_key: str = Field(alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Database
    database_url: str = Field(alias="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Monitoring
    prometheus_enabled: bool = Field(default=False, alias="PROMETHEUS_ENABLED")

    # Celery
    celery_broker_url: str = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(alias="CELERY_RESULT_BACKEND")

    # Initial Superuser
    first_superuser_email: str = Field(default="admin@gmail.com", alias="FIRST_SUPERUSER_EMAIL")
    first_superuser_password: str = Field(default="admin123", alias="FIRST_SUPERUSER_PASSWORD")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = False

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.env.lower() == "prod"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env.lower() in ("dev", "development")

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.env.lower() in ("test", "testing")


# Global settings instance
settings = Settings()

# Set timezone to UTC
os.environ["TZ"] = "UTC"
