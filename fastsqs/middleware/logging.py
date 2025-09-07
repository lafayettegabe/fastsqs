import json
import time
import traceback
from typing import Callable, List, Optional

from .base import Middleware
from ..utils import shallow_mask
from ..logger.logger import Logger

class LoggingMiddleware(Middleware):
    def __init__(
        self,
        logger: Optional[Callable[[dict], None]] = None,
        level: str = "INFO",
        include_payload: bool = True,
        include_record: bool = False,
        include_context: bool = False,
        mask_fields: Optional[List[str]] = None,
        verbose: bool = True,
        use_custom_logger: bool = True,
    ):
        self.level = level
        self.include_payload = include_payload
        self.include_record = include_record
        self.include_context = include_context
        self.mask_fields = mask_fields or []
        self.verbose = verbose
        
        if logger is None:
            if use_custom_logger and Logger is not None:
                try:
                    self._custom_logger = Logger()
                    def _custom_logger_func(obj: dict) -> None:
                        level = obj.get("lvl", "INFO").lower()
                        message = obj.get("message", "")
                        data = {k: v for k, v in obj.items() if k != "message"}
                        self._custom_logger.log(level, message, **data)
                    self.logger = _custom_logger_func
                except Exception:
                    def _default_logger(obj: dict) -> None:
                        print(json.dumps(obj, ensure_ascii=False))
                    self.logger = _default_logger
            else:
                def _default_logger(obj: dict) -> None:
                    print(json.dumps(obj, ensure_ascii=False))
                self.logger = _default_logger
        else:
            self.logger = logger

    def log(self, level: str, message: str, **data) -> None:
        entry = {
            "ts": time.time(),
            "lvl": level.upper(),
            "message": message,
            **data
        }
        self.logger(entry)

    async def before(self, payload, record, context, ctx):
        entry = {
            "ts": time.time(),
            "lvl": self.level,
            "stage": "before_processing",
            "msg_id": record.get("messageId"),
            "middleware": "LoggingMiddleware",
        }
        
        entry["message_info"] = {
            "source": record.get("eventSource"),
            "source_arn": record.get("eventSourceARN"),
            "aws_region": record.get("awsRegion"),
            "approximate_receive_count": record.get("attributes", {}).get("ApproximateReceiveCount"),
            "sent_timestamp": record.get("attributes", {}).get("SentTimestamp"),
        }
        
        entry["processing_info"] = {
            "route_path": ctx.get("route_path", []),
            "message_type": payload.get("type") if isinstance(payload, dict) else None,
            "queue_type": ctx.get("queueType"),
            "context_aws_request_id": getattr(context, 'aws_request_id', None),
            "context_function_name": getattr(context, 'function_name', None),
            "context_memory_limit": getattr(context, 'memory_limit_in_mb', None),
        }
        
        if self.include_payload:
            entry["payload"] = shallow_mask(payload, self.mask_fields)
        if self.include_record:
            entry["record"] = record
        if self.include_context:
            entry["context_repr"] = repr(context)
            
        if self.verbose:
            entry["ctx_keys"] = list(ctx.keys())
            
        self.logger(entry)

    async def after(self, payload, record, context, ctx, error):
        entry = {
            "ts": time.time(),
            "lvl": "ERROR" if error else self.level,
            "stage": "after_processing",
            "msg_id": record.get("messageId"),
            "middleware": "LoggingMiddleware",
        }
        
        entry["processing_results"] = {
            "duration_ms": ctx.get("duration_ms"),
            "route_path": ctx.get("route_path", []),
            "message_type": ctx.get("message_type"),
            "handler_result_type": type(ctx.get("handler_result")).__name__ if ctx.get("handler_result") is not None else None,
            "idempotency_hit": ctx.get("idempotency_hit", False),
            "retry_attempt": ctx.get("retry_attempt", 0),
            "should_retry": ctx.get("should_retry", False),
        }
        
        if error:
            entry["error_details"] = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "error_repr": repr(error),
                "traceback": traceback.format_exc(),
                "error_history": ctx.get("error_history", []),
            }
        
        if self.verbose:
            entry["context_summary"] = {
                "all_ctx_keys": list(ctx.keys()),
                "visibility_timeout": ctx.get("visibility_timeout"),
                "visibility_warned": ctx.get("visibility_warned"),
                "concurrency_stats": ctx.get("concurrency_stats"),
            }
        
        if self.include_payload:
            entry["payload"] = shallow_mask(payload, self.mask_fields)
        if self.include_record:
            entry["record"] = record
        if self.include_context:
            entry["context_repr"] = repr(context)
            
        self.logger(entry)