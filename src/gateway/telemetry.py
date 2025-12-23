"""
OpenTelemetry instrumentation for SentinelLLM
- PROD: Datadog via OTLP HTTP endpoint
- DEV: Console exporters (no cloud accounts required)
"""

import logging
from typing import Dict, Any

from opentelemetry import trace, metrics
from opentelemetry.context import attach, detach
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

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

    def initialize(self) -> None:
        """Initialize OpenTelemetry providers and exporters."""
        if self._initialized:
            return

        try:
            # ----------------------------
            # EXPORTER CONFIG
            # ----------------------------
            if self.settings.DATADOG_API_KEY:
                # ✅ Datadog OTLP ingest endpoint
                endpoint = f"https://api.{self.settings.DATADOG_SITE}/api/v2/otlp"
                headers = {"DD-API-KEY": self.settings.DATADOG_API_KEY}

                span_exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
                metric_exporter = OTLPMetricExporter(endpoint=endpoint, headers=headers)

                logger.info("Telemetry: PROD mode (Datadog OTLP exporter enabled)")
            else:
                # ✅ DEV fallback: console exporters (no accounts needed)
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                from opentelemetry.sdk.metrics.export import ConsoleMetricExporter

                span_exporter = ConsoleSpanExporter()
                metric_exporter = ConsoleMetricExporter()

                logger.info("Telemetry: DEV mode (console exporters enabled)")

            # ----------------------------
            # TRACING PROVIDER
            # ----------------------------
            tracer_provider = TracerProvider()
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)
            self.tracer = trace.get_tracer(self.settings.OTEL_SERVICE_NAME)

            # ----------------------------
            # METRICS PROVIDER
            # ----------------------------
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=5000,
            )
            metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
            self.meter = metrics.get_meter(self.settings.OTEL_SERVICE_NAME)

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
        """Define custom OpenTelemetry metrics."""
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
    # METRIC RECORDING
    # ----------------------------
    def record_metrics(self, **kwargs) -> None:
        """Record LLM metrics for Datadog dashboards and monitors."""
        model = kwargs.get("model", "unknown")

        if "latency_ms" in kwargs:
            self.metrics["llm_request_latency"].record(
                kwargs["latency_ms"],
                attributes={"model": model},
            )

        if "input_tokens" in kwargs:
            self.metrics["llm_tokens_input"].add(
                kwargs["input_tokens"],
                attributes={"model": model},
            )

        if "output_tokens" in kwargs:
            self.metrics["llm_tokens_output"].add(
                kwargs["output_tokens"],
                attributes={"model": model},
            )

        if "cost_estimate" in kwargs:
            self.metrics["llm_cost_estimate"].add(
                kwargs["cost_estimate"],
                attributes={"model": model},
            )

        if kwargs.get("prompt_injection_detected"):
            self.metrics["llm_prompt_injection_detected"].add(
                1,
                attributes={"method": kwargs.get("detection_method", "regex")},
            )

        if kwargs.get("error"):
            self.metrics["llm_errors"].add(
                1,
                attributes={"type": kwargs.get("error_type", "unknown"), "model": model},
            )

        # Always count requests
        self.metrics["llm_requests"].add(1, attributes={"model": model})


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
