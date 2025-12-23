"""
FastAPI routes for SentinelLLM gateway
"""
import logging
import time
import uuid
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.gateway.config import get_settings, validate_environment
from src.gateway.llm_client import get_llm_client, LLMResponse
from src.gateway.security import check_security
from src.gateway.telemetry import telemetry_manager

logger = logging.getLogger(__name__)


# ----------------------------
# MODELS
# ----------------------------
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    model: Optional[str] = None


class GenerateResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_estimate: float
    model: str
    prompt_injection_detected: bool = False
    pii_detected: bool = False
    security_analysis: Optional[Dict[str, Any]] = None
    request_id: str


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    service: str
    version: str
    environment_valid: bool
    llm_client_healthy: bool


# ----------------------------
# APP INIT
# ----------------------------
app = FastAPI(
    title="SentinelLLM Gateway",
    description="Production-grade observability and security for LLM applications",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting SentinelLLM Gateway")

    if not validate_environment():
        raise RuntimeError("Invalid environment configuration")

    telemetry_manager.initialize()
    logger.info("Telemetry initialized")


# ----------------------------
# ROUTES
# ----------------------------
@app.get("/health", response_model=HealthResponse)
async def health_check():
    settings = get_settings()
    llm_client = get_llm_client()

    return HealthResponse(
        status="healthy",
        timestamp=time.time(),
        service=settings.APP_NAME,
        version="1.0.0",
        environment_valid=validate_environment(),
        llm_client_healthy=llm_client.health_check().get("initialized", False),
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Generate text using LLM with full observability and security.
    """
    start_time = time.time()
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    # ✅ Start span
    span_ctx = telemetry_manager.start_llm_span()

    try:
        logger.info(f"[{request_id}] Processing generation request")

        # 1️⃣ Security analysis (prompt)
        security_results = check_security(request.prompt)

        if security_results["prompt_analysis"]["injection_detected"]:
            telemetry_manager.record_metrics(
                latency_ms=(time.time() - start_time) * 1000,
                error=True,
                error_type="PromptInjection",
                model=request.model or "unknown",
                prompt_injection_detected=True,
            )
            raise HTTPException(
                status_code=400,
                detail="Prompt rejected due to security concerns",
            )

        # 2️⃣ Call LLM
        llm_client = get_llm_client()
        llm_response: LLMResponse = llm_client.generate(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        latency_ms = (time.time() - start_time) * 1000

        # 3️⃣ Record metrics
        telemetry_manager.record_metrics(
            latency_ms=latency_ms,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            cost_estimate=llm_response.cost_estimate,
            model=llm_response.model,
            prompt_injection_detected=False,
        )

        response = GenerateResponse(
            text=llm_response.text,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            latency_ms=latency_ms,
            cost_estimate=llm_response.cost_estimate,
            model=llm_response.model,
            prompt_injection_detected=False,
            pii_detected=len(security_results["prompt_analysis"]["pii_types"]) > 0,
            security_analysis=security_results,
            request_id=request_id,
        )

        background_tasks.add_task(
            _post_process_response,
            request_id,
            request.prompt,
            llm_response,
            security_results,
        )

        logger.info(f"[{request_id}] Request completed successfully")
        return response

    except HTTPException:
        raise

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000

        telemetry_manager.record_metrics(
            latency_ms=latency_ms,
            error=True,
            error_type=type(e).__name__,
            model=request.model or "unknown",
        )

        logger.exception(f"[{request_id}] Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        # ✅ End span (CRITICAL)
        telemetry_manager.end_llm_span(span_ctx)


# ----------------------------
# BACKGROUND TASK
# ----------------------------
async def _post_process_response(
    request_id: str,
    prompt: str,
    llm_response: LLMResponse,
    security_results: Dict[str, Any],
):
    logger.debug(f"[{request_id}] Post-processing completed")


# ----------------------------
# META ROUTES
# ----------------------------
@app.get("/metrics")
async def get_metrics():
    return {
        "note": "Metrics are exported via OpenTelemetry. View them in Datadog.",
        "status": "ok",
    }


@app.get("/config")
async def get_config():
    settings = get_settings()
    return {
        "model": settings.GEMINI_MODEL,
        "location": settings.VERTEX_LOCATION,
        "service_name": settings.OTEL_SERVICE_NAME,
        "environment": settings.DATADOG_ENV,
        "security_enabled": settings.ENABLE_SECURITY_CHECKS,
    }
