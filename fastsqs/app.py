from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from .events import SQSEvent
from .types import QueueType, Handler
from .exceptions import RouteNotFound, InvalidMessage
from .middleware import Middleware, run_middlewares
from .routing import QueueRouter
from .utils import group_records_by_message_group, invoke_handler


class FastSQS:
    """Modern FastAPI-like interface for SQS message processing with FIFO/Standard queue support"""
    
    def __init__(
        self,
        title: str = "FastSQS App",
        description: str = "",
        version: str = "1.0.0",
        debug: bool = False,
        queue_type: QueueType = QueueType.STANDARD,
        message_type_key: str = "type",
        flexible_matching: bool = True
    ):
        self.title = title
        self.description = description
        self.version = version
        self.debug = debug
        self.queue_type = queue_type
        self.message_type_key = message_type_key
        self.flexible_matching = flexible_matching
        
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
        """Route a Pydantic model to a handler function"""
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
                        print(f"Warning: Message type variant '{variant}' conflicts with existing route")
            
            return handler
        
        return decorator

    def default(self) -> Callable[[Handler], Handler]:
        """Set a default handler for unmatched messages"""
        def decorator(handler: Handler) -> Handler:
            self._default_handler = handler
            return handler
        return decorator

    def _find_route(self, message_type: str) -> Optional[tuple[Type[SQSEvent], Handler]]:
        """Find route with flexible matching"""
        if message_type in self._routes:
            return self._routes[message_type]
        
        if self.flexible_matching and message_type in self._route_lookup:
            primary_type = self._route_lookup[message_type]
            return self._routes[primary_type]
        
        return None

    def include_router(self, router: QueueRouter) -> None:
        """Include a QueueRouter for complex nested routing scenarios"""
        self._routers.append(router)

    def add_middleware(self, middleware: Middleware) -> None:
        """Add middleware to the app"""
        self._middlewares.append(middleware)

    def set_queue_type(self, queue_type: QueueType) -> None:
        """Set the queue type (STANDARD or FIFO)"""
        self.queue_type = queue_type
        if self.debug:
            print(f"[FastSQS] Queue type set to: {queue_type.value}")

    def is_fifo_queue(self) -> bool:
        """Check if this is a FIFO queue"""
        return self.queue_type == QueueType.FIFO

    async def _handle_record(self, record: dict, context: Any) -> None:
        """Handle a single record with both new and legacy routing"""
        body_str = record.get("body", "")
        msg_id = record.get("messageId") or record.get("message_id") or "UNKNOWN"

        try:
            payload = json.loads(body_str) if body_str else {}
            if not isinstance(payload, dict):
                raise InvalidMessage("Message body must be a JSON object")
        except json.JSONDecodeError as e:
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

        err: Optional[Exception] = None
        await run_middlewares(self._middlewares, "before", payload, record, context, ctx)
        
        try:
            handled = False
            
            message_type = payload.get(self.message_type_key)
            if message_type:
                route = self._find_route(message_type)
                if route:
                    event_model, handler = route
                    
                    try:
                        event_instance = event_model.model_validate(payload)
                    except ValidationError as e:
                        raise InvalidMessage(f"Validation failed for {message_type}: {e}")

                    ctx["message_type"] = message_type
                    await invoke_handler(handler, msg=event_instance, record=record, context=context, ctx=ctx)
                    handled = True

            if not handled and self._routers:
                for router in self._routers:
                    if await router.dispatch(payload, record, context, ctx, root_payload=payload):
                        handled = True
                        break

            if not handled:
                if self._default_handler:
                    await invoke_handler(self._default_handler, payload=payload, record=record, context=context, ctx=ctx)
                else:
                    available_routes = list(self._routes.keys())
                    available_routers = [r.key for r in self._routers]
                    raise RouteNotFound(
                        f"No handler found for message. "
                        f"Available FastSQS routes: {available_routes}, "
                        f"Available router keys: {available_routers}"
                    )
                    
        except Exception as e:
            err = e
            raise
        finally:
            await run_middlewares(self._middlewares, "after", payload, record, context, ctx, err)

    async def _handle_event(self, event: dict, context: Any) -> dict:
        """Handle the full SQS event"""
        records = event.get("Records", [])
        if not records:
            return {"batchItemFailures": []}
        
        if self.debug:
            queue_info = f"queue_type={self.queue_type.value}, records={len(records)}"
            print(f"[FastSQS] Processing event: {queue_info}")
        
        if self.is_fifo_queue():
            return await self._handle_fifo_event(records, context)
        else:
            return await self._handle_standard_event(records, context)
    
    async def _handle_standard_event(self, records: List[dict], context: Any) -> dict:
        """Handle standard queue events (parallel processing)"""
        failures: List[Dict[str, str]] = []
        
        tasks = [asyncio.create_task(self._handle_record_safe(rec, context)) for rec in records]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                msg_id = records[i].get("messageId", "UNKNOWN")
                if self.debug:
                    print(f"[FastSQS] Record failed: messageId={msg_id}, error={result}")
                failures.append({"itemIdentifier": msg_id})
        
        return {"batchItemFailures": failures}
    
    async def _handle_fifo_event(self, records: List[dict], context: Any) -> dict:
        """Handle FIFO queue events (sequential processing by message group)"""
        failures: List[Dict[str, str]] = []
        
        message_groups = group_records_by_message_group(records)
        
        if self.debug:
            print(f"[FastSQS] FIFO processing: {len(records)} records in {len(message_groups)} groups")
        
        for group_id, group_records in message_groups.items():
            if self.debug:
                print(f"[FastSQS] Processing group '{group_id}' with {len(group_records)} records")
            
            for rec in group_records:
                try:
                    await self._handle_record(rec, context)
                except Exception as e:
                    msg_id = rec.get("messageId", "UNKNOWN")
                    if self.debug:
                        print(f"[FastSQS] FIFO record failed: messageId={msg_id}, group={group_id}, error={e}")
                    failures.append({"itemIdentifier": msg_id})
        
        return {"batchItemFailures": failures}
    
    async def _handle_record_safe(self, record: dict, context: Any) -> None:
        """Safely handle a record (used for async gather)"""
        await self._handle_record(record, context)

    def handler(self, event: dict, context: Any) -> dict:
        """AWS Lambda handler entry point"""
        return asyncio.run(self._handle_event(event, context))