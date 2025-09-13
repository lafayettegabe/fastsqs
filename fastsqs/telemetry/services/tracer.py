from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

class Tracer:
    def __init__(self, tracer_name, resource):
        tracer_provider = TracerProvider(resource=resource)
        otel_exporter = OTLPSpanExporter(timeout=10)
        self._batch_processor = BatchSpanProcessor(otel_exporter)
        tracer_provider.add_span_processor(self._batch_processor)
        trace.set_tracer_provider(tracer_provider)
        self._tracer = trace.get_tracer(tracer_name)

    @property
    def tracer(self):
        return self._tracer
        
    def force_flush(self, timeout_millis: int = 10000):
        if self._batch_processor:
            try:
                self._batch_processor.force_flush(timeout_millis=timeout_millis)
            except Exception:
                pass
