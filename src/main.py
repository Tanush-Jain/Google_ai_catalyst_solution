"""
SentinelLLM Gateway - Production Entry Point

This is the main entry point for the SentinelLLM application.
It imports the FastAPI app from src.api.routes and configures proper startup.
"""
import logging
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Import the configured FastAPI app and telemetry
from src.api.routes import app as api_app
from src.gateway.telemetry import telemetry_manager, instrument_fastapi_app
from src.gateway.config import get_settings, validate_environment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    This function:
    1. Uses the existing FastAPI app from src.api.routes
    2. Adds middleware for CORS and security
    3. Sets up proper startup/shutdown handlers
    4. Instruments the app with OpenTelemetry
    """
    settings = get_settings()
    
    # Use the existing app from routes.py
    app = api_app
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # TODO: Restrict in production
    )
    
    @app.on_event("startup")
    async def startup_event():
        """Application startup event handler"""
        logger.info("Starting SentinelLLM Gateway...")
        
        try:
            # Validate environment (but don't fail startup if missing keys)
            env_valid = validate_environment()
            if not env_valid:
                logger.warning("Environment validation failed - running in degraded mode")
                logger.warning("Please set GCP_PROJECT_ID and DATADOG_API_KEY for full functionality")
            
            # Ensure telemetry is initialized (it's already done at import time)
            if not telemetry_manager._initialized:
                telemetry_manager.initialize()
            
            # Instrument FastAPI with OpenTelemetry
            instrument_fastapi_app(app)
            
            logger.info("SentinelLLM Gateway started successfully")
            logger.info(f"Service: {settings.APP_NAME}")
            logger.info(f"Environment: {settings.DATADOG_ENV}")
            logger.info(f"Debug mode: {settings.DEBUG}")
            
        except Exception as e:
            logger.error(f"Startup failed: {e}")
            # Don't raise - let the app start in degraded mode
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event handler"""
        logger.info("Shutting down SentinelLLM Gateway...")
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    """
    Main entry point when running: python src/main.py
    
    This provides a clean, production-style way to start the application.
    """
    settings = get_settings()
    
    logger.info("Starting SentinelLLM Gateway via uvicorn...")
    logger.info(f"Host: 0.0.0.0")
    logger.info(f"Port: 8080")
    logger.info(f"Reload: {settings.DEBUG}")
    logger.info(f"Log Level: {'debug' if settings.DEBUG else 'info'}")
    
    # Run with uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=True
    )
