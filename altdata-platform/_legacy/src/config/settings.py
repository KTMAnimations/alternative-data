"""Configuration settings for the Alternative Data Platform."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env not defined in Settings
    )
    
    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Database
    database_url: str = Field(default="postgresql://localhost/altdata_dev")
    database_pool_size: int = Field(default=5)
    database_echo: bool = Field(default=False)
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Storage
    use_local_storage: bool = Field(default=True)
    local_storage_path: str = Field(default="./data/raw")
    s3_bucket: Optional[str] = Field(default=None)
    aws_access_key_id: Optional[str] = Field(default=None)
    aws_secret_access_key: Optional[str] = Field(default=None)
    aws_region: str = Field(default="us-east-1")
    
    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    api_key_admin: Optional[str] = Field(default=None)
    api_key_default: Optional[str] = Field(default=None)

    # JWT Authentication
    jwt_secret_key: str = Field(default="change-this-secret-in-production-use-openssl-rand-hex-32")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)
    
    # External APIs
    sec_edgar_user_agent: str = Field(default="AltData Platform contact@example.com")
    fred_api_key: Optional[str] = Field(default=None)
    adsb_exchange_api_key: Optional[str] = Field(default=None)
    adsb_exchange_rapidapi_key: Optional[str] = Field(default=None)
    openaq_api_key: Optional[str] = Field(default=None)
    uspto_api_key: Optional[str] = Field(default=None)
    openweathermap_api_key: Optional[str] = Field(default=None)
    
    # Collector settings
    sec_edgar_interval: int = Field(default=300)  # 5 minutes
    sec_edgar_rate_limit: float = Field(default=10)  # requests per second
    fred_interval: int = Field(default=3600)  # 1 hour
    fred_rate_limit: float = Field(default=2)
    
    # Development flags
    skip_rate_limits: bool = Field(default=False)
    mock_external_apis: bool = Field(default=False)
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
