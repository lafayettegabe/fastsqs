"""FastSQS - A FastAPI-style AWS SQS message handling framework.

This package provides a modern, FastAPI-inspired interface for handling
AWS SQS messages with support for routing, middleware, validation, and more.
"""

from .types import QueueType, Handler, RouteValue
from .exceptions import RouteNotFound, InvalidMessage
from .app import FastSQS
from .routing import SQSRouter, RouteEntry
from .middleware import (
    Middleware,
    TimingMsMiddleware,
    LoggingMiddleware,
    IdempotencyMiddleware,
    IdempotencyStore,
    MemoryIdempotencyStore,
    DynamoDBIdempotencyStore,
    ErrorHandlingMiddleware,
    RetryConfig,
    CircuitBreaker,
    DeadLetterQueueMiddleware,
    VisibilityTimeoutMonitor,
    ProcessingTimeMiddleware,
    QueueMetricsMiddleware,
    ParallelizationMiddleware,
    ConcurrencyLimiter,
    ResourcePool,
    ParallelizationConfig,
    LoadBalancingMiddleware,
)
from .events import SQSEvent
from .presets import MiddlewarePreset
from .logger import Logger

__all__ = [
    "QueueType",
    "Handler",
    "RouteValue",
    "RouteNotFound",
    "InvalidMessage",
    "FastSQS",
    "SQSRouter",
    "RouteEntry",
    "Middleware",
    "TimingMsMiddleware",
    "LoggingMiddleware",
    "SQSEvent",
    "IdempotencyMiddleware",
    "IdempotencyStore",
    "MemoryIdempotencyStore",
    "DynamoDBIdempotencyStore",
    "ErrorHandlingMiddleware",
    "RetryConfig",
    "CircuitBreaker",
    "DeadLetterQueueMiddleware",
    "VisibilityTimeoutMonitor",
    "ProcessingTimeMiddleware",
    "QueueMetricsMiddleware",
    "ParallelizationMiddleware",
    "ConcurrencyLimiter",
    "ResourcePool",
    "ParallelizationConfig",
    "LoadBalancingMiddleware",
    "MiddlewarePreset",
    "Logger",
]
