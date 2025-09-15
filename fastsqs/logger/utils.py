from datetime import datetime, timezone
from elasticsearch import Elasticsearch
from .config import OtelConfig

otel_config = OtelConfig()
ELASTIC_URL = otel_config.elastic_url
ELASTIC_TOKEN = otel_config.elastic_token

_es_client = None


def filter_extra_fields(record_dict):
    """Filter and return allowed extra fields from log record."""
    allowed_fields = {"data", "extra", "custom"}
    filtered = {}
    
    for key, value in record_dict.items():
        if key in allowed_fields:
            # If it's the data field and it's a dict, include it directly for proper JSON formatting
            if key == "data" and isinstance(value, dict):
                filtered.update(value)
            else:
                filtered[key] = value
    
    return filtered


def get_elastic_client():
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(
            ELASTIC_URL, 
            api_key=ELASTIC_TOKEN,
            request_timeout=10
        )
    return _es_client


def build_log_entry(record, service_name, environment, formatter,
                     context_info=None):
    """Build ECS-compliant log entry.

    Args:
        record: LogRecord instance
        service_name: Name of the service
        environment: Environment (production, homolog, local)
        formatter: Log formatter
        context_info: Dictionary with context information
                     (request_id, lambda_context, etc.)
    """
    log_entry = {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "log.level": record.levelname.lower(),
        "message": formatter.format(record),
        "service": {
            "name": service_name,
            "environment": environment
        },
        "agent": {
            "name": "opentelemetry/python",
            "version": "1.0.0"
        },
        "labels": filter_extra_fields(record.__dict__),
    }

    if context_info:
        if context_info.get('request_id'):
            log_entry["trace"] = {"id": context_info['request_id']}

        if context_info.get('lambda_context'):
            lambda_ctx = context_info['lambda_context']
            log_entry["cloud"] = {
                "provider": "aws",
                "service": {
                    "name": "lambda"
                }
            }
            log_entry["faas"] = {
                "name": getattr(lambda_ctx, 'function_name', None),
                "version": getattr(lambda_ctx, 'function_version', None),
                "execution": getattr(lambda_ctx, 'aws_request_id', None)
            }
            if (not context_info.get('request_id') and
                    hasattr(lambda_ctx, 'aws_request_id')):
                log_entry["trace"] = {"id": lambda_ctx.aws_request_id}

        if context_info.get('custom_fields'):
            log_entry["labels"].update(context_info['custom_fields'])

    return log_entry
