"""
OpenTelemetry instrumentation for SentinelLLM
- PROD: Datadog via OTLP HTTP endpoint
- DEV: Console exporters (no cloud accounts required)
"""

import logging
import os
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from opentelemetry import trace, metrics
from opentelemetry.context import attach, detach
from opentelemetry.sdk.trace import TracerProvider, Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

# ✅ OTLP exporters (explicit at top as you asked)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

from src.gateway.config import get_settings

logger = logging.getLogger(__name__)


class TelemetryManager:
    """Manages OpenTelemetry tracing + metrics for SentinelLLM."""

    def __init__(self):
        self.settings = get_settings()
        self.tracer = None
        self.meter = None
        self.metrics = {}
        self._initialized = False
        self.request_id = None

    def initialize(self) -> None:
        """Initialize OpenTelemetry providers and exporters."""
        if self._initialized:
            return

        try:
            # ----------------------------
            # OTLP EXPORTER CONFIG (for Collector)
            # ----------------------------
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
            otlp_traces_exporter = os.getenv("OTEL_TRACES_EXPORTER", "otlp")
            otlp_metrics_exporter = os.getenv("OTEL_METRICS_EXPORTER", "otlp")
            
            # Get service configuration from environment
            service_name = os.getenv("OTEL_SERVICE_NAME", "sentinel-llm")
            resource_attrs_env = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "env=development")
            
            # Parse resource attributes
            resource_attrs = {}
            for attr in resource_attrs_env.split(","):
                if "=" in attr:
                    key, value = attr.split("=", 1)
                    resource_attrs[key] = value
            
            service_env = resource_attrs.get("env", "development")

            if otlp_traces_exporter == "otlp" and otlp_metrics_exporter == "otlp":
                # ✅ OTLP mode (Collector)
                span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)

                logger.info("Telemetry: OTLP mode (Collector endpoint enabled)")
                logger.info(f"OTLP Endpoint: {otlp_endpoint}")
                logger.info(f"Service: {service_name}, Environment: {service_env}")
            else:
                # ✅ Fallback: console exporters
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                from opentelemetry.sdk.metrics.export import ConsoleMetricExporter

                span_exporter = ConsoleSpanExporter()
                metric_exporter = ConsoleMetricExporter()

                logger.info("Telemetry: Console mode (fallback exporters enabled)")

            # ----------------------------
            # RESOURCE ATTRIBUTES
            # ----------------------------
            resource = Resource.create({
                ResourceAttributes.SERVICE_NAME: service_name,
                ResourceAttributes.SERVICE_VERSION: "1.0.0",
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT: service_env,
                ResourceAttributes.TELEMETRY_SDK_NAME: "opentelemetry-python",
                ResourceAttributes.TELEMETRY_SDK_VERSION: "1.21.0",
            })

            # ----------------------------
            # TRACING PROVIDER
            # ----------------------------
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)
            self.tracer = trace.get_tracer(service_name)

            # ----------------------------
            # METRICS PROVIDER
            # ----------------------------
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=5000,
            )
            metrics.set_meter_provider(MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            ))
            self.meter = metrics.get_meter(service_name)

            # Custom metrics
            self._initialize_metrics()

            self._initialized = True
            logger.info("Telemetry initialized successfully")

        except Exception as e:
            # Degraded mode (still lets app run)
            logger.exception(f"Telemetry init failed, degraded mode: {e}")
            self.tracer = trace.get_tracer(__name__)
            self.meter = metrics.get_meter(__name__)
            self._initialize_metrics()

    def _initialize_metrics(self) -> None:
        """Define custom OpenTelemetry metrics as specified in requirements."""
        # Request metrics
        self.metrics["sentinel_llm_request_count"] = self.meter.create_counter(
            name="sentinel_llm.request.count",
            description="Total request count",
            unit="requests",
        )

        self.metrics["sentinel_llm_request_latency"] = self.meter.create_histogram(
            name="sentinel_llm.request.latency_ms",
            description="Request latency in milliseconds",
            unit="ms",
        )

        self.metrics["sentinel_llm_request_errors"] = self.meter.create_counter(
            name="sentinel_llm.request.errors",
            description="Total request errors",
            unit="errors",
        )

        # LLM-specific metrics
        self.metrics["sentinel_llm_llm_failures"] = self.meter.create_counter(
            name="sentinel_llm.llm.failures",
            description="LLM call failures",
            unit="failures",
        )

        self.metrics["sentinel_llm_security_prompt_injection"] = self.meter.create_counter(
            name="sentinel_llm.security.prompt_injection",
            description="Prompt injection attempts detected",
            unit="attempts",
        )

        # Legacy metrics for compatibility
        self.metrics["llm_request_latency"] = self.meter.create_histogram(
            name="llm.request.latency",
            description="Latency of LLM requests",
            unit="ms",
        )

        self.metrics["llm_tokens_input"] = self.meter.create_counter(
            name="llm.tokens.input",
            description="Input token count",
            unit="tokens",
        )

        self.metrics["llm_tokens_output"] = self.meter.create_counter(
            name="llm.tokens.output",
            description="Output token count",
            unit="tokens",
        )

        self.metrics["llm_cost_estimate"] = self.meter.create_counter(
            name="llm.cost.estimate",
            description="Estimated LLM cost",
            unit="USD",
        )

        self.metrics["llm_prompt_injection_detected"] = self.meter.create_counter(
            name="llm.prompt.injection.detected",
            description="Prompt injection attempts detected",
            unit="attempts",
        )

        self.metrics["llm_errors"] = self.meter.create_counter(
            name="llm.errors",
            description="LLM errors",
            unit="errors",
        )

        self.metrics["llm_requests"] = self.meter.create_counter(
            name="llm.requests",
            description="Total LLM requests",
            unit="requests",
        )

    # ----------------------------
    # SPAN LIFECYCLE (FIXED)
    # ----------------------------
    def start_llm_span(self) -> Dict[str, Any]:
        """
        Start a span and attach it to current context.
        Returns span context object to end later.
        """
        span = self.tracer.start_span("llm.request")
        ctx = trace.set_span_in_context(span)
        token = attach(ctx)
        return {"span": span, "token": token}

    def end_llm_span(self, span_ctx: Dict[str, Any]) -> None:
        """End span and detach context (ensures export happens)."""
        span = span_ctx["span"]
        token = span_ctx["token"]
        span.end()
        detach(token)

    # ----------------------------
    # REQUEST CONTEXT MANAGEMENT
    # ----------------------------
    def set_request_context(self, request_id: str = None) -> str:
        """Set request context for correlation."""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        self.request_id = request_id
        return request_id

    def get_request_context(self) -> str:
        """Get current request context."""
        return self.request_id or "no-request-id"

    # ----------------------------
    # METRIC RECORDING (UPDATED)
    # ----------------------------
    def record_request_metrics(self, latency_ms: float, status: str = "success", 
                             error_type: str = None, **attributes) -> None:
        """Record request-level metrics."""
        # Request count
        self.metrics["sentinel_llm_request_count"].add(
            1, 
            attributes={
                "status": status,
                "environment": os.getenv("DATADOG_ENV", "production"),
                **attributes
            }
        )

        # Request latency
        self.metrics["sentinel_llm_request_latency"].record(
            latency_ms,
            attributes={
                "status": status,
                "environment": os.getenv("DATADOG_ENV", "production"),
                **attributes
            }
        )

        # Request errors
        if status == "error":
            self.metrics["sentinel_llm_request_errors"].add(
                1,
                attributes={
                    "error_type": error_type or "unknown",
                    "environment": os.getenv("DATADOG_ENV", "production"),
                    **attributes
                }
            )

    def record_llm_metrics(self, **kwargs) -> None:
        """Record LLM-specific metrics."""
        model = kwargs.get("model", "unknown")
        status = kwargs.get("status", "success")
        error_type = kwargs.get("error_type")
        latency_ms = kwargs.get("latency_ms", 0)

        # LLM failures
        if kwargs.get("llm_failure"):
            self.metrics["sentinel_llm_llm_failures"].add(
                1,
                attributes={
                    "model": model,
                    "error_type": error_type or "unknown",
                    "environment": os.getenv("DATADOG_ENV", "production")
                }
            )

        # Prompt injection detection
        if kwargs.get("prompt_injection_detected"):
            self.metrics["sentinel_llm_security_prompt_injection"].add(
                1,
                attributes={
                    "method": kwargs.get("detection_method", "regex"),
                    "model": model,
                    "environment": os.getenv("DATADOG_ENV", "production")
                }
            )

        # Legacy metrics for compatibility
        if latency_ms > 0:
            self.metrics["llm_request_latency"].record(
                latency_ms,
                attributes={"model": model, "status": status}
            )

        if "input_tokens" in kwargs:
            self.metrics["llm_tokens_input"].add(
                kwargs["input_tokens"],
                attributes={"model": model}
            )

        if "output_tokens" in kwargs:
            self.metrics["llm_tokens_output"].add(
                kwargs["output_tokens"],
                attributes={"model": model}
            )

        if "cost_estimate" in kwargs:
            self.metrics["llm_cost_estimate"].add(
                kwargs["cost_estimate"],
                attributes={"model": model}
            )

        if error_type:
            self.metrics["llm_errors"].add(
                1,
                attributes={"type": error_type, "model": model}
            )

        # Always count requests
        self.metrics["llm_requests"].add(1, attributes={"model": model, "status": status})

    def record_metrics(self, **kwargs) -> None:
        """Legacy method for backward compatibility."""
        self.record_llm_metrics(**kwargs)

    # ----------------------------
    # STRUCTURED LOGGING
    # ----------------------------
    def log_structured(self, level: str, message: str, **kwargs) -> None:
        """Log structured data for Datadog parsing."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "service": os.getenv("DATADOG_SERVICE", "sentinel-llm"),
            "environment": os.getenv("DATADOG_ENV", "production"),
            "request_id": self.get_request_context(),
            **kwargs
        }
        
        # Get trace context if available
        current_span = trace.get_current_span()
        if current_span:
            span_context = current_span.get_span_context()
            log_data.update({
                "trace_id": f"0x{span_context.trace_id:016x}",
                "span_id": f"0x{span_context.span_id:016x}"
            })
        
        # Log as JSON
        log_message = json.dumps(log_data)
        
        if level.upper() == "ERROR":
            logger.error(log_message)
        elif level.upper() == "WARNING":
            logger.warning(log_message)
        elif level.upper() == "DEBUG":
            logger.debug(log_message)
        else:
            logger.info(log_message)


# Global telemetry manager
telemetry_manager = TelemetryManager()
telemetry_manager.initialize()


def initialize_telemetry() -> None:
    """
    Initialize OpenTelemetry instrumentation.
    
    This function ensures the telemetry manager is properly initialized
    and can be called during application startup.
    """
    if not telemetry_manager._initialized:
        telemetry_manager.initialize()
        logger.info("Telemetry initialized via initialize_telemetry() function")


def instrument_fastapi_app(app) -> None:
    """Instrument FastAPI with OpenTelemetry auto-instrumentation."""
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI instrumentation enabled")
