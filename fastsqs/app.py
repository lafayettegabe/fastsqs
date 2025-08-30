from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .types import QueueType, Handler
from .exceptions import RouteNotFound, InvalidMessage
from .middleware import Middleware, run_middlewares
from .routing import QueueRouter
from .utils import group_records_by_message_group, invoke_handler


class QueueApp:
    def __init__(
        self,
        title: str = "",
        description: str = "",
        version: str = "",
        debug: bool = False,
        strict: bool = True,
        on_decode_error: str = "fail",
        on_validation_error: str = "fail",
        default_handler: Optional[Handler] = None,
        queue_type: QueueType = QueueType.STANDARD,
    ):
        self.title = title
        self.description = description
        self.version = version
        self.debug = debug
        self.strict = strict
        self.on_decode_error = on_decode_error
        self.on_validation_error = on_validation_error
        self.default_handler = default_handler
        self.queue_type = queue_type
        self._routers: List[QueueRouter] = []
        self._middlewares: List[Middleware] = []

    def include_router(self, router: QueueRouter) -> None:
        self._routers.append(router)

    def add_middleware(self, mw: Middleware) -> None:
        self._middlewares.append(mw)
    
    def is_fifo_queue(self, record: dict) -> bool:
        return self.queue_type == QueueType.FIFO
    
    def get_fifo_info(self, record: dict) -> Dict[str, Any]:
        if not self.is_fifo_queue(record):
            return {}
        
        attributes = record.get("attributes", {})
        return {
            "messageGroupId": attributes.get("messageGroupId"),
            "messageDeduplicationId": attributes.get("messageDeduplicationId"),
            "queueType": "fifo"
        }
    
    def set_queue_type(self, queue_type: QueueType) -> None:
        self.queue_type = queue_type
        if self.debug:
            print(f"[QueueApp] Queue type changed to: {queue_type.value}")

    async def _handle_record(self, record: dict, context: Any) -> None:
        body_str = record.get("body", "")
        msg_id = record.get("messageId") or record.get("message_id") or "UNKNOWN"

        try:
            payload = json.loads(body_str) if body_str else {}
            if not isinstance(payload, dict):
                raise InvalidMessage("Body must be a JSON object")
        except Exception as e:
            if self.debug:
                print(f"[QueueApp] JSON decode error: {e}")
            if self.on_decode_error == "skip":
                return
            raise

        fifo_info = {}
        if self.queue_type == QueueType.FIFO:
            attributes = record.get("attributes", {})
            fifo_info = {
                "messageGroupId": attributes.get("messageGroupId"),
                "messageDeduplicationId": attributes.get("messageDeduplicationId"),
                "queueType": "fifo"
            }
        else:
            fifo_info = {"queueType": "standard"}

        ctx: Dict[str, Any] = {
            "messageId": msg_id, 
            "route_path": [],
            "queueType": self.queue_type.value,
            "fifoInfo": fifo_info
        }

        err: Optional[Exception] = None
        await run_middlewares(self._middlewares, "before", payload, record, context, ctx)
        
        try:
            handled = False
            for router in self._routers:
                try:
                    if await router.dispatch(payload, record, context, ctx, root_payload=payload):
                        handled = True
                        break
                except ValidationError as ve:
                    if self.debug:
                        print(f"[QueueApp] validation error: {ve}")
                    if self.on_validation_error == "skip":
                        handled = True
                        break
                    else:
                        raise

            if not handled:
                if self.default_handler:
                    await invoke_handler(
                        self.default_handler, 
                        payload=payload, 
                        record=record, 
                        context=context, 
                        ctx=ctx
                    )
                elif self.strict:
                    raise RouteNotFound(
                        f"No route matched for keys {[r.key for r in self._routers]}"
                    )
                    
        except Exception as e:
            err = e
            raise
        finally:
            await run_middlewares(self._middlewares, "after", payload, record, context, ctx, err)

    async def _handle_event(self, event: dict, context: Any) -> dict:
        records = event.get("Records", [])
        if not records:
            return {"batchItemFailures": []}
        
        if self.debug:
            print(f"[QueueApp] Using configured queue type: {self.queue_type.value}")
        
        if self.queue_type == QueueType.FIFO:
            return await self._handle_fifo_event(records, context)
        else:
            return await self._handle_standard_event(records, context)
    
    async def _handle_standard_event(self, records: List[dict], context: Any) -> dict:
        failures: List[Dict[str, str]] = []
        
        tasks = []
        for rec in records:
            task = asyncio.create_task(self._handle_record_safe(rec, context))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                msg_id = (records[i].get("messageId") or 
                         records[i].get("message_id") or "UNKNOWN")
                if self.debug:
                    print(f"[QueueApp] record failed: messageId={msg_id} error={result}")
                failures.append({"itemIdentifier": msg_id})
        
        return {"batchItemFailures": failures}
    
    async def _handle_fifo_event(self, records: List[dict], context: Any) -> dict:
        failures: List[Dict[str, str]] = []
        
        message_groups = group_records_by_message_group(records)
        
        if self.debug:
            print(f"[QueueApp] Processing {len(records)} records in "
                  f"{len(message_groups)} message groups")
        
        for group_id, group_records in message_groups.items():
            if self.debug:
                print(f"[QueueApp] Processing message group: {group_id} "
                      f"with {len(group_records)} records")
            
            for rec in group_records:
                try:
                    await self._handle_record(rec, context)
                except Exception as e:
                    msg_id = rec.get("messageId") or rec.get("message_id") or "UNKNOWN"
                    if self.debug:
                        print(f"[QueueApp] FIFO record failed: messageId={msg_id} "
                              f"group={group_id} error={e}")
                    failures.append({"itemIdentifier": msg_id})
        
        return {"batchItemFailures": failures}
    
    async def _handle_record_safe(self, record: dict, context: Any) -> None:
        await self._handle_record(record, context)

    def handler(self, event: dict, context: Any) -> dict:
        return asyncio.run(self._handle_event(event, context))