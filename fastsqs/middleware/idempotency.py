from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Set, Callable, Union
from .base import Middleware

logger = logging.getLogger(__name__)


class IdempotencyStore:
    
    async def get(self, key: str, consistent_read: bool = False) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
    
    async def put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        raise NotImplementedError
    
    async def conditional_put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        raise NotImplementedError
    
    async def update(self, key: str, updates: Dict[str, Any]) -> bool:
        raise NotImplementedError
    
    async def delete(self, key: str) -> None:
        raise NotImplementedError
    
    async def conditional_delete(self, key: str, condition_attr: str, condition_value: Any) -> bool:
        raise NotImplementedError


class MemoryIdempotencyStore(IdempotencyStore):
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
    
    async def get(self, key: str, consistent_read: bool = False) -> Optional[Dict[str, Any]]:
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
    
    async def conditional_put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        if key in self._store:
            record = self._store[key]
            if record.get("expires_at", float("inf")) > time.time():
                return False
            else:
                del self._store[key]
        
        await self.put(key, value, ttl_seconds)
        return True
    
    async def update(self, key: str, updates: Dict[str, Any]) -> bool:
        if key not in self._store:
            return False
        
        record = self._store[key]
        if record.get("expires_at", float("inf")) <= time.time():
            del self._store[key]
            return False
        
        record.update(updates)
        return True
    
    async def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]
    
    async def conditional_delete(self, key: str, condition_attr: str, condition_value: Any) -> bool:
        if key in self._store and self._store[key].get(condition_attr) == condition_value:
            del self._store[key]
            return True
        return False


class DynamoDBIdempotencyStore(IdempotencyStore):
    
    def __init__(self, table_name: str, key_attr: str = "idempotency_key", 
                 ttl_attr: str = "ttl", region_name: Optional[str] = None,
                 create_table: bool = True, read_capacity_units: int = 5, 
                 write_capacity_units: int = 5):
        try:
            import aioboto3
            from botocore.exceptions import ClientError
            from boto3.dynamodb.conditions import Attr
            self.ClientError = ClientError
            self.Attr = Attr
            self.session = aioboto3.Session()
            self.table_name = table_name
            self.region_name = region_name
            self.key_attr = key_attr
            self.ttl_attr = ttl_attr
            self.create_table = create_table
            self.read_capacity_units = read_capacity_units
            self.write_capacity_units = write_capacity_units
            self._table = None
            self._table_exists_checked = False
        except ImportError:
            raise ImportError("aioboto3 is required for DynamoDB idempotency store")
    
    async def _ensure_table_exists(self):
        if not self.create_table or self._table_exists_checked:
            return
        
        try:
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                try:
                    table = await dynamodb.Table(self.table_name)
                    await table.load()
                    logger.info(f"DynamoDB table {self.table_name} already exists")
                    
                    await self._ensure_ttl_enabled(table)
                    
                except self.ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        await self._create_table(dynamodb)
                    else:
                        raise
                
                self._table_exists_checked = True
                
        except Exception as e:
            logger.error(f"Failed to ensure table exists: {str(e)}")
            raise
    
    async def _create_table(self, dynamodb):
        try:
            logger.info(f"Creating DynamoDB table {self.table_name}")
            
            table = await dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        'AttributeName': self.key_attr,
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': self.key_attr,
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={
                    'ReadCapacityUnits': self.read_capacity_units,
                    'WriteCapacityUnits': self.write_capacity_units
                }
            )
            
            await table.wait_until_exists()
            logger.info(f"DynamoDB table {self.table_name} created successfully")
            
            await self._ensure_ttl_enabled(table)
            
        except self.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info(f"Table {self.table_name} already exists")
            else:
                logger.error(f"Failed to create table {self.table_name}: {str(e)}")
                raise
    
    async def _ensure_ttl_enabled(self, table):
        try:
            async with self.session.client("dynamodb", region_name=self.region_name) as client:
                try:
                    response = await client.describe_time_to_live(TableName=self.table_name)
                    ttl_status = response.get('TimeToLiveDescription', {}).get('TimeToLiveStatus')
                    
                    if ttl_status != 'ENABLED':
                        logger.info(f"Enabling TTL on table {self.table_name}")
                        await client.update_time_to_live(
                            TableName=self.table_name,
                            TimeToLiveSpecification={
                                'AttributeName': self.ttl_attr,
                                'Enabled': True
                            }
                        )
                        logger.info(f"TTL enabled on table {self.table_name}")
                    else:
                        logger.debug(f"TTL already enabled on table {self.table_name}")
                        
                except self.ClientError as e:
                    if e.response['Error']['Code'] != 'ValidationException':
                        logger.warning(f"Failed to enable TTL on table {self.table_name}: {str(e)}")
                        
        except Exception as e:
            logger.warning(f"Failed to configure TTL on table {self.table_name}: {str(e)}")
    
    async def _get_table(self):
        if self._table is None:
            await self._ensure_table_exists()
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                self._table = await dynamodb.Table(self.table_name)
        return self._table
    
    async def get(self, key: str, consistent_read: bool = False) -> Optional[Dict[str, Any]]:
        try:
            await self._ensure_table_exists()
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                table = await dynamodb.Table(self.table_name)
                response = await table.get_item(
                    Key={self.key_attr: key},
                    ConsistentRead=consistent_read
                )
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
            await self._ensure_table_exists()
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                table = await dynamodb.Table(self.table_name)
                await table.put_item(Item=item)
        except Exception:
            pass
    
    async def conditional_put(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        item = {self.key_attr: key, **value}
        if ttl_seconds:
            item[self.ttl_attr] = int(time.time() + ttl_seconds)
        
        try:
            current_time = int(time.time())
            await self._ensure_table_exists()
            
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                table = await dynamodb.Table(self.table_name)
                await table.put_item(
                    Item=item,
                    ConditionExpression=f"attribute_not_exists(#{self.key_attr}) OR #{self.ttl_attr} <= :now",
                    ExpressionAttributeNames={
                        f"#{self.key_attr}": self.key_attr,
                        f"#{self.ttl_attr}": self.ttl_attr
                    },
                    ExpressionAttributeValues={
                        ":now": current_time
                    }
                )
            return True
        except self.ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            raise
    
    async def update(self, key: str, updates: Dict[str, Any]) -> bool:
        try:
            update_expression_parts = []
            expression_attribute_values = {}
            
            for k, v in updates.items():
                update_expression_parts.append(f"#{k} = :{k}")
                expression_attribute_values[f":{k}"] = v
            
            expression_attribute_names = {f"#{k}": k for k in updates.keys()}
            
            await self._ensure_table_exists()
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                table = await dynamodb.Table(self.table_name)
                await table.update_item(
                    Key={self.key_attr: key},
                    UpdateExpression="SET " + ", ".join(update_expression_parts),
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values,
                    ConditionExpression=f"attribute_exists(#{self.key_attr})"
                )
            return True
        except self.ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            raise
        except Exception:
            return False
    
    async def delete(self, key: str) -> None:
        try:
            await self._ensure_table_exists()
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                table = await dynamodb.Table(self.table_name)
                await table.delete_item(Key={self.key_attr: key})
        except Exception:
            pass
    
    async def conditional_delete(self, key: str, condition_attr: str, condition_value: Any) -> bool:
        try:
            await self._ensure_table_exists()
            async with self.session.resource("dynamodb", region_name=self.region_name) as dynamodb:
                table = await dynamodb.Table(self.table_name)
                await table.delete_item(
                    Key={self.key_attr: key},
                    ConditionExpression=self.Attr(condition_attr).eq(condition_value)
                )
            return True
        except self.ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            logger.warning(f"Error in conditional delete for {key}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error in conditional delete for {key}: {e}")
            return False


class IdempotencyMiddleware(Middleware):
    
    def __init__(
        self,
        store: Optional[IdempotencyStore] = None,
        key_generator: Optional[Callable[[dict, dict], str]] = None,
        ttl_seconds: int = 3600,
        skip_on_error: bool = False,
        use_message_deduplication_id: bool = False,
        payload_hash_fields: Optional[list] = None,
        use_strong_consistency: bool = True,
        per_entity_sequencing: bool = False,
        entity_key_extractor: Optional[Callable[[dict], str]] = None,
        fail_on_store_errors: bool = True,
        entity_lock_ttl_seconds: Optional[int] = None,
        sqs_visibility_timeout_seconds: int = 30
    ):
        self.store = store or MemoryIdempotencyStore()
        self.key_generator = key_generator or self._default_key_generator
        self.ttl_seconds = ttl_seconds
        self.skip_on_error = skip_on_error
        self.use_message_deduplication_id = use_message_deduplication_id
        self.payload_hash_fields = payload_hash_fields or []
        self.use_strong_consistency = use_strong_consistency
        self.per_entity_sequencing = per_entity_sequencing
        self.entity_key_extractor = entity_key_extractor
        self.fail_on_store_errors = fail_on_store_errors
        
        self.entity_lock_ttl_seconds = entity_lock_ttl_seconds or (sqs_visibility_timeout_seconds + 60)
        self.sqs_visibility_timeout_seconds = sqs_visibility_timeout_seconds
    
    def _default_key_generator(self, payload: dict, record: dict) -> str:
        if self.use_message_deduplication_id:
            attributes = record.get("attributes", {})
            dedup_id = attributes.get("messageDeduplicationId")
            if dedup_id:
                return f"dedup:{dedup_id}"
        
        return self._hash_payload(payload)
    
    def _hash_payload(self, payload: dict) -> str:
        if self.payload_hash_fields:
            hash_data = {k: payload.get(k) for k in self.payload_hash_fields if k in payload}
        else:
            hash_data = payload
        
        payload_str = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
        return f"hash:{hashlib.sha256(payload_str.encode()).hexdigest()}"
    
    def _get_entity_key(self, payload: dict) -> Optional[str]:
        if not self.per_entity_sequencing or not self.entity_key_extractor:
            return None
        return self.entity_key_extractor(payload)
    
    async def _acquire_entity_lock(self, entity_key: str, idempotency_key: str) -> bool:
        lock_key = f"lock:{entity_key}"
        lock_record = {
            "status": "LOCKED",
            "locked_by": idempotency_key,
            "created_at": time.time()
        }
        
        try:
            return await self.store.conditional_put(lock_key, lock_record, self.entity_lock_ttl_seconds)
        except Exception as e:
            if self.fail_on_store_errors:
                raise IdempotencyStoreError(f"Failed to acquire entity lock: {str(e)}")
            return False
    
    async def _release_entity_lock(self, entity_key: str, idempotency_key: str) -> None:
        lock_key = f"lock:{entity_key}"
        try:
            if hasattr(self.store, 'conditional_delete'):
                success = await self.store.conditional_delete(lock_key, "locked_by", idempotency_key)
                if not success:
                    logger.warning(f"Failed to release lock {lock_key}: not owned by {idempotency_key}")
            else:
                await self.store.delete(lock_key)
        except Exception as e:
            if self.fail_on_store_errors:
                raise IdempotencyStoreError(f"Failed to release entity lock: {str(e)}")
    
    async def before(self, payload: dict, record: dict, context: Any, ctx: dict) -> None:
        try:
            idempotency_key = self.key_generator(payload, record)
            ctx["idempotency_key"] = idempotency_key
            
            entity_key = self._get_entity_key(payload) if self.per_entity_sequencing else None
            if entity_key:
                ctx["entity_key"] = entity_key
            
            if self.use_strong_consistency:
                reservation_record = {
                    "status": "IN_PROGRESS",
                    "created_at": time.time(),
                    "message_id": record.get("messageId"),
                    "entity_key": entity_key
                }
                
                success = await self.store.conditional_put(
                    idempotency_key, 
                    reservation_record, 
                    self.ttl_seconds
                )
                
                if not success:
                    existing_record = await self.store.get(idempotency_key, consistent_read=True)
                    if existing_record:
                        status = existing_record.get("status")
                        if status == "IN_PROGRESS":
                            raise IdempotencyInProgress(
                                key=idempotency_key,
                                created_at=existing_record.get("created_at")
                            )
                        elif status == "COMPLETED":
                            ctx["idempotency_hit"] = True
                            ctx["idempotency_result"] = existing_record.get("result")
                            ctx["idempotency_timestamp"] = existing_record.get("finished_at")
                            
                            raise IdempotencyHit(
                                key=idempotency_key,
                                result=existing_record.get("result"),
                                timestamp=existing_record.get("finished_at")
                            )
                        elif status == "FAILED":
                            raise IdempotencyFailedPreviously(
                                key=idempotency_key,
                                error=existing_record.get("error"),
                                timestamp=existing_record.get("finished_at")
                            )
                
                if entity_key:
                    if not await self._acquire_entity_lock(entity_key, idempotency_key):
                        try:
                            await self.store.delete(idempotency_key)
                        except Exception:
                            pass
                        
                        raise EntityLockAcquisitionFailed(
                            entity_key=entity_key,
                            idempotency_key=idempotency_key
                        )
                    ctx["entity_locked"] = True
                
                ctx["idempotency_hit"] = False
                ctx["reservation_created"] = True
            else:
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
        
        except (IdempotencyHit, IdempotencyInProgress, IdempotencyFailedPreviously, EntityLockAcquisitionFailed):
            raise
        except Exception as e:
            if self.fail_on_store_errors or not self.skip_on_error:
                raise IdempotencyStoreError(f"Idempotency check failed: {str(e)}")
            ctx["idempotency_error"] = str(e)
    
    async def after(self, payload: dict, record: dict, context: Any, ctx: dict, error: Optional[Exception]) -> None:
        entity_key = ctx.get("entity_key")
        idempotency_key = ctx.get("idempotency_key")
        
        try:
            if ctx.get("idempotency_hit") or not ctx.get("reservation_created"):
                return
            
            if self.use_strong_consistency and idempotency_key:
                if error:
                    failure_record = {
                        "status": "FAILED",
                        "finished_at": time.time(),
                        "error": str(error),
                        "error_type": type(error).__name__
                    }
                    await self.store.update(idempotency_key, failure_record)
                else:
                    completion_record = {
                        "status": "COMPLETED",
                        "finished_at": time.time(),
                        "result": ctx.get("handler_result")
                    }
                    await self.store.update(idempotency_key, completion_record)
            elif not error and idempotency_key:
                idempotency_record = {
                    "timestamp": time.time(),
                    "message_id": record.get("messageId"),
                    "result": ctx.get("handler_result"),
                    "status": "completed"
                }
                
                await self.store.put(idempotency_key, idempotency_record, self.ttl_seconds)
            
            if ctx.get("entity_locked") and entity_key and idempotency_key:
                await self._release_entity_lock(entity_key, idempotency_key)
        
        except Exception as e:
            if ctx.get("entity_locked") and entity_key and idempotency_key:
                try:
                    await self._release_entity_lock(entity_key, idempotency_key)
                except Exception:
                    pass
            
            if self.fail_on_store_errors or not self.skip_on_error:
                raise IdempotencyStoreError(f"Failed to update idempotency record: {str(e)}")
            ctx["idempotency_store_error"] = str(e)


class IdempotencyHit(Exception):
    
    def __init__(self, key: str, result: Any = None, timestamp: Optional[float] = None):
        self.key = key
        self.result = result
        self.timestamp = timestamp
        super().__init__(f"Message already processed: {key}")


class IdempotencyInProgress(Exception):
    
    def __init__(self, key: str, created_at: Optional[float] = None):
        self.key = key
        self.created_at = created_at
        super().__init__(f"Message currently in progress: {key}")


class IdempotencyFailedPreviously(Exception):
    
    def __init__(self, key: str, error: Any = None, timestamp: Optional[float] = None):
        self.key = key
        self.error = error
        self.timestamp = timestamp
        super().__init__(f"Message failed previously: {key}, error: {error}")


class EntityLockAcquisitionFailed(Exception):
    
    def __init__(self, entity_key: str, idempotency_key: str):
        self.entity_key = entity_key
        self.idempotency_key = idempotency_key
        super().__init__(f"Failed to acquire lock for entity: {entity_key}")


class IdempotencyStoreError(Exception):
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
