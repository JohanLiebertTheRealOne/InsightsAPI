"""
Configuration Management for InsightFinance API
===============================================

This module handles all environment variables and application settings.
It provides a centralized way to manage configuration across different
environments (development, staging, production).

Key Features:
- Environment variable loading with defaults
- Type validation and conversion
- Security settings (JWT secrets, CORS, etc.)
- Database and cache configuration
- External API keys management
"""

import os
from typing import Optional, List
from pydantic import BaseSettings, validator
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    This class uses Pydantic's BaseSettings to automatically load
    configuration from environment variables with type validation.
    
    Environment Variables Required:
    - DATABASE_URL: PostgreSQL connection string
    - REDIS_URL: Redis connection string
    - SECRET_KEY: JWT secret key
    - ALPHA_VANTAGE_API_KEY: Alpha Vantage API key
    
    Optional Environment Variables:
    - ENVIRONMENT: deployment environment (dev/staging/prod)
    - DEBUG: enable debug mode
    - CORS_ORIGINS: allowed CORS origins
    """
    
    # Application Settings
    APP_NAME: str = "InsightFinance API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Security Settings
    SECRET_KEY: str = "your-super-secret-jwt-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/insightfinance"
    
    # Redis Cache Configuration
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 300  # 5 minutes default cache time
    
    # External API Keys
    ALPHA_VANTAGE_API_KEY: str = "demo"  # Replace with real API key
    YAHOO_FINANCE_ENABLED: bool = True
    COINGECKO_ENABLED: bool = True
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # Rate Limiting (basic implementation)
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "insightfinance.log"
    
    # API Limits
    MAX_PORTFOLIO_SIZE: int = 100
    MAX_HISTORICAL_DAYS: int = 365
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        """
        Validate that SECRET_KEY is not the default value in production.
        
        Args:
            v: The secret key value
            
        Returns:
            str: The validated secret key
            
        Raises:
            ValueError: If secret key is default in production
        """
        if v == "your-super-secret-jwt-key-change-in-production" and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("SECRET_KEY must be changed in production environment")
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """
        Validate database URL format.
        
        Args:
            v: The database URL
            
        Returns:
            str: The validated database URL
        """
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection string")
        return v
    
    @validator("REDIS_URL")
    def validate_redis_url(cls, v):
        """
        Validate Redis URL format.
        
        Args:
            v: The Redis URL
            
        Returns:
            str: The validated Redis URL
        """
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must be a valid Redis connection string")
        return v
    
    @validator("ALPHA_VANTAGE_API_KEY")
    def validate_alpha_vantage_key(cls, v):
        """
        Validate Alpha Vantage API key.
        
        Args:
            v: The API key
            
        Returns:
            str: The validated API key
        """
        if v == "demo" and os.getenv("ENVIRONMENT") == "production":
            logger.warning("Using demo Alpha Vantage API key in production")
        return v
    
    class Config:
        """
        Pydantic configuration for environment variable loading.
        """
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()

# Log configuration on startup
logger.info(f"Configuration loaded for environment: {settings.ENVIRONMENT}")
logger.info(f"Database URL configured: {settings.DATABASE_URL[:20]}...")
logger.info(f"Redis URL configured: {settings.REDIS_URL}")
logger.info(f"Debug mode: {settings.DEBUG}")


def get_settings() -> Settings:
    """
    Dependency function to get settings instance.
    
    This function can be used as a FastAPI dependency to inject
    settings into route handlers.
    
    Returns:
        Settings: The global settings instance
    """
    return settings


# Environment-specific configurations
class DevelopmentSettings(Settings):
    """Development environment settings with relaxed security."""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    CACHE_TTL: int = 60  # Shorter cache for development


class ProductionSettings(Settings):
    """Production environment settings with enhanced security."""
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    CACHE_TTL: int = 600  # Longer cache for production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Shorter token expiry


def get_environment_settings() -> Settings:
    """
    Get environment-specific settings based on ENVIRONMENT variable.
    
    Returns:
        Settings: Environment-specific settings instance
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "staging":
        return DevelopmentSettings()  # Use dev settings for staging
    else:
        return DevelopmentSettings()


# Export the appropriate settings instance
settings = get_environment_settings()

