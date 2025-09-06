from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional, Set, Callable, Union
from .base import Middleware


class IdempotencyStore:
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
    
    async def put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        raise NotImplementedError
    
    async def delete(self, key: str) -> None:
        raise NotImplementedError


class MemoryIdempotencyStore(IdempotencyStore):
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        record = self._store.get(key)
        if record and record.get("expires_at", float("inf")) > time.time():
            return record
        elif record:
            del self._store[key]
        return None
    
    async def put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        if ttl_seconds:
            value["expires_at"] = time.time() + ttl_seconds
        self._store[key] = value
    
    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class DynamoDBIdempotencyStore(IdempotencyStore):
    
    def __init__(self, table_name: str, key_attr: str = "idempotency_key", 
                 ttl_attr: str = "ttl", region_name: Optional[str] = None):
        try:
            import boto3
            self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
            self.table = self.dynamodb.Table(table_name)
            self.key_attr = key_attr
            self.ttl_attr = ttl_attr
        except ImportError:
            raise ImportError("boto3 is required for DynamoDB idempotency store")
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.table.get_item(Key={self.key_attr: key})
            item = response.get("Item")
            if item:
                item.pop(self.key_attr, None)
                item.pop(self.ttl_attr, None)
                return item
        except Exception:
            pass
        return None
    
    async def put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        item = {self.key_attr: key, **value}
        if ttl_seconds:
            item[self.ttl_attr] = int(time.time() + ttl_seconds)
        
        try:
            self.table.put_item(Item=item)
        except Exception:
            pass
    
    async def delete(self, key: str) -> None:
        try:
            self.table.delete_item(Key={self.key_attr: key})
        except Exception:
            pass


class IdempotencyMiddleware(Middleware):
    
    def __init__(
        self,
        store: Optional[IdempotencyStore] = None,
        key_generator: Optional[Callable[[dict, dict], str]] = None,
        ttl_seconds: int = 3600,  # 1 hour default
        skip_on_error: bool = True,
        use_message_deduplication_id: bool = True,
        payload_hash_fields: Optional[list] = None
    ):
        self.store = store or MemoryIdempotencyStore()
        self.key_generator = key_generator or self._default_key_generator
        self.ttl_seconds = ttl_seconds
        self.skip_on_error = skip_on_error
        self.use_message_deduplication_id = use_message_deduplication_id
        self.payload_hash_fields = payload_hash_fields or []
    
    def _default_key_generator(self, payload: dict, record: dict) -> str:
        if self.use_message_deduplication_id:
            attributes = record.get("attributes", {})
            dedup_id = attributes.get("messageDeduplicationId")
            if dedup_id:
                return f"dedup:{dedup_id}"
        
        message_id = record.get("messageId")
        if message_id:
            return f"msg:{message_id}"
        
        return self._hash_payload(payload)
    
    def _hash_payload(self, payload: dict) -> str:
        if self.payload_hash_fields:
            hash_data = {k: payload.get(k) for k in self.payload_hash_fields if k in payload}
        else:
            hash_data = payload
        
        payload_str = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
        return f"hash:{hashlib.sha256(payload_str.encode()).hexdigest()}"
    
    async def before(self, payload: dict, record: dict, context: Any, ctx: dict) -> None:
        try:
            idempotency_key = self.key_generator(payload, record)
            ctx["idempotency_key"] = idempotency_key
            
            existing_record = await self.store.get(idempotency_key)
            if existing_record:
                ctx["idempotency_hit"] = True
                ctx["idempotency_result"] = existing_record.get("result")
                ctx["idempotency_timestamp"] = existing_record.get("timestamp")
                
                raise IdempotencyHit(
                    key=idempotency_key,
                    result=existing_record.get("result"),
                    timestamp=existing_record.get("timestamp")
                )
            else:
                ctx["idempotency_hit"] = False
        
        except IdempotencyHit:
            raise
        except Exception as e:
            if not self.skip_on_error:
                raise
            ctx["idempotency_error"] = str(e)
    
    async def after(self, payload: dict, record: dict, context: Any, ctx: dict, error: Optional[Exception]) -> None:
        if error or ctx.get("idempotency_hit"):
            return
        
        try:
            idempotency_key = ctx.get("idempotency_key")
            if idempotency_key:
                idempotency_record = {
                    "timestamp": time.time(),
                    "message_id": record.get("messageId"),
                    "result": ctx.get("handler_result"),
                    "status": "completed"
                }
                
                await self.store.put(idempotency_key, idempotency_record, self.ttl_seconds)
        
        except Exception as e:
            if not self.skip_on_error:
                raise
            ctx["idempotency_store_error"] = str(e)


class IdempotencyHit(Exception):
    
    def __init__(self, key: str, result: Any = None, timestamp: Optional[float] = None):
        self.key = key
        self.result = result
        self.timestamp = timestamp
        super().__init__(f"Message already processed: {key}")
