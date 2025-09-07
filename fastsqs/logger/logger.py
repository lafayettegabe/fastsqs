import logging
import json
import os

from .config import OtelConfig
from ..concurrency.decorators import background
from .elasticsearch_handler import ElasticsearchHandler

otel_config = OtelConfig()
USE_OTEL = otel_config.use_otel

class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._configure_logger()
        return cls._instance

    def _configure_logger(self):
        logging.getLogger().setLevel(logging.WARNING)
        self.use_otel = USE_OTEL
        self._logger = logging.getLogger("appLogger")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        if not self._logger.handlers:
            self._add_handler(logging.StreamHandler())
            if USE_OTEL:
                try:
                    self._add_handler(ElasticsearchHandler(use_otel=self.use_otel))
                except Exception as e:
                    self._logger.warning(f"Failed to initialize ElasticsearchHandler: {e}")

    def _add_handler(self, handler):
        try:
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        except Exception as e:
            self._logger.error(
                f"Failed to configure {handler.__class__.__name__}: {e}"
            )

    @background
    def log(self, level, message, **data):
        log_method = getattr(self._logger, level, self._logger.debug)
        if data:
            try:
                message = f"{message} | data: {json.dumps(data, default=str)}"
            except Exception:
                message = f"{message} | data: {data}"
        log_method(message)