from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Callable, Union
from concurrent.futures import ThreadPoolExecutor
from .base import Middleware


class ConcurrencyLimiter:
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.waiting_count = 0
    
    async def acquire(self) -> None:
        self.waiting_count += 1
        try:
            await self.semaphore.acquire()
            self.active_count += 1
        finally:
            self.waiting_count -= 1
    
    def release(self) -> None:
        self.active_count = max(0, self.active_count - 1)
        self.semaphore.release()
    
    @property
    def stats(self) -> Dict[str, int]:
        return {
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "waiting_count": self.waiting_count,
            "available_slots": self.max_concurrent - self.active_count
        }


class ResourcePool:
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks = 0
    
    async def run_in_executor(self, func: Callable, *args) -> Any:
        self.active_tasks += 1
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.executor, func, *args)
        finally:
            self.active_tasks = max(0, self.active_tasks - 1)
    
    def shutdown(self, wait: bool = True) -> None:
        self.executor.shutdown(wait=wait)
    
    @property
    def stats(self) -> Dict[str, int]:
        return {
            "max_workers": self.max_workers,
            "active_tasks": self.active_tasks
        }


class ParallelizationConfig:
    
    def __init__(
        self,
        max_concurrent_messages: int = 10,
        max_concurrent_per_group: int = 1,  # For FIFO queues
        use_thread_pool: bool = False,
        thread_pool_size: Optional[int] = None,
        batch_processing: bool = False,
        batch_size: int = 5,
        batch_timeout: float = 1.0
    ):
        self.max_concurrent_messages = max_concurrent_messages
        self.max_concurrent_per_group = max_concurrent_per_group
        self.use_thread_pool = use_thread_pool
        self.thread_pool_size = thread_pool_size or min(32, 5)
        self.batch_processing = batch_processing
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout


class ParallelizationMiddleware(Middleware):
    
    def __init__(
        self,
        config: Optional[ParallelizationConfig] = None,
        resource_pools: Optional[Dict[str, ResourcePool]] = None,
        concurrency_limiter: Optional[ConcurrencyLimiter] = None
    ):
        self.config = config or ParallelizationConfig()
        self.resource_pools = resource_pools or {}
        self.concurrency_limiter = concurrency_limiter or ConcurrencyLimiter(
            self.config.max_concurrent_messages
        )
        
        self.thread_pool: Optional[ThreadPoolExecutor] = None
        if self.config.use_thread_pool:
            self.thread_pool = ThreadPoolExecutor(
                max_workers=self.config.thread_pool_size,
                thread_name_prefix="fastsqs-worker"
            )
        
        self.pending_batches: Dict[str, List[Dict]] = {}
        self.batch_timers: Dict[str, asyncio.Task] = {}
    
    async def before(self, payload: dict, record: dict, context: Any, ctx: dict) -> None:
        start_time = time.time()
        await self.concurrency_limiter.acquire()
        wait_time = time.time() - start_time
        
        ctx["concurrency_wait_time"] = wait_time
        ctx["concurrency_stats"] = self.concurrency_limiter.stats
        ctx["acquired_resources"] = {}
        
        ctx["_parallelization_middleware"] = self
    
    async def after(self, payload: dict, record: dict, context: Any, ctx: dict, error: Optional[Exception]) -> None:
        acquired_resources = ctx.get("acquired_resources", {})
        for resource_name, resource in acquired_resources.items():
            if resource_name in self.resource_pools:
                await self.resource_pools[resource_name].release(resource)
        
        self.concurrency_limiter.release()
    
    async def acquire_resource(self, resource_name: str, ctx: dict) -> Any:
        if resource_name not in self.resource_pools:
            raise ValueError(f"Resource pool '{resource_name}' not found")
        
        resource = await self.resource_pools[resource_name].acquire()
        ctx["acquired_resources"][resource_name] = resource
        return resource
    
    async def run_in_thread_pool(self, func: Callable, *args, **kwargs) -> Any:
        if not self.thread_pool:
            raise RuntimeError("Thread pool not enabled")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)
    
    async def process_batch(self, batch_key: str, items: List[Dict], 
                          handler: Callable[[List[Dict]], Any]) -> Any:
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(items)
            else:
                return handler(items)
        except Exception as e:
            raise BatchProcessingError(f"Batch processing failed for key '{batch_key}': {e}")
    
    async def add_to_batch(self, batch_key: str, item: Dict, 
                          batch_handler: Callable[[List[Dict]], Any]) -> None:
        if batch_key not in self.pending_batches:
            self.pending_batches[batch_key] = []
        
        self.pending_batches[batch_key].append(item)
        
        if len(self.pending_batches[batch_key]) >= self.config.batch_size:
            await self._process_ready_batch(batch_key, batch_handler)
        elif batch_key not in self.batch_timers:
            self.batch_timers[batch_key] = asyncio.create_task(
                self._batch_timeout_handler(batch_key, batch_handler)
            )
    
    async def _process_ready_batch(self, batch_key: str, handler: Callable[[List[Dict]], Any]) -> None:
        if batch_key in self.pending_batches and self.pending_batches[batch_key]:
            items = self.pending_batches[batch_key]
            del self.pending_batches[batch_key]
            
            if batch_key in self.batch_timers:
                self.batch_timers[batch_key].cancel()
                del self.batch_timers[batch_key]
            
            await self.process_batch(batch_key, items, handler)
    
    async def _batch_timeout_handler(self, batch_key: str, handler: Callable[[List[Dict]], Any]) -> None:
        try:
            await asyncio.sleep(self.config.batch_timeout)
            await self._process_ready_batch(batch_key, handler)
        except asyncio.CancelledError:
            pass
    
    async def cleanup(self) -> None:
        for pool in self.resource_pools.values():
            await pool.cleanup()
        
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        for timer in self.batch_timers.values():
            timer.cancel()
        
        self.batch_timers.clear()
        self.pending_batches.clear()


class LoadBalancingMiddleware(Middleware):
    
    def __init__(
        self,
        strategy: str = "round_robin",
        health_check_interval: float = 30.0,
        weights: Optional[Dict[str, float]] = None
    ):
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self.weights = weights or {}
        
        self.handler_stats: Dict[str, Dict] = {}
        self.current_index = 0
        self.last_health_check = 0.0
    
    def register_handler(self, handler_id: str, handler: Callable, weight: float = 1.0) -> None:
        self.handler_stats[handler_id] = {
            "handler": handler,
            "weight": weight,
            "active_requests": 0,
            "total_requests": 0,
            "total_errors": 0,
            "avg_response_time": 0.0,
            "healthy": True,
            "last_request_time": 0.0
        }
    
    def select_handler(self) -> Optional[tuple[str, Callable]]:
        healthy_handlers = [
            (handler_id, stats) for handler_id, stats in self.handler_stats.items()
            if stats["healthy"]
        ]
        
        if not healthy_handlers:
            return None
        
        if self.strategy == "round_robin":
            self.current_index = (self.current_index + 1) % len(healthy_handlers)
            handler_id, stats = healthy_handlers[self.current_index]
            return handler_id, stats["handler"]
        
        elif self.strategy == "least_busy":
            handler_id, stats = min(healthy_handlers, key=lambda x: x[1]["active_requests"])
            return handler_id, stats["handler"]
        
        elif self.strategy == "weighted":
            import random
            total_weight = sum(stats["weight"] for _, stats in healthy_handlers)
            if total_weight == 0:
                return None
            
            rand_val = random.uniform(0, total_weight)
            current_weight = 0
            
            for handler_id, stats in healthy_handlers:
                current_weight += stats["weight"]
                if rand_val <= current_weight:
                    return handler_id, stats["handler"]
        
        return None
    
    async def before(self, payload: dict, record: dict, context: Any, ctx: dict) -> None:
        selected = self.select_handler()
        if selected:
            handler_id, handler = selected
            ctx["selected_handler_id"] = handler_id
            ctx["selected_handler"] = handler
            ctx["handler_start_time"] = time.time()
            
            self.handler_stats[handler_id]["active_requests"] += 1
            self.handler_stats[handler_id]["total_requests"] += 1
            self.handler_stats[handler_id]["last_request_time"] = time.time()
    
    async def after(self, payload: dict, record: dict, context: Any, ctx: dict, error: Optional[Exception]) -> None:
        handler_id = ctx.get("selected_handler_id")
        if handler_id and handler_id in self.handler_stats:
            start_time = ctx.get("handler_start_time", time.time())
            response_time = time.time() - start_time
            
            stats = self.handler_stats[handler_id]
            stats["active_requests"] = max(0, stats["active_requests"] - 1)
            
            prev_avg = stats["avg_response_time"]
            total_requests = stats["total_requests"]
            stats["avg_response_time"] = ((prev_avg * (total_requests - 1)) + response_time) / total_requests
            
            if error:
                stats["total_errors"] += 1
                
                error_rate = stats["total_errors"] / stats["total_requests"]
                if error_rate > 0.5 and stats["total_requests"] > 10:
                    stats["healthy"] = False


class ResourcePoolExhaustedError(Exception):
    pass


class ResourceCreationError(Exception):
    pass


class BatchProcessingError(Exception):
    pass
