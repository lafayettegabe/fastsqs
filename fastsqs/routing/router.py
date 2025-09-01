from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Iterable, List, Optional, Union
from pydantic import BaseModel, ValidationError

from ..types import Handler, RouteValue
from ..middleware import Middleware, run_middlewares
from ..utils import invoke_handler
from .entry import RouteEntry


class QueueRouter:
    def __init__(
        self, 
        key: str, 
        name: Optional[str] = None, 
        payload_scope: str = "root",
        inherit_middlewares: bool = True
    ):
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
        values = [value] if isinstance(value, (str, int)) else list(value)
        
        if router is not None:
            for v in values:
                k = str(v)
                if k in self._routes:
                    self._routes[k].subrouter = router
                else:
                    self._routes[k] = RouteEntry(subrouter=router)
            return router
        
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
        if root_payload is None:
            root_payload = payload
            
        if parent_middlewares is None:
            parent_middlewares = []

        if self.key not in payload:
            return False
            
        key_value = payload.get(self.key)
        if key_value is None:
            return False
            
        str_value = str(key_value)
        
        route_path = ctx.setdefault("route_path", [])
        route_path.append(f"{self.key}={str_value}")
        
        entry = self._routes.get(str_value)
        
        if entry is None and self._wildcard_handler:
            entry = self._routes.get("*")
            
        if entry is None:
            if self._default_handler:
                await self._execute_handler(
                    self._default_handler,
                    None,
                    [],
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
        
        if entry.is_nested and entry.subrouter:
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
        all_mws = parent_middlewares + self._middlewares + route_middlewares
        
        if self.payload_scope == "root":
            handler_payload = root_payload
        elif self.payload_scope == "both":
            handler_payload = root_payload
        else:
            handler_payload = payload
        
        err: Optional[Exception] = None
        await run_middlewares(all_mws, "before", handler_payload, record, context, ctx)
        
        try:
            if model is not None:
                try:
                    msg = model.model_validate(payload)
                except ValidationError as e:
                    raise ValidationError(f"Validation failed for {self.key}: {e}")
            else:
                sig = inspect.signature(handler)
                params = list(sig.parameters.values())
                
                if params and hasattr(params[0].annotation, 'model_validate'):
                    model_class = params[0].annotation
                    try:
                        msg = model_class.model_validate(payload)
                    except ValidationError as e:
                        raise ValidationError(f"Validation failed for {model_class.__name__}: {e}")
                else:
                    from ..events import SQSEvent
                    msg = SQSEvent.model_validate(payload)
            
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            
            if len(params) >= 2 and 'ctx' in params[1]:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(msg, ctx)
                else:
                    result = handler(msg, ctx)
            else:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(msg)
                else:
                    result = handler(msg)
                
        except Exception as e:
            err = e
            raise
        finally:
            await run_middlewares(all_mws, "after", handler_payload, record, context, ctx, err)