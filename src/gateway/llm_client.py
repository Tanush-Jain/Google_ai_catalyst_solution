"""
LLM Client for Vertex AI Gemini integration with fault tolerance
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from src.gateway.config import get_settings
from src.utils.token_counter import estimate_token_count
from src.gateway.telemetry import telemetry_manager
from opentelemetry.trace import Status, StatusCode, get_current_span

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_estimate: float
    model: str


class GeminiClient:
    def __init__(self):
        self.settings = get_settings()
        self.model = None
        self.selected_model = None
        self._initialized = False
        self.valid_regions = {
            "us-central1", "us-east1", "us-west1", "us-west2", "us-west3", "us-west4",
            "us-east4", "us-east5", "northamerica-northeast1", "southamerica-east1",
            "europe-west1", "europe-west2", "europe-west3", "europe-west4", 
            "europe-west6", "europe-central2", "asia-east1", "asia-east2",
            "asia-northeast1", "asia-northeast2", "asia-northeast3", "asia-southeast1",
            "australia-southeast1", "australia-southeast2", "me-west1"
        }
        self.model_fallback_order = [
            "gemini-1.5-flash-002",
            "gemini-1.0-pro"
        ]
        self._initialize_client()

    def _validate_region(self, region: str) -> str:
        """Validate and normalize region string"""
        region = region.strip()
        if region in self.valid_regions:
            return region
        logger.warning(f"Invalid region '{region}', defaulting to 'us-central1'")
        return "us-central1"

    def _get_model_from_env(self) -> Optional[str]:
        """Get model name from environment variable with fallback"""
        env_model = getattr(self.settings, 'GEMINI_MODEL', None)
        if env_model and env_model not in ["your_gemini_model", ""]:
            logger.info(f"Using model from environment: {env_model}")
            return env_model
        
        logger.warning("GEMINI_MODEL not set or invalid, using fallback model")
        return self.model_fallback_order[0]  # gemini-1.5-flash-002

    def _initialize_client(self) -> None:
        """Initialize Vertex AI Gemini with fault tolerance"""
        try:
            if self.settings.DATADOG_ENV in ["dev", "development"]:
                logger.info("GeminiClient running in DEV mode (mock responses)")
                self._initialized = False
                return

            import vertexai
            from vertexai.generative_models import GenerativeModel
            import google.api_core.exceptions as google_exceptions

            # Validate and set region
            region = self._validate_region(getattr(self.settings, 'VERTEX_LOCATION', 'us-central1'))
            
            # Initialize Vertex AI
            try:
                vertexai.init(
                    project=self.settings.GCP_PROJECT_ID,
                    location=region,
                )
            except (google_exceptions.PermissionDenied, google_exceptions.FailedPrecondition) as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
                self._initialized = False
                return

            # Get model name with fallback
            primary_model = self._get_model_from_env()
            models_to_try = [primary_model] + [m for m in self.model_fallback_order if m != primary_model]

            # Try models in order
            for model_name in models_to_try:
                try:
                    logger.info(f"Attempting to initialize model: {model_name}")
                    self.model = GenerativeModel(model_name)
                    self.selected_model = model_name
                    self._initialized = True
                    logger.info(f"✅ Successfully initialized Gemini model: {model_name}")
                    break
                    
                except google_exceptions.NotFound as e:
                    logger.warning(f"Model {model_name} not found: {e}")
                    continue
                    
                except google_exceptions.PermissionDenied as e:
                    logger.warning(f"Access denied for model {model_name}: {e}")
                    continue
                    
                except google_exceptions.FailedPrecondition as e:
                    logger.warning(f"Precondition failed for model {model_name}: {e}")
                    continue
                    
                except Exception as e:
                    logger.error(f"Unexpected error with model {model_name}: {e}")
                    continue

            if not self._initialized:
                logger.error("❌ Failed to initialize any Gemini model")
                return

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self._initialized = False

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        start_time = time.time()

        # DEV MODE (MOCK)
        if self.settings.DATADOG_ENV in ["dev", "development"]:
            time.sleep(0.2)  # simulate latency
            response_text = "This is a mock Gemini response (DEV mode)."

            latency_ms = (time.time() - start_time) * 1000
            input_tokens = estimate_token_count(prompt)
            output_tokens = estimate_token_count(response_text)

            # Record DEV metrics
            telemetry_manager.record_llm_metrics(
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model="gemini-mock",
                status="success"
            )

            # Structured logging
            telemetry_manager.log_structured(
                "INFO", 
                "Mock LLM response generated",
                model="gemini-mock",
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                environment="development"
            )

            return LLMResponse(
                text=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_estimate=0.0,
                model="gemini-mock",
            )

        # PROD MODE - Check Initialization
        if not self._initialized:
            latency_ms = (time.time() - start_time) * 1000
            input_tokens = estimate_token_count(prompt)
            
            # Record Error Metrics
            telemetry_manager.record_llm_metrics(
                llm_failure=True,
                error_type="initialization_failure",
                latency_ms=latency_ms,
                model="uninitialized",
                status="error"
            )

            # Structured logging
            telemetry_manager.log_structured(
                "ERROR", 
                "LLM client not initialized",
                error_type="initialization_failure",
                latency_ms=latency_ms,
                model="uninitialized",
                environment="production"
            )

            return LLMResponse(
                text="Error: Vertex AI model not accessible for this project",
                input_tokens=input_tokens,
                output_tokens=0,
                latency_ms=latency_ms,
                cost_estimate=0.0,
                model="error",
            )

        # PROD MODE (REAL GEMINI)
        max_tokens = max_tokens or getattr(self.settings, 'MAX_TOKENS', 2048)
        temperature = temperature or getattr(self.settings, 'TEMPERATURE', 0.7)
        region = self._validate_region(getattr(self.settings, 'VERTEX_LOCATION', 'us-central1'))

        try:
            # Trace LLM Call with proper span attributes
            with telemetry_manager.tracer.start_as_current_span("vertexai.generate_content") as span:
                span.set_attribute("model_name", self.selected_model)
                span.set_attribute("region", region)
                span.set_attribute("max_tokens", max_tokens)
                span.set_attribute("temperature", temperature)
                span.set_attribute("prompt_length", len(prompt))
                
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                span.set_status(Status(StatusCode.OK))
                span.set_attribute("success", True)
                
                latency_ms = (time.time() - start_time) * 1000
                response_text = response.text if hasattr(response, "text") else str(response)

                input_tokens = estimate_token_count(prompt)
                output_tokens = estimate_token_count(response_text)
                cost_estimate = self._calculate_cost_estimate(input_tokens, output_tokens)

                # Record Success Metrics
                telemetry_manager.record_llm_metrics(
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_estimate=cost_estimate,
                    model=self.selected_model,
                    status="success"
                )

                # Structured logging for success
                telemetry_manager.log_structured(
                    "INFO", 
                    "LLM request completed successfully",
                    model=self.selected_model,
                    region=region,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_estimate=cost_estimate,
                    success=True
                )

                return LLMResponse(
                    text=response_text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost_estimate=cost_estimate,
                    model=self.selected_model,
                )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            
            # Graceful error response
            latency_ms = (time.time() - start_time) * 1000
            input_tokens = estimate_token_count(prompt)
            
            # Record Failure Metrics
            telemetry_manager.record_llm_metrics(
                llm_failure=True,
                error_type=str(type(e).__name__),
                latency_ms=latency_ms,
                model=self.selected_model,
                status="error"
            )

            # Structured logging for error
            telemetry_manager.log_structured(
                "ERROR", 
                "LLM request failed",
                model=self.selected_model,
                region=region,
                latency_ms=latency_ms,
                error_type=str(type(e).__name__),
                error_message=str(e),
                success=False
            )

            return LLMResponse(
                text="Error: Vertex AI model not accessible for this project",
                input_tokens=input_tokens,
                output_tokens=0,
                latency_ms=latency_ms,
                cost_estimate=0.0,
                model="error",
            )

    def _calculate_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        input_cost_per_1k = 0.00125
        output_cost_per_1k = 0.0025

        return round(
            (input_tokens / 1000) * input_cost_per_1k
            + (output_tokens / 1000) * output_cost_per_1k,
            6,
        )

    def health_check(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "selected_model": self.selected_model if self._initialized else None,
            "model": self.selected_model if self._initialized else "mock",
            "region": self._validate_region(getattr(self.settings, 'VERTEX_LOCATION', 'us-central1')),
        }


# Singleton
_gemini_client = GeminiClient()


def get_llm_client() -> GeminiClient:
    return _gemini_client
