"""
OpenTelemetry tracing initialisation for SentinelOps AI.

For development, traces are written to stdout via ConsoleSpanExporter.
For production with Tempo, install opentelemetry-exporter-otlp and configure:
  OTEL_EXPORTER_OTLP_ENDPOINT=http://<tempo-host>:4318
  OTEL_SERVICE_NAME=sentinelops-api
"""
from __future__ import annotations

import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = structlog.get_logger(__name__)


def configure_tracing() -> None:
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        return

    from core.config import get_settings
    settings = get_settings()

    tracer_provider = TracerProvider()

    # Attempt OTLP export to Tempo if the exporter package is installed.
    # In development or when the package is absent, fall back to console.
    _exporter_added = False
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore[import]

        tempo_endpoint = settings.tempo_url.rstrip("/") + "/v1/traces"
        otlp_exporter = OTLPSpanExporter(endpoint=tempo_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("tracing_configured", backend="otlp", endpoint=tempo_endpoint)
        _exporter_added = True
    except ImportError:
        pass

    if not _exporter_added:
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("tracing_configured", backend="console")

    trace.set_tracer_provider(tracer_provider)


def get_tracer(name: str = "sentinelops"):
    return trace.get_tracer(name)
