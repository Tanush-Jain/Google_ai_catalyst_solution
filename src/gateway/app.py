"""
SentinelLLM Gateway - Production-grade LLM observability and security

This FastAPI application provides a gateway to Vertex AI Gemini with:
- Comprehensive OpenTelemetry instrumentation
- Security monitoring (prompt injection, PII detection)
- Real-time telemetry streaming to Datadog
- Production-ready error handling and monitoring
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from src.gateway.config import get_settings, validate_environment
from src.gateway.telemetry import initialize_telemetry, instrument_fastapi_app
from src.api.routes import app as api_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        # TODO: Add file handler for production logging
        # logging.FileHandler('/var/log/sentinel-llm/app.log')
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management"""
    logger.info("Starting SentinelLLM Gateway application...")
    
    # Startup
    try:
        # Validate environment
        if not validate_environment():
            logger.error("Environment validation failed!")
            raise RuntimeError("Invalid environment configuration")
        
        # Initialize telemetry
        initialize_telemetry()
        
        # Instrument FastAPI app with OpenTelemetry
        instrument_fastapi_app(app)
        
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SentinelLLM Gateway application...")


# Create FastAPI application
app = FastAPI(
    title="SentinelLLM Gateway",
    description="""
    Production-grade observability and security for LLM applications.
    
    This gateway provides:
    - **Security Monitoring**: Prompt injection detection, PII detection
    - **Observability**: OpenTelemetry instrumentation with Datadog export
    - **Cost Tracking**: Real-time token and cost monitoring
    - **Performance**: Latency tracking and performance metrics
    
    ## Features
    
    ### Security
    - Prompt injection detection using regex patterns
    - PII detection (emails, phones, SSNs, credit cards)
    - Response safety analysis
    
    ### Observability  
    - Request/response latency tracking
    - Token usage monitoring
    - Cost estimation and tracking
    - Error rate monitoring
    - Custom metrics for Datadog
    
    ### API Endpoints
    - `POST /generate` - Generate text with full observability
    - `GET /health` - Health check with service status
    - `GET /metrics` - Current metrics summary
    - `GET /config` - Non-sensitive configuration
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


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


# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with service information"""
    settings = get_settings()
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "description": "Production-grade LLM observability and security gateway",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        # Check if all required services are healthy
        from src.gateway.config import validate_environment
        from src.gateway.llm_client import get_llm_client
        
        env_valid = validate_environment()
        client_healthy = get_llm_client().health_check().get("initialized", False)
        
        if env_valid and client_healthy:
            return {"status": "ready"}
        else:
            return {"status": "not_ready", "reason": "Service dependencies not healthy"}
            
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)}


@app.get("/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}


if __name__ == "__main__":
    settings = get_settings()
    
    # Run with uvicorn
    uvicorn.run(
        "src.gateway.app:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
        log_level="info"
    )

