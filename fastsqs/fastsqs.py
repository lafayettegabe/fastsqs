from __future__ import annotations

import inspect
import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Union, TypeVar

from pydantic import BaseModel, ValidationError

Handler = Callable[..., Union[None, Awaitable[None]]]
RouteValue = Union[str, int]
T = TypeVar('T', bound=BaseModel)


class RouteNotFound(Exception):
    pass


class InvalidMessage(Exception):
    pass


class Middleware:
    """Async middleware hooks."""

    async def before(self, payload: dict, record: dict, context: Any, ctx: dict) -> None:
        return None

    async def after(
        self, payload: dict, record: dict, context: Any, ctx: dict, error: Optional[Exception]
    ) -> None:
        return None


def _call_mw(mw: Middleware, hook: str, *args) -> Awaitable[None]:
    fn = getattr(mw, hook, None)
    if fn is None:
        async def _noop():
            return None
        return _noop()
    res = fn(*args)
    if inspect.isawaitable(res):
        return res  # type: ignore[return-value]

    async def _wrap():
        return None

    return _wrap()


async def _run_middlewares(
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
            await _call_mw(mw, "before", payload, record, context, ctx)
    elif when == "after":
        for mw in reversed(mws):
            await _call_mw(mw, "after", payload, record, context, ctx, error)
    else:
        raise ValueError("when must be 'before' or 'after'")


class TimingMsMiddleware(Middleware):
    """Stores per-record latency (ns start, ms duration) in ctx."""

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


def _shallow_mask(d: dict, fields: List[str], mask: str = "***") -> dict:
    if not fields:
        return d
    out = dict(d)
    for f in fields:
        if f in out:
            out[f] = mask
    return out


class LoggingMiddleware(Middleware):
    """Structured logging with optional payload/record/context and shallow masking."""

    def __init__(
        self,
        logger: Optional[Callable[[dict], None]] = None,
        level: str = "INFO",
        include_payload: bool = True,
        include_record: bool = False,
        include_context: bool = False,
        mask_fields: Optional[List[str]] = None,
    ):
        self.level = level
        self.include_payload = include_payload
        self.include_record = include_record
        self.include_context = include_context
        self.mask_fields = mask_fields or []
        if logger is None:
            def _default_logger(obj: dict) -> None:
                print(json.dumps(obj, ensure_ascii=False))
            self.logger = _default_logger
        else:
            self.logger = logger

    async def before(self, payload, record, context, ctx):
        entry = {
            "ts": time.time(),
            "lvl": self.level,
            "stage": "before",
            "msg_id": record.get("messageId"),
            "route": ctx.get("route_path", []),
        }
        if self.include_payload:
            entry["payload"] = _shallow_mask(payload, self.mask_fields)
        if self.include_record:
            entry["record"] = record
        if self.include_context:
            entry["context_repr"] = repr(context)
        self.logger(entry)

    async def after(self, payload, record, context, ctx, error):
        entry = {
            "ts": time.time(),
            "lvl": "ERROR" if error else self.level,
            "stage": "after",
            "msg_id": record.get("messageId"),
            "route": ctx.get("route_path", []),
            "duration_ms": ctx.get("duration_ms"),
            "error": None if not error else repr(error),
        }
        if self.include_payload:
            entry["payload"] = _shallow_mask(payload, self.mask_fields)
        if self.include_record:
            entry["record"] = record
        if self.include_context:
            entry["context_repr"] = repr(context)
        self.logger(entry)


def _select_kwargs(fn: Handler, **candidates) -> Dict[str, Any]:
    """Pass only params the handler accepts."""
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return candidates
    accepted = {
        p.name for p in sig.parameters.values()
        if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
    }
    return {k: v for k, v in candidates.items() if k in accepted}


async def _invoke(fn: Handler, **kwargs) -> None:
    kw = _select_kwargs(fn, **kwargs)
    res = fn(**kw)
    if inspect.isawaitable(res):
        await res  # type: ignore[misc]


@dataclass
class RouteEntry:
    handler: Optional[Handler] = None
    model: Optional[type[BaseModel]] = None
    middlewares: List[Middleware] = field(default_factory=list)
    subrouter: Optional["QueueRouter"] = None
    
    @property
    def is_nested(self) -> bool:
        return self.subrouter is not None


class QueueRouter:
    """Routes by a key in the payload; supports nested routers and per-route validation."""

    def __init__(
        self, 
        key: str, 
        name: Optional[str] = None, 
        payload_scope: str = "root",
        inherit_middlewares: bool = True
    ):
        """
        Initialize a QueueRouter.
        
        Args:
            key: The field name to check in the payload
            name: Optional name for the router (defaults to key)
            payload_scope: How to pass payload to handlers:
                - "root": Pass the original root payload
                - "current": Pass the current level payload
                - "both": Pass both as payload and current_payload
            inherit_middlewares: Whether nested routers inherit parent middlewares
        """
        if payload_scope not in ("current", "root", "both"):
            raise ValueError("payload_scope must be 'current', 'root', or 'both'")
        self.key = key
        self.name = name or key
        self.payload_scope = payload_scope
        self.inherit_middlewares = inherit_middlewares
        self._routes: Dict[str, RouteEntry] = {}
        self._middlewares: List[Middleware] = []
        self._default_handler: Optional[Handler] = None
        self._wildcard_handler: Optional[Handler] = None

    def route(
        self,
        value: Union[RouteValue, Iterable[RouteValue], None] = None,
        *,
        model: Optional[type[BaseModel]] = None,
        middlewares: Optional[List[Middleware]] = None,
    ) -> Callable[[Handler], Handler]:
        """
        Decorator to register a handler for specific route values.
        
        Args:
            value: The value(s) to match, or None for default handler
            model: Optional Pydantic model for validation
            middlewares: Additional middlewares for this route
        """
        if value is None:
            def decorator(fn: Handler) -> Handler:
                self._default_handler = fn
                return fn
            return decorator
            
        values = [value] if isinstance(value, (str, int)) else list(value)

        def decorator(fn: Handler) -> Handler:
            for v in values:
                k = str(v)
                if k in self._routes:
                    existing = self._routes[k]
                    if existing.handler is not None:
                        raise ValueError(f"Duplicate handler for {self.key}={k}")
                    existing.handler = fn
                    existing.model = model
                    existing.middlewares = list(middlewares or [])
                else:
                    self._routes[k] = RouteEntry(
                        handler=fn, 
                        model=model, 
                        middlewares=list(middlewares or [])
                    )
            return fn

        return decorator
    
    def wildcard(
        self,
        model: Optional[type[BaseModel]] = None,
        middlewares: Optional[List[Middleware]] = None,
    ) -> Callable[[Handler], Handler]:
        """Register a wildcard handler that matches any value."""
        def decorator(fn: Handler) -> Handler:
            self._wildcard_handler = fn
            if "*" not in self._routes:
                self._routes["*"] = RouteEntry(
                    handler=fn,
                    model=model,
                    middlewares=list(middlewares or [])
                )
            return fn
        return decorator

    def subrouter(
        self,
        value: Union[RouteValue, Iterable[RouteValue]],
        router: Optional["QueueRouter"] = None,
    ) -> Union["QueueRouter", Callable[["QueueRouter"], "QueueRouter"]]:
        """
        Attach a subrouter for nested routing.
        
        Can be used as:
        - router.subrouter("value", existing_router)
        - @router.subrouter("value")
          def nested_router() -> QueueRouter: ...
        """
        values = [value] if isinstance(value, (str, int)) else list(value)
        
        if router is not None:
            # Direct attachment
            for v in values:
                k = str(v)
                if k in self._routes:
                    self._routes[k].subrouter = router
                else:
                    self._routes[k] = RouteEntry(subrouter=router)
            return router
        
        # Decorator style
        def decorator(router_or_fn: Union[QueueRouter, Callable[[], QueueRouter]]) -> QueueRouter:
            if callable(router_or_fn) and not isinstance(router_or_fn, QueueRouter):
                router_instance = router_or_fn()
            else:
                router_instance = router_or_fn
                
            for v in values:
                k = str(v)
                if k in self._routes:
                    self._routes[k].subrouter = router_instance
                else:
                    self._routes[k] = RouteEntry(subrouter=router_instance)
            return router_instance
        
        return decorator

    def add_middleware(self, mw: Middleware) -> None:
        """Add a middleware to this router."""
        self._middlewares.append(mw)

    async def dispatch(
        self,
        payload: dict,
        record: dict,
        context: Any,
        ctx: dict,
        root_payload: Optional[dict] = None,
        parent_middlewares: Optional[List[Middleware]] = None,
    ) -> bool:
        """
        Dispatch a message through the routing tree.
        
        Returns True if a handler was found and executed, False otherwise.
        """
        if root_payload is None:
            root_payload = payload
            
        if parent_middlewares is None:
            parent_middlewares = []

        # Check if the key exists in payload
        if self.key not in payload:
            return False
            
        key_value = payload.get(self.key)
        if key_value is None:
            return False
            
        str_value = str(key_value)
        
        # Update route path in context
        route_path = ctx.setdefault("route_path", [])
        route_path.append(f"{self.key}={str_value}")
        
        # Try to find matching route
        entry = self._routes.get(str_value)
        
        # Fallback to wildcard if no exact match
        if entry is None and self._wildcard_handler:
            entry = self._routes.get("*")
            
        if entry is None:
            # Try default handler if no match
            if self._default_handler:
                await self._execute_handler(
                    self._default_handler,
                    None,  # No model for default
                    [],    # No extra middlewares
                    payload,
                    record,
                    context,
                    ctx,
                    root_payload,
                    parent_middlewares
                )
                return True
            route_path.pop()  # Remove from path if not handled
            return False
        
        # Handle nested router
        if entry.is_nested and entry.subrouter:
            # Determine which middlewares to pass down
            if self.inherit_middlewares:
                combined_mws = parent_middlewares + self._middlewares + entry.middlewares
            else:
                combined_mws = entry.middlewares
                
            handled = await entry.subrouter.dispatch(
                payload,
                record,
                context,
                ctx,
                root_payload,
                combined_mws
            )
            if handled:
                return True
            route_path.pop()
            return False
        
        # Handle regular handler
        if entry.handler:
            await self._execute_handler(
                entry.handler,
                entry.model,
                entry.middlewares,
                payload,
                record,
                context,
                ctx,
                root_payload,
                parent_middlewares
            )
            return True
            
        route_path.pop()
        return False

    async def _execute_handler(
        self,
        handler: Handler,
        model: Optional[type[BaseModel]],
        route_middlewares: List[Middleware],
        payload: dict,
        record: dict,
        context: Any,
        ctx: dict,
        root_payload: dict,
        parent_middlewares: List[Middleware],
    ) -> None:
        """Execute a handler with all applicable middlewares."""
        # Combine all middlewares
        all_mws = parent_middlewares + self._middlewares + route_middlewares
        
        # Determine what payload to pass
        if self.payload_scope == "root":
            handler_payload = root_payload
        elif self.payload_scope == "both":
            handler_payload = root_payload
        else:  # "current"
            handler_payload = payload
        
        err: Optional[Exception] = None
        await _run_middlewares(all_mws, "before", handler_payload, record, context, ctx)
        
        try:
            data = None
            if model is not None:
                try:
                    data = model.model_validate(payload)
                except ValidationError as e:
                    raise ValidationError(f"Validation failed for {self.key}: {e}")
                    
            # Prepare kwargs based on scope
            handler_kwargs = {
                "payload": handler_payload,
                "record": record,
                "context": context,
                "ctx": ctx,
            }
            
            if self.payload_scope == "both":
                handler_kwargs["current_payload"] = payload
                handler_kwargs["root_payload"] = root_payload
                
            if data is not None:
                handler_kwargs["data"] = data
                handler_kwargs["model"] = data
                
            await _invoke(handler, **handler_kwargs)
            
        except Exception as e:
            err = e
            raise
        finally:
            await _run_middlewares(all_mws, "after", handler_payload, record, context, ctx, err)


class QueueApp:
    """App container exposing an async SQS Lambda handler with partial-batch responses."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        version: str = "",
        debug: bool = False,
        strict: bool = True,
        on_decode_error: str = "fail",
        on_validation_error: str = "fail",
        default_handler: Optional[Handler] = None,
    ):
        """
        Initialize QueueApp.
        
        Args:
            title: Application title
            description: Application description
            version: Application version
            debug: Enable debug logging
            strict: Raise error if no route matches (when no default_handler)
            on_decode_error: How to handle JSON decode errors ("fail" or "skip")
            on_validation_error: How to handle validation errors ("fail" or "skip")
            default_handler: Handler to use when no routes match
        """
        self.title = title
        self.description = description
        self.version = version
        self.debug = debug
        self.strict = strict
        self.on_decode_error = on_decode_error
        self.on_validation_error = on_validation_error
        self.default_handler = default_handler
        self._routers: List[QueueRouter] = []
        self._middlewares: List[Middleware] = []

    def include_router(self, router: QueueRouter) -> None:
        """Include a router in the app."""
        self._routers.append(router)

    def add_middleware(self, mw: Middleware) -> None:
        """Add a global middleware."""
        self._middlewares.append(mw)

    async def _handle_record(self, record: dict, context: Any) -> None:
        """Process a single SQS record."""
        body_str = record.get("body", "")
        msg_id = record.get("messageId") or record.get("message_id") or "UNKNOWN"

        try:
            payload = json.loads(body_str) if body_str else {}
            if not isinstance(payload, dict):
                raise InvalidMessage("Body must be a JSON object")
        except Exception as e:
            if self.debug:
                print(f"[QueueApp] JSON decode error: {e}")
            if self.on_decode_error == "skip":
                return
            raise

        ctx: Dict[str, Any] = {"messageId": msg_id, "route_path": []}

        err: Optional[Exception] = None
        await _run_middlewares(self._middlewares, "before", payload, record, context, ctx)
        
        try:
            handled = False
            for router in self._routers:
                try:
                    if await router.dispatch(payload, record, context, ctx, root_payload=payload):
                        handled = True
                        break
                except ValidationError as ve:
                    if self.debug:
                        print(f"[QueueApp] validation error: {ve}")
                    if self.on_validation_error == "skip":
                        handled = True
                        break
                    else:
                        raise

            if not handled:
                if self.default_handler:
                    await _invoke(
                        self.default_handler, 
                        payload=payload, 
                        record=record, 
                        context=context, 
                        ctx=ctx
                    )
                elif self.strict:
                    raise RouteNotFound(
                        f"No route matched for keys {[r.key for r in self._routers]}"
                    )
                    
        except Exception as e:
            err = e
            raise
        finally:
            await _run_middlewares(self._middlewares, "after", payload, record, context, ctx, err)

    async def _handle_event(self, event: dict, context: Any) -> dict:
        """Handle an SQS event with multiple records."""
        failures: List[Dict[str, str]] = []
        for rec in event.get("Records", []):
            msg_id = rec.get("messageId") or rec.get("message_id") or "UNKNOWN"
            try:
                await self._handle_record(rec, context)
            except Exception as e:
                if self.debug:
                    print(f"[QueueApp] record failed: messageId={msg_id} error={e}")
                failures.append({"itemIdentifier": msg_id})
        return {"batchItemFailures": failures}

    def handler(self, event: dict, context: Any) -> dict:
        return asyncio.run(self._handle_event(event, context))