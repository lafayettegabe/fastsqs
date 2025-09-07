from datetime import datetime, timezone
from elasticsearch import Elasticsearch
from .config import OtelConfig

otel_config = OtelConfig()
ELASTIC_URL = otel_config.elastic_url
ELASTIC_TOKEN = otel_config.elastic_token

_es_client = None


def filter_extra_fields(record_dict):
    allowed_fields = {"data"}
    return {key: value for key, value in record_dict.items() if key in allowed_fields}


def get_elastic_client():
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(
            ELASTIC_URL, 
            api_key=ELASTIC_TOKEN,
            request_timeout=10
        )
    return _es_client


def build_log_entry(record, request_id, service_name, environment, formatter):
    return {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "log.level": record.levelname.lower(),
        "message": formatter.format(record),
        "app.name": service_name,
        "x-request-id": request_id,
        "service.name": service_name,
        "environment": environment,
        "extra": filter_extra_fields(record.__dict__),
        "agent": {
            "name": "opentelemetry/python",
        },
    }
