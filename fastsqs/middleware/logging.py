import json
import time
from typing import Callable, List, Optional

from .base import Middleware
from ..utils import shallow_mask


class LoggingMiddleware(Middleware):
    def __init__(
        self,
        logger: Optional[Callable[[dict], None]] = None,
        level: str = "INFO",
        include_payload: bool = True,
        include_record: bool = False,
        include_context: bool = False,
        mask_fields: Optional[List[str]] = None,
    ):
        self.level = level
        self.include_payload = include_payload
        self.include_record = include_record
        self.include_context = include_context
        self.mask_fields = mask_fields or []
        if logger is None:
            def _default_logger(obj: dict) -> None:
                print(json.dumps(obj, ensure_ascii=False))
            self.logger = _default_logger
        else:
            self.logger = logger

    async def before(self, payload, record, context, ctx):
        entry = {
            "ts": time.time(),
            "lvl": self.level,
            "stage": "before",
            "msg_id": record.get("messageId"),
            "route": ctx.get("route_path", []),
        }
        if self.include_payload:
            entry["payload"] = shallow_mask(payload, self.mask_fields)
        if self.include_record:
            entry["record"] = record
        if self.include_context:
            entry["context_repr"] = repr(context)
        self.logger(entry)

    async def after(self, payload, record, context, ctx, error):
        entry = {
            "ts": time.time(),
            "lvl": "ERROR" if error else self.level,
            "stage": "after",
            "msg_id": record.get("messageId"),
            "route": ctx.get("route_path", []),
            "duration_ms": ctx.get("duration_ms"),
            "error": None if not error else repr(error),
        }
        if self.include_payload:
            entry["payload"] = shallow_mask(payload, self.mask_fields)
        if self.include_record:
            entry["record"] = record
        if self.include_context:
            entry["context_repr"] = repr(context)
        self.logger(entry)