import time
from .base import Middleware


class TimingMsMiddleware(Middleware):
    def __init__(self, store_key_start: str = "start_ns", store_key_ms: str = "duration_ms"):
        self.store_key_start = store_key_start
        self.store_key_ms = store_key_ms

    async def before(self, payload, record, context, ctx):
        ctx[self.store_key_start] = time.perf_counter_ns()

    async def after(self, payload, record, context, ctx, error):
        start = ctx.get(self.store_key_start)
        if start is not None:
            dur_ns = time.perf_counter_ns() - start
            ctx[self.store_key_ms] = round(dur_ns / 1_000_000, 3)