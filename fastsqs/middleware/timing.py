import time
from .base import Middleware


class TimingMsMiddleware(Middleware):
    def __init__(self, store_key_start: str = "start_ns", store_key_ms: str = "duration_ms"):
        super().__init__()
        self.store_key_start = store_key_start
        self.store_key_ms = store_key_ms

    async def before(self, payload, record, context, ctx):
        msg_id = record.get("messageId", "UNKNOWN")
        ctx[self.store_key_start] = time.perf_counter_ns()
        self._log("debug", f"Processing started", msg_id=msg_id)

    async def after(self, payload, record, context, ctx, error):
        msg_id = record.get("messageId", "UNKNOWN")
        start = ctx.get(self.store_key_start)
        if start is not None:
            dur_ns = time.perf_counter_ns() - start
            duration_ms = round(dur_ns / 1_000_000, 3)
            ctx[self.store_key_ms] = duration_ms
            
            status = "FAILED" if error else "SUCCESS"
            self._log("info", f"Processing completed", 
                     msg_id=msg_id, status=status, duration_ms=duration_ms)