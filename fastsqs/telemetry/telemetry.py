import os
from enum import Enum
from typing import Callable

from opentelemetry.sdk.resources import Resource

from ..concurrency.decorators import background

from .services import Tracer, Metrics


class Environment(Enum):
    PRODUCTION = "production"
    HOMOLOG = "homolog"
    LOCAL = "local"


ENVIRONMENT = os.getenv("OTEL_ENVIRONMENT", Environment.LOCAL.value)
TRACER_NAME = os.getenv("OTEL_TRACER_NAME", "default_tracer")


class Telemetry:
    _instance = None

    TELEMETRY_ENVIRONMENTS = {
        Environment.PRODUCTION.value,
        Environment.HOMOLOG.value
    }

    use_otel = os.getenv("USE_OTEL", "true").lower() != "false"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configure_telemetry()
        return cls._instance

    def _configure_telemetry(self) -> None:
        self.tracer_name = TRACER_NAME
        self.environment = ENVIRONMENT
        self.telemetry_enabled = (
            self.use_otel and
            self.environment in self.TELEMETRY_ENVIRONMENTS
        )

        self._tracer: Tracer | None = None
        self._counter: Metrics | None = None

        if self.telemetry_enabled:
            self._init_telemetry()
        else:
            self._init_noop()

    def _init_telemetry(self) -> None:
        try:
            app_resource = Resource.create({})
            self._tracer = Tracer(self.tracer_name, app_resource)
            self._counter = Metrics(self.tracer_name, app_resource)
        except Exception:
            self._init_noop()
            self.telemetry_enabled = False

    def _init_noop(self) -> None:
        self._tracer = None
        self._counter = None

    def get_tracer(self):
        return self._tracer.tracer if self._tracer else None

    def get_counter(self):
        return self._counter.counter if self._counter else None

    def get_operation_counter(self):
        return self._counter.operation_counter if self._counter else None

    @background
    def count_function_call(self, span_name: str, module: str) -> None:
        if not self.telemetry_enabled:
            return
        counter = self.get_counter()
        if counter:
            counter.add(
                1,
                {
                    "function.name": span_name,
                    "function.module": module or "unknown",
                    "environment": self.environment,
                },
            )

    @background
    def count_operation(
        self, operation_name: str, count: int = 1, **additional_attributes
    ) -> None:
        if not self.telemetry_enabled:
            return

        counter = self.get_operation_counter()
        if counter:
            attributes = {
                "operation": operation_name,
                "environment": self.environment,
                "service.name": os.getenv("OTEL_SERVICE_NAME", "unknown"),
                **additional_attributes
            }
            counter.add(count, attributes)

    def force_flush(self, timeout_millis: int = 5000) -> None:
        if not self.telemetry_enabled:
            return

        tasks = self._flush_tasks(timeout_millis)
        for t in tasks:
            try:
                t()
            except Exception:
                pass

    def _flush_tasks(self, timeout_millis: int) -> list[Callable[[], None]]:
        tasks: list[Callable[[], None]] = []
        if self._tracer is not None:
            tasks.append(lambda: self._tracer.force_flush(timeout_millis))
        if self._counter is not None:
            tasks.append(lambda: self._counter.force_flush(timeout_millis))
        return tasks