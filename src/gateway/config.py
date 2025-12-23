"""
Configuration management for SentinelLLM
"""
import logging
import os
from typing import Optional
from pydantic import validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Google Cloud Configuration
    GCP_PROJECT_ID: str
    VERTEX_LOCATION: str = "us-central1"
    
    # Vertex AI Configuration
    GEMINI_MODEL: str = "gemini-1.5-pro"
    MAX_TOKENS: int = 8192
    TEMPERATURE: float = 0.7
    
    # Datadog Configuration
    DATADOG_API_KEY: str
    DATADOG_SITE: str = "datadoghq.com"
    DATADOG_SERVICE_NAME: str = "sentinel-llm"
    DATADOG_ENV: str = "production"
    
    # OpenTelemetry Configuration
    OTEL_SERVICE_NAME: str = "sentinel-llm"
    OTEL_EXPORTER_DATADOG_AGENT_HOST: str = "localhost"
    OTEL_EXPORTER_DATADOG_AGENT_PORT: int = 8126
    
    # Security Configuration
    ENABLE_SECURITY_CHECKS: bool = True
    PROMPT_INJECTION_THRESHOLD: float = 0.8
    PII_DETECTION_ENABLED: bool = True
    
    # Performance Configuration
    REQUEST_TIMEOUT: int = 30
    MAX_CONCURRENT_REQUESTS: int = 10
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Application Configuration
    APP_NAME: str = "SentinelLLM"
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @validator("GCP_PROJECT_ID")
    def validate_gcp_project(cls, v):
        if not v or v == "your_project_id":
            # Allow startup in development mode with warning
            return "development_project_id"
        return v
    
    @validator("DATADOG_API_KEY")
    def validate_datadog_key(cls, v):
        if not v or v == "your_datadog_api_key":
            # Allow startup in development mode with warning
            return "development_api_key"
        return v


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the application settings"""
    return settings


def validate_environment() -> bool:
    """
    Validate that all required environment variables are set
    
    For development mode, this allows placeholder values but logs warnings.
    For production, it requires actual values.
    
    Returns:
        bool: True if environment is valid for development/testing
    """
    try:
        # Check for development mode (placeholder values)
        if settings.GCP_PROJECT_ID == "development_project_id":
            logger.warning("⚠️ Running in DEVELOPMENT mode - GCP_PROJECT_ID not set")
            logger.warning("   Some features will be limited or unavailable")
            return True
            
        if settings.DATADOG_API_KEY == "development_api_key":
            logger.warning("⚠️ Running in DEVELOPMENT mode - DATADOG_API_KEY not set")
            logger.warning("   Telemetry will use console exporters instead of Datadog")
            return True
        
        # Check for production mode (actual values)
        required_vars = ["GCP_PROJECT_ID", "DATADOG_API_KEY"]
        missing_vars = []
        
        for var in required_vars:
            value = getattr(settings, var)
            if not value or value.startswith("your_"):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            return False
            
        logger.info("✅ Environment validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Environment validation error: {e}")
        return False


# Don't fail import if environment validation fails
try:
    if not validate_environment():
        logger.warning("Environment validation failed on import - app will start in degraded mode")
except Exception:
    logger.warning("Could not validate environment on import - app will start anyway")
