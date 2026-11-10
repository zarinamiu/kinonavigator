from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider(
    resource=Resource.create({"service.name": "kinonavigator"})
)
exporter = OTLPSpanExporter(
    endpoint="http://localhost:6006/v1/traces"
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("kinonavigator")

with tracer.start_as_current_span("manual-smoke-test") as span:
    span.set_attribute("test.kind", "observability-smoke-test")
    span.set_attribute("project", "kinonavigator")
    print("Тестовая трасса отправлена")

provider.force_flush()
