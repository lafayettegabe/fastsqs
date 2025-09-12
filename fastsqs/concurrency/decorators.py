"""Decorators for background task execution."""

import functools
import contextvars
from typing import Callable

from .concurrency import ThreadPoolManager


def background(func: Callable):
    """Decorator to execute function in background using shared thread pool.

    Exceptions inside the function are swallowed by the manager.
    Returns None immediately without waiting for completion.
    ContextVar state is copied to the background thread.

    Args:
        func: Function to execute in background

    Returns:
        Wrapper function that submits to thread pool

    Usage:
        @background
        def my_task(...):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ctx = contextvars.copy_context()
        ThreadPoolManager().submit(lambda: ctx.run(func, *args, **kwargs))
    return wrapper
