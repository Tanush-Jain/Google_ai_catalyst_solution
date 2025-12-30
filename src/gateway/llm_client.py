"""
LLM Client for Vertex AI Gemini 2.0 integration
CRITICAL: Uses Gemini 2.0 preview API - requires structured content input
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from src.gateway.config import get_settings
from src.utils.token_counter import estimate_token_count
from src.gateway.telemetry import telemetry_manager
from opentelemetry.trace import Status, StatusCode

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
        self._initialize_client()

    def _validate_region(self, region: str) -> str:
        """Validate and normalize region string"""
        region = region.strip()
        if region in self.valid_regions:
            return region
        logger.warning(f"Invalid region '{region}', defaulting to 'us-central1'")
        return "us-central1"

    def _initialize_client(self) -> None:
        """
        Initialize Vertex AI Gemini 2.0.
        CRITICAL: This must succeed or raise RuntimeError.
        No mock mode. No fallback. No silent degradation.
        """
        import vertexai
        from vertexai.preview.generative_models import GenerativeModel

        # Validate and set region
        region = self._validate_region(getattr(self.settings, 'VERTEX_LOCATION', 'us-central1'))
        project_id = self.settings.GCP_PROJECT_ID
        model_name = getattr(self.settings, 'GEMINI_MODEL', None)
        
        if not project_id:
            raise RuntimeError("GCP_PROJECT_ID is not set. Cannot initialize Vertex AI.")
        
        if not model_name:
            raise RuntimeError("GEMINI_MODEL is not set. Cannot initialize Vertex AI.")
        
        logger.info(f"Initializing Vertex AI with project={project_id}, location={region}")
        
        # Initialize Vertex AI - FAIL HARD if this fails
        vertexai.init(
            project=project_id,
            location=region,
        )
        logger.info("✅ Vertex AI initialized successfully")

        # Initialize the model - Gemini 2.0 requires model_name= parameter
        logger.info(f"Loading GenerativeModel: {model_name}")
        self.model = GenerativeModel(model_name=model_name)
        self.selected_model = model_name
        self._initialized = True
        
        logger.info(f"✅ Gemini 2.0 initialized successfully: {model_name}")

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Generate response using real Gemini 2.0.
        CRITICAL: This ALWAYS calls Vertex AI. No mock mode.
        If Gemini fails, this raises an exception.
        Gemini 2.0 requires structured content input.
        """
        start_time = time.time()

        # Assert initialization (fail fast if not initialized)
        if not self._initialized or self.model is None:
            raise RuntimeError("Gemini client not initialized. Application should have failed at startup.")

        # Configure generation parameters
        max_tokens = max_tokens or getattr(self.settings, 'MAX_TOKENS', 2048)
        temperature = temperature or getattr(self.settings, 'TEMPERATURE', 0.7)
        region = self._validate_region(getattr(self.settings, 'VERTEX_LOCATION', 'us-central1'))

        # Trace LLM Call with proper span attributes
        with telemetry_manager.tracer.start_as_current_span("vertexai.generate_content") as span:
            span.set_attribute("model_name", self.selected_model)
            span.set_attribute("region", region)
            span.set_attribute("max_tokens", max_tokens)
            span.set_attribute("temperature", temperature)
            span.set_attribute("prompt_length", len(prompt))
            
            # Gemini 2.0 requires structured content input
            response = self.model.generate_content(
                contents=[
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("success", True)
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Gemini 2.0: response.text is the structured text accessor
            if not hasattr(response, 'text') or not response.text:
                raise RuntimeError("Gemini returned empty response")
            
            response_text = response.text

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
            "selected_model": self.selected_model,
            "model": self.selected_model,
            "region": self._validate_region(getattr(self.settings, 'VERTEX_LOCATION', 'us-central1')),
        }


# Singleton
_gemini_client = GeminiClient()


def get_llm_client() -> GeminiClient:
    return _gemini_client
