from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


def configure_tracing() -> None:
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(TracerProvider())
