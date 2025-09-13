from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

class Metrics:
    def __init__(self, tracer_name, resource: Resource):
        self._metric_exporter = OTLPMetricExporter(timeout=10)
        self._metric_reader = PeriodicExportingMetricReader(
            exporter=self._metric_exporter,
            export_interval_millis=5000,  # Export every 5 seconds
            export_timeout_millis=10000    # 10 second timeout
        )

        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[self._metric_reader]
        )
        
        metrics.set_meter_provider(meter_provider)
        self._meter = metrics.get_meter(tracer_name)
        
        self._counter = self._meter.create_counter(
            name="function.calls",
            description="Number of function calls traced",
            unit="1"
        )
        
        self._operation_counter = self._meter.create_counter(
            name="operation.count",
            description="Number of operations performed",
            unit="1"
        )

    @property
    def counter(self):
        return self._counter
    
    @property
    def operation_counter(self):
        return self._operation_counter
        
    def force_flush(self, timeout_millis: int = 10000):
        if self._metric_reader:
            try:
                metrics.get_meter_provider().force_flush(timeout_millis=timeout_millis)
            except Exception:
                pass
