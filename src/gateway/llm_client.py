"""
LLM Client for Vertex AI Gemini integration
(No telemetry here – handled at route level)
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from src.gateway.config import get_settings
from src.utils.token_counter import estimate_token_count

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
        self._initialized = False
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Vertex AI Gemini (PROD only)."""
        try:
            if self.settings.DATADOG_ENV in ["dev", "development"]:
                logger.info("GeminiClient running in DEV mode (mock responses)")
                self._initialized = False
                return

            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(
                project=self.settings.GCP_PROJECT_ID,
                location=self.settings.VERTEX_LOCATION,
            )

            self.model = GenerativeModel(self.settings.GEMINI_MODEL)
            self._initialized = True

            logger.info(f"Gemini client initialized: {self.settings.GEMINI_MODEL}")

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

        # ----------------------------
        # DEV MODE (MOCK)
        # ----------------------------
        if self.settings.DATADOG_ENV in ["dev", "development"] or not self._initialized:
            time.sleep(0.2)  # simulate latency
            response_text = "This is a mock Gemini response (DEV mode)."

            latency_ms = (time.time() - start_time) * 1000
            input_tokens = estimate_token_count(prompt)
            output_tokens = estimate_token_count(response_text)

            return LLMResponse(
                text=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_estimate=0.0,
                model="gemini-mock",
            )

        # ----------------------------
        # PROD MODE (REAL GEMINI)
        # ----------------------------
        max_tokens = max_tokens or self.settings.MAX_TOKENS
        temperature = temperature or self.settings.TEMPERATURE

        response = self.model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )

        latency_ms = (time.time() - start_time) * 1000
        response_text = response.text if hasattr(response, "text") else str(response)

        input_tokens = estimate_token_count(prompt)
        output_tokens = estimate_token_count(response_text)
        cost_estimate = self._calculate_cost_estimate(input_tokens, output_tokens)

        return LLMResponse(
            text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            model=self.settings.GEMINI_MODEL,
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
            "model": self.settings.GEMINI_MODEL if self._initialized else "mock",
        }


# Singleton
_gemini_client = GeminiClient()


def get_llm_client() -> GeminiClient:
    return _gemini_client
