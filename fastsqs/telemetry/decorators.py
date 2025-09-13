import functools
import inspect
from opentelemetry.trace import SpanKind
from .telemetry import Telemetry


def trace_function(span_name, span_kind=SpanKind.INTERNAL):
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                telemetry = Telemetry()

                if not telemetry.telemetry_enabled:
                    return await func(*args, **kwargs)

                module_name = getattr(func, "__module__", "unknown")
                telemetry.count_function_call(span_name, module_name)

                tracer = telemetry.get_tracer()
                if tracer:
                    with tracer.start_as_current_span(span_name, kind=span_kind):
                        return await func(*args, **kwargs)
                return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                telemetry = Telemetry()

                if not telemetry.telemetry_enabled:
                    return func(*args, **kwargs)

                module_name = getattr(func, "__module__", "unknown")
                telemetry.count_function_call(span_name, module_name)

                tracer = telemetry.get_tracer()
                if tracer:
                    with tracer.start_as_current_span(span_name, kind=span_kind):
                        return func(*args, **kwargs)
                return func(*args, **kwargs)
            
            return sync_wrapper
    return decorator
