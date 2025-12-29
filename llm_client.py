import os
import re
from typing import List

import structlog
import vertexai
from google.api_core import exceptions
from vertexai.generative_models import GenerativeModel

# Configure structured logging
logger = structlog.get_logger()

class LLMClient:
    def __init__(self):
        """Initialize the Vertex AI client with region validation."""
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.region = self._validate_region(os.getenv("GOOGLE_CLOUD_REGION", "us-central1"))
        
        # Initialize Vertex AI SDK safely
        try:
            vertexai.init(project=self.project_id, location=self.region)
            logger.info("vertex_ai_initialized", project=self.project_id, region=self.region)
        except Exception as e:
            # Log error but do not crash the application startup
            logger.error("vertex_ai_init_failed", error=str(e))

    def _validate_region(self, region: str) -> str:
        """
        Validates and cleans the region string.
        Ensures no UI-style strings like 'asia-south2 (Delhi)' are used.
        Defaults to 'us-central1' if invalid.
        """
        if not region:
            return "us-central1"
            
        # Extract the region code (everything before the first space)
        clean_region = region.split(" ")[0].strip()
        
        # Validate against standard Google Cloud region format (e.g., us-central1)
        if not re.match(r"^[a-z]+-[a-z]+\d+$", clean_region):
            logger.warning("invalid_region_detected", original=region, fallback="us-central1")
            return "us-central1"
            
        return clean_region

    def _get_model_candidates(self) -> List[str]:
        """
        Returns a list of Gemini models to try in priority order.
        1. GEMINI_MODEL env var (if set)
        2. gemini-1.5-flash-002
        3. gemini-1.0-pro
        """
        candidates = []
        
        # 1. Environment variable
        env_model = os.getenv("GEMINI_MODEL")
        if env_model:
            candidates.append(env_model)
            
        # 2. & 3. Fallback models
        fallbacks = ["gemini-1.5-flash-002", "gemini-1.0-pro"]
        for model in fallbacks:
            if model not in candidates:
                candidates.append(model)
                
        return candidates

    async def generate_content(self, prompt: str) -> str:
        """
        Generates content using the first accessible Gemini model.
        Implements fault tolerance and automatic fallback.
        """
        candidates = self._get_model_candidates()
        last_error = None

        for model_name in candidates:
            try:
                logger.info("attempting_generation", model=model_name)
                
                # Instantiate model
                model = GenerativeModel(model_name)
                
                # Generate content (async)
                response = await model.generate_content_async(prompt)
                
                logger.info("generation_success", model=model_name)
                return response.text

            except (exceptions.NotFound, exceptions.PermissionDenied, exceptions.FailedPrecondition) as e:
                logger.warning("model_access_failed", model=model_name, error=str(e))
                last_error = e
                continue # Try next model
            except Exception as e:
                logger.error("generation_error", model=model_name, error=str(e))
                last_error = e
                continue

        # If all models fail
        logger.error("all_models_failed", last_error=str(last_error))
        return "Vertex AI model not accessible for this project"