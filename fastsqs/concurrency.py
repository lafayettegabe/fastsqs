"""Background task execution utilities."""

import functools
import asyncio
from typing import Any, Callable


def background(func: Callable) -> Callable:
    """Decorator for background task execution.
    
    Args:
        func: Function to execute in background
        
    Returns:
        Wrapped function that executes in background
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return sync_wrapper
