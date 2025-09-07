import functools
from typing import Callable

from .concurrency import ThreadPoolManager


def background(func: Callable):
    """
    Decorator to execute the function in the background using the shared thread pool.
    Exceptions inside the function are swallowed by the manager. Returns None immediately.

    Usage:
        @background
        def my_task(...):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ThreadPoolManager().submit(func, *args, **kwargs)
    return wrapper
