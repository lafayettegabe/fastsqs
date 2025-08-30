from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel

from ..types import Handler
from ..middleware import Middleware

if TYPE_CHECKING:
    from .router import QueueRouter


@dataclass
class RouteEntry:
    handler: Optional[Handler] = None
    model: Optional[type[BaseModel]] = None
    middlewares: List[Middleware] = field(default_factory=list)
    subrouter: Optional["QueueRouter"] = None
    
    @property
    def is_nested(self) -> bool:
        return self.subrouter is not None