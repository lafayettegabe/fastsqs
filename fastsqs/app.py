from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from .events import SQSEvent
from .types import QueueType, Handler
from .exceptions import RouteNotFound, InvalidMessage
from .middleware import Middleware, run_middlewares
from .middleware.idempotency import IdempotencyHit
from .middleware.logging import LoggingMiddleware
from .routing import QueueRouter
from .utils import group_records_by_message_group, invoke_handler
from .presets import MiddlewarePreset


class FastSQS:
    
    def __init__(
        self,
        title: str = "FastSQS App",
        description: str = "",
        version: str = "1.0.0",
        debug: bool = False,
        queue_type: QueueType = QueueType.STANDARD,
        message_type_key: str = "type",
        flexible_matching: bool = True,
        max_concurrent_messages: int = 10,
        enable_partial_batch_failure: bool = True
    ):
        self.title = title
        self.description = description
        self.version = version
        self.debug = debug
        self.queue_type = queue_type
        self.message_type_key = message_type_key
        self.flexible_matching = flexible_matching
        self.max_concurrent_messages = max_concurrent_messages
        self.enable_partial_batch_failure = enable_partial_batch_failure
        
        self._routes: Dict[str, tuple[Type[SQSEvent], Handler]] = {}
        self._route_lookup: Dict[str, str] = {}
        self._routers: List[QueueRouter] = []
        
        self._middlewares: List[Middleware] = []
        self._default_handler: Optional[Handler] = None
    
    def route(
        self, 
        event_model: Type[SQSEvent],
        *,
        middlewares: Optional[List[Middleware]] = None
    ) -> Callable[[Handler], Handler]:
        primary_type = event_model.get_message_type()
        
        def decorator(handler: Handler) -> Handler:
            if primary_type in self._routes:
                raise ValueError(f"Handler for message type '{primary_type}' already exists")
            
            self._routes[primary_type] = (event_model, handler)
            
            if self.flexible_matching:
                variants = event_model.get_message_type_variants()
                for variant in variants:
                    if variant not in self._route_lookup:
                        self._route_lookup[variant] = primary_type
                    elif self.debug:
                        self._log("warning", f"Message type variant conflicts with existing route", variant=variant)
            
            return handler
        
        return decorator

    def default(self) -> Callable[[Handler], Handler]:
        def decorator(handler: Handler) -> Handler:
            self._default_handler = handler
            return handler
        return decorator

    def _find_route(self, message_type: str) -> Optional[tuple[Type[SQSEvent], Handler]]:
        if message_type in self._routes:
            return self._routes[message_type]
        
        if self.flexible_matching and message_type in self._route_lookup:
            primary_type = self._route_lookup[message_type]
            return self._routes[primary_type]
        
        return None

    def include_router(self, router: QueueRouter) -> None:
        self._routers.append(router)

    def add_middleware(self, middleware: Middleware) -> None:
        middleware._app = self
        self._middlewares.append(middleware)
    
    def use(self, middleware: Middleware) -> None:
        self.add_middleware(middleware)

    def _log(self, level: str, message: str, **data) -> None:
        for middleware in self._middlewares:
            if isinstance(middleware, LoggingMiddleware) and hasattr(middleware, 'log'):
                middleware.log(level, message, **data)
                return

    def use_preset(self, preset: str, **kwargs) -> None:
        if preset == "production":
            middlewares = MiddlewarePreset.production(**kwargs)
        elif preset == "development":
            middlewares = MiddlewarePreset.development(**kwargs)
        elif preset == "minimal":
            middlewares = MiddlewarePreset.minimal(**kwargs)
        else:
            raise ValueError(f"Unknown preset: {preset}. Available: production, development, minimal")
        
        for middleware in middlewares:
            self.add_middleware(middleware)

    def set_queue_type(self, queue_type: QueueType) -> None:
        self.queue_type = queue_type
        if self.debug:
            self._log("info", f"Queue type set to: {queue_type.value}")

    def is_fifo_queue(self) -> bool:
        return self.queue_type == QueueType.FIFO

    async def _handle_record(self, record: dict, context: Any) -> Optional[Any]:
        body_str = record.get("body", "")
        msg_id = record.get("messageId") or record.get("message_id") or "UNKNOWN"

        self._log("info", f"Starting record processing", msg_id=msg_id)
        self._log("debug", f"Raw body", msg_id=msg_id, body=body_str[:500] + ('...' if len(body_str) > 500 else ''))

        try:
            payload = json.loads(body_str, parse_float=Decimal) if body_str else {}
            if not isinstance(payload, dict):
                raise InvalidMessage("Message body must be a JSON object")
            self._log("debug", f"Parsed payload", msg_id=msg_id, payload=payload)
        except json.JSONDecodeError as e:
            self._log("error", f"JSON decode error", msg_id=msg_id, error=str(e))
            raise InvalidMessage(f"Invalid JSON in message body: {e}")

        ctx: Dict[str, Any] = {
            "messageId": msg_id,
            "record": record,
            "context": context,
            "route_path": [],
            "queueType": self.queue_type.value,
        }

        if self.is_fifo_queue():
            attributes = record.get("attributes", {})
            ctx["fifoInfo"] = {
                "messageGroupId": attributes.get("messageGroupId"),
                "messageDeduplicationId": attributes.get("messageDeduplicationId"),
                "queueType": "fifo"
            }
            self._log("debug", f"FIFO info", msg_id=msg_id, fifo_info=ctx["fifoInfo"])

        err: Optional[Exception] = None
        result: Any = None
        
        try:
            self._log("debug", f"Running 'before' middleware chain", msg_id=msg_id)
            await run_middlewares(self._middlewares, "before", payload, record, context, ctx)
            self._log("debug", f"'before' middleware chain completed", msg_id=msg_id)
        except IdempotencyHit as idempotency_hit:
            self._log("info", f"Idempotency hit, returning cached result", msg_id=msg_id, key=idempotency_hit.key)
            if self.debug:
                self._log("debug", f"Idempotency hit for message", msg_id=msg_id, key=idempotency_hit.key)
            ctx["idempotency_result"] = idempotency_hit.result
            ctx["idempotency_hit"] = True
            await run_middlewares(self._middlewares, "after", payload, record, context, ctx, None)
            return idempotency_hit.result
        
        try:
            handled = False
            
            message_type = payload.get(self.message_type_key)
            self._log("debug", f"Message type", msg_id=msg_id, message_type=message_type)
            
            if message_type:
                route = self._find_route(message_type)
                if route:
                    event_model, handler = route
                    self._log("debug", f"Found route for {message_type}", msg_id=msg_id, handler=handler.__name__)
                    
                    try:
                        event_instance = event_model.model_validate(payload)
                        self._log("debug", f"Payload validation successful", msg_id=msg_id)
                    except ValidationError as e:
                        self._log("error", f"Validation failed", msg_id=msg_id, error=str(e))
                        raise InvalidMessage(f"Validation failed for {message_type}: {e}")

                    ctx["message_type"] = message_type
                    self._log("debug", f"Invoking handler", msg_id=msg_id, handler=handler.__name__)
                    result = await invoke_handler(handler, msg=event_instance, record=record, context=context, ctx=ctx)
                    self._log("debug", f"Handler completed successfully", msg_id=msg_id, result_type=type(result).__name__)
                    ctx["handler_result"] = result
                    handled = True
                else:
                    self._log("warning", f"No route found for message type", msg_id=msg_id, message_type=message_type)

            if not handled and self._routers:
                self._log("debug", f"Trying routers", msg_id=msg_id, router_count=len(self._routers))
                for i, router in enumerate(self._routers):
                    self._log("debug", f"Trying router {i}", msg_id=msg_id, router_key=router.key)
                    if await router.dispatch(payload, record, context, ctx, root_payload=payload):
                        self._log("debug", f"Router {i} handled the message", msg_id=msg_id)
                        handled = True
                        result = ctx.get("handler_result")
                        break
                    else:
                        self._log("debug", f"Router {i} did not handle the message", msg_id=msg_id)

            if not handled:
                if self._default_handler:
                    self._log("debug", f"Using default handler", msg_id=msg_id)
                    result = await invoke_handler(self._default_handler, payload=payload, record=record, context=context, ctx=ctx)
                    ctx["handler_result"] = result
                else:
                    available_routes = list(self._routes.keys())
                    available_routers = [r.key for r in self._routers]
                    error_msg = (f"No handler found for message. "
                               f"Available FastSQS routes: {available_routes}, "
                               f"Available router keys: {available_routers}")
                    self._log("error", error_msg, msg_id=msg_id, available_routes=available_routes, available_routers=available_routers)
                    raise RouteNotFound(error_msg)
                    
        except Exception as e:
            self._log("error", f"Handler error", msg_id=msg_id, error_type=type(e).__name__, error=str(e))
            err = e
            raise
        finally:
            self._log("debug", f"Running 'after' middleware chain", msg_id=msg_id)
            await run_middlewares(self._middlewares, "after", payload, record, context, ctx, err)
            self._log("debug", f"'after' middleware chain completed", msg_id=msg_id)
        
        self._log("info", f"Record processing completed successfully", msg_id=msg_id)
        return result

    async def _handle_event(self, event: dict, context: Any) -> dict:
        records = event.get("Records", [])
        if not records:
            return {"batchItemFailures": []}
        
        if self.debug:
            queue_info = f"queue_type={self.queue_type.value}, records={len(records)}"
            self._log("info", f"Processing event", queue_info=queue_info)
        
        if self.is_fifo_queue():
            return await self._handle_fifo_event(records, context)
        else:
            return await self._handle_standard_event(records, context)
    
    async def _handle_standard_event(self, records: List[dict], context: Any) -> dict:
        failures: List[Dict[str, str]] = []
        
        self._log("info", f"Processing records in standard queue mode", record_count=len(records))
        
        semaphore = asyncio.Semaphore(self.max_concurrent_messages)
        
        async def process_with_semaphore(record):
            async with semaphore:
                return await self._handle_record_safe(record, context)
        
        tasks = [asyncio.create_task(process_with_semaphore(rec)) for rec in records]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                msg_id = records[i].get("messageId", "UNKNOWN")
                self._log("error", f"Record failed", msg_id=msg_id, error_type=type(result).__name__, error=str(result))
                if self.debug:
                    self._log("debug", f"Record failed", msg_id=msg_id, error=str(result))
                if self.enable_partial_batch_failure:
                    failures.append({"itemIdentifier": msg_id})
            else:
                msg_id = records[i].get("messageId", "UNKNOWN")
                self._log("debug", f"Record succeeded", msg_id=msg_id)
        
        self._log("info", f"Batch processing completed", succeeded=len(records) - len(failures), failed=len(failures))
        return {"batchItemFailures": failures}
    
    async def _handle_fifo_event(self, records: List[dict], context: Any) -> dict:
        failures: List[Dict[str, str]] = []
        
        message_groups = group_records_by_message_group(records)
        
        if self.debug:
            self._log("info", f"FIFO processing", record_count=len(records), group_count=len(message_groups))
        
        async def process_group(group_id: str, group_records: List[dict]):
            group_failures = []
            if self.debug:
                self._log("debug", f"Processing group", group_id=group_id, record_count=len(group_records))
            
            for rec in group_records:
                try:
                    await self._handle_record(rec, context)
                except Exception as e:
                    msg_id = rec.get("messageId", "UNKNOWN")
                    if self.debug:
                        self._log("error", f"FIFO record failed", msg_id=msg_id, group_id=group_id, error=str(e))
                    if self.enable_partial_batch_failure:
                        group_failures.append({"itemIdentifier": msg_id})
            
            return group_failures
        
        group_tasks = [
            asyncio.create_task(process_group(group_id, group_records))
            for group_id, group_records in message_groups.items()
        ]
        
        group_results = await asyncio.gather(*group_tasks, return_exceptions=True)
        
        for result in group_results:
            if isinstance(result, list):
                failures.extend(result)
            elif isinstance(result, Exception):
                if self.debug:
                    self._log("error", f"Message group processing failed", error=str(result))
        
        return {"batchItemFailures": failures}
    
    async def _handle_record_safe(self, record: dict, context: Any) -> None:
        msg_id = record.get("messageId", "UNKNOWN")
        try:
            await self._handle_record(record, context)
        except Exception as e:
            self._log("error", f"Record processing failed", msg_id=msg_id, error_type=type(e).__name__, error=str(e))
            raise

    def handler(self, event: dict, context: Any) -> dict:
        try:
            asyncio.get_running_loop()
            raise RuntimeError("FastSQS handler called from within event loop. Use async_handler() for testing.")
        except RuntimeError as e:
            if "no running event loop" in str(e):
                return asyncio.run(self._handle_event(event, context))
            else:
                raise
    
    async def async_handler(self, event: dict, context: Any) -> dict:
        return await self._handle_event(event, context)