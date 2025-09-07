import os


class OtelConfig:
    def __init__(self):
        self.use_otel = os.getenv("USE_OTEL", "true").lower() != "false"
        self.environment = os.getenv("OTEL_ENVIRONMENT", "production")
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "fastsqs-service")
        self.tracer_name = os.getenv("OTEL_TRACER_NAME", "fastsqs-tracer")
        self.elastic_url = os.getenv("OTEL_ELASTIC_URL", None)
        self.elastic_token = os.getenv("OTEL_ELASTIC_TOKEN", None)
        self.exporter_endpoint = os.getenv("OTEL_EXPORTER_ENDPOINT", "http://localhost:4318/v1/traces")
