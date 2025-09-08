"""Type definitions for FastSQS."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Union, TypeVar
from enum import Enum
from pydantic import BaseModel


class QueueType(Enum):
    """Enumeration for SQS queue types."""
    STANDARD = "standard"
    FIFO = "fifo"


Handler = Callable[..., Union[None, Awaitable[None], Any]]
"""Type alias for message handler functions."""

RouteValue = Union[str, int]
"""Type alias for route values."""

T = TypeVar('T', bound=BaseModel)
"""Type variable bound to Pydantic BaseModel."""
