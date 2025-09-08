"""Thread pool management for background task execution."""

from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class ThreadPoolManager:
    """Singleton manager for a shared ThreadPoolExecutor.
    
    Provides a shared thread pool with AWS Lambda safety limits
    and fire-and-forget task submission with exception handling.
    """

    MAX_WORKERS: int = 1024
    THREAD_NAME_PREFIX: str = "thread-pool-manager"
    _instance = None

    def __new__(cls):
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configure_executor()
        return cls._instance

    def _configure_executor(self) -> None:
        """Configure the thread pool executor."""
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix=self.THREAD_NAME_PREFIX,
        )

    @staticmethod
    def _swallow(call: Callable[[], None]) -> None:
        """Execute a callable and swallow any exceptions.
        
        Args:
            call: Callable to execute
        """
        try:
            call()
        except Exception:
            pass

    def submit(self, fn: Callable, *args, **kwargs) -> None:
        """Submit a task to the shared executor (fire-and-forget).
        
        Args:
            fn: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        self._executor.submit(self._swallow, lambda: fn(*args, **kwargs))
