from __future__ import annotations

from typing import Any, Awaitable, Callable, Union, TypeVar
from enum import Enum
from pydantic import BaseModel


class QueueType(Enum):
    STANDARD = "standard"
    FIFO = "fifo"


Handler = Callable[..., Union[None, Awaitable[None], Any]]
RouteValue = Union[str, int]
T = TypeVar('T', bound=BaseModel)