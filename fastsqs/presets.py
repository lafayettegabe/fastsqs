from __future__ import annotations

from typing import Optional, Dict, Any
from .middleware import (
    IdempotencyMiddleware, DynamoDBIdempotencyStore, MemoryIdempotencyStore,
    ErrorHandlingMiddleware, RetryConfig, CircuitBreaker,
    VisibilityTimeoutMonitor, ParallelizationMiddleware, ParallelizationConfig,
    LoggingMiddleware, TimingMsMiddleware
)


class MiddlewarePreset:
    @staticmethod
    def production(
        dynamodb_table: Optional[str] = None,
        region_name: Optional[str] = None,
        max_concurrent: int = 10,
        retry_attempts: int = 3,
        visibility_timeout: float = 30.0,
        circuit_breaker_threshold: int = 5
    ) -> list:
        middlewares = []
        
        middlewares.append(LoggingMiddleware())
        middlewares.append(TimingMsMiddleware())
        
        if dynamodb_table:
            store = DynamoDBIdempotencyStore(
                table_name=dynamodb_table,
                region_name=region_name
            )
        else:
            store = MemoryIdempotencyStore()
        
        middlewares.append(IdempotencyMiddleware(
            store=store,
            ttl_seconds=3600
        ))
        
        retry_config = RetryConfig(
            max_retries=retry_attempts,
            base_delay=1.0,
            max_delay=60.0,
            exponential_backoff=True
        )
        circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=60.0
        )
        middlewares.append(ErrorHandlingMiddleware(
            retry_config=retry_config,
            circuit_breaker=circuit_breaker
        ))
        
        middlewares.append(VisibilityTimeoutMonitor(
            default_visibility_timeout=visibility_timeout,
            warning_threshold=0.8
        ))
        
        parallel_config = ParallelizationConfig(
            max_concurrent_messages=max_concurrent,
            use_thread_pool=True,
            thread_pool_size=min(32, max_concurrent)
        )
        middlewares.append(ParallelizationMiddleware(config=parallel_config))
        
        return middlewares
    
    @staticmethod
    def development(max_concurrent: int = 5) -> list:
        middlewares = []
        
        middlewares.append(LoggingMiddleware())
        middlewares.append(TimingMsMiddleware())
        
        store = MemoryIdempotencyStore()
        middlewares.append(IdempotencyMiddleware(
            store=store,
            ttl_seconds=300
        ))
        
        retry_config = RetryConfig(max_retries=2, base_delay=0.5)
        middlewares.append(ErrorHandlingMiddleware(retry_config=retry_config))
        
        middlewares.append(VisibilityTimeoutMonitor(
            default_visibility_timeout=30.0,
            warning_threshold=0.9
        ))
        
        parallel_config = ParallelizationConfig(
            max_concurrent_messages=max_concurrent,
            use_thread_pool=False
        )
        middlewares.append(ParallelizationMiddleware(config=parallel_config))
        
        return middlewares
    
    @staticmethod
    def minimal() -> list:
        return [
            LoggingMiddleware(),
            TimingMsMiddleware(),
            IdempotencyMiddleware(ttl_seconds=3600)
        ]
