from __future__ import annotations

import inspect
from typing import Any, Awaitable, List, Optional


class Middleware:
    async def before(self, payload: dict, record: dict, context: Any, ctx: dict) -> None:
        return None

    async def after(
        self, payload: dict, record: dict, context: Any, ctx: dict, error: Optional[Exception]
    ) -> None:
        return None


def call_middleware_hook(mw: Middleware, hook: str, *args) -> Awaitable[None]:
    fn = getattr(mw, hook, None)
    if fn is None:
        async def _noop():
            return None
        return _noop()
    res = fn(*args)
    if inspect.isawaitable(res):
        return res

    async def _wrap():
        return None

    return _wrap()


async def run_middlewares(
    mws: List[Middleware],
    when: str,
    payload: dict,
    record: dict,
    context: Any,
    ctx: dict,
    error: Optional[Exception] = None,
) -> None:
    if when == "before":
        for mw in mws:
            await call_middleware_hook(mw, "before", payload, record, context, ctx)
    elif when == "after":
        for mw in reversed(mws):
            await call_middleware_hook(mw, "after", payload, record, context, ctx, error)
    else:
        raise ValueError("when must be 'before' or 'after'")