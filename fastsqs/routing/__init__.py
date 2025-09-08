"""Routing components for FastSQS."""

from .entry import RouteEntry
from .router import SQSRouter

__all__ = [
    "RouteEntry",
    "SQSRouter",
]
