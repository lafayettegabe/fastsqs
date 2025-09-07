from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class ThreadPoolManager:
    """
    Manager for a shared ThreadPoolExecutor with a hard cap on the
    number of worker threads (max = 1024 for AWS Lambda safety).
    """

    MAX_WORKERS: int = 1024
    THREAD_NAME_PREFIX: str = "thread-pool-manager"
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configure_executor()
        return cls._instance

    def _configure_executor(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix=self.THREAD_NAME_PREFIX,
        )

    @staticmethod
    def _swallow(call: Callable[[], None]) -> None:
        try:
            call()
        except Exception:
            pass

    def submit(self, fn: Callable, *args, **kwargs) -> None:
        """Submit a task to the shared executor (fire-and-forget), swallowing exceptions."""
        self._executor.submit(self._swallow, lambda: fn(*args, **kwargs))
