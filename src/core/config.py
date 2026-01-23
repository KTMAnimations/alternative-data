"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Alternative Data Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/altdata"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/altdata"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # API
    api_prefix: str = "/api/v1"
    api_rate_limit_per_minute: int = 100
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Security
    secret_key: str = "change-this-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # External APIs
    fred_api_key: Optional[str] = None
    cloudflare_api_token: Optional[str] = None

    # Collector Settings
    collector_timeout_seconds: int = 60
    collector_max_retries: int = 3
    collector_retry_delay_seconds: int = 5

    # Storage
    s3_bucket: Optional[str] = None
    s3_endpoint_url: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
