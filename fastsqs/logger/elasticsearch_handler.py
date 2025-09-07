import logging
from enum import Enum

from .config import OtelConfig
from .utils import get_elastic_client, build_log_entry


class Environment(Enum):
    PRODUCTION = "production"
    HOMOLOG = "homolog"
    LOCAL = "local"


otel_config = OtelConfig()
OTEL_ENVIRONMENT = otel_config.environment
OTEL_SERVICE_NAME = otel_config.service_name
USE_OTEL = otel_config.use_otel


class ElasticsearchHandler(logging.Handler):
    ELASTICSEARCH_ENVIRONMENTS = {
        Environment.PRODUCTION.value,
        Environment.HOMOLOG.value
    }
    
    def __init__(self, index_name=None, use_otel=USE_OTEL):
        super().__init__()

        self.enable_logging = use_otel and OTEL_ENVIRONMENT in self.ELASTICSEARCH_ENVIRONMENTS

        if self.enable_logging:
            self.es_client = get_elastic_client()
            self.index_name = (
                index_name or
                f"logs-{OTEL_SERVICE_NAME}-{OTEL_ENVIRONMENT}"
            )

    def emit(self, record):
        try:
            if not self.enable_logging:
                return

            log_entry = build_log_entry(
                record=record,
                service_name=OTEL_SERVICE_NAME,
                environment=OTEL_ENVIRONMENT,
                formatter=self
            )

            if self.es_client:
                self.es_client.index(index=self.index_name, document=log_entry)

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to send log to Elasticsearch: {e}"
            )
