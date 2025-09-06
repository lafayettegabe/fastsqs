from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, List

from .types import Handler


def group_records_by_message_group(
    records: List[dict]
) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = {}
    
    for record in records:
        attributes = record.get("attributes", {})
        message_group_id = attributes.get("messageGroupId", "default")
        
        if message_group_id not in groups:
            groups[message_group_id] = []
        groups[message_group_id].append(record)
    
    return groups


def select_kwargs(fn: Handler, **candidates) -> Dict[str, Any]:
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return candidates
    accepted = {
        p.name for p in sig.parameters.values()
        if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
    }
    return {k: v for k, v in candidates.items() if k in accepted}


async def invoke_handler(fn: Handler, **kwargs) -> Any:
    kw = select_kwargs(fn, **kwargs)
    
    if inspect.iscoroutinefunction(fn):
        result = await fn(**kw)
    else:
        result = fn(**kw)
        if inspect.isawaitable(result):
            result = await result
    
    return result


def shallow_mask(d: dict, fields: List[str], mask: str = "***") -> dict:
    if not fields:
        return d
    out = dict(d)
    for f in fields:
        if f in out:
            out[f] = mask
    return out