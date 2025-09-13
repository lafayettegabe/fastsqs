"""Thread pool management for background task execution."""

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, List
import time


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
        self._pending_futures: List[Future] = []

    @staticmethod
    def _swallow(call: Callable[[], None]) -> None:
        try:
            call()
        except Exception:
            pass

    def submit(self, fn: Callable, *args, **kwargs) -> None:
        future = self._executor.submit(
            self._swallow, lambda: fn(*args, **kwargs)
        )
        self._pending_futures.append(future)

    def wait_for_completion(self, timeout_seconds: float = 10.0) -> None:
        if not self._pending_futures:
            return

        start_time = time.time()
        completed_futures = []

        for future in self._pending_futures:
            remaining_time = timeout_seconds - (time.time() - start_time)
            if remaining_time <= 0:
                break

            try:
                future.result(timeout=remaining_time)
                completed_futures.append(future)
            except Exception:
                completed_futures.append(future)

        for future in completed_futures:
            self._pending_futures.remove(future)
