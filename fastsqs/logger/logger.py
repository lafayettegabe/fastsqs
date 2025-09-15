"""Singleton logger with OpenTelemetry and Elasticsearch support."""

import logging
import json

from .config import OtelConfig
from ..concurrency.decorators import background
from .elasticsearch_handler import ElasticsearchHandler
from .state import LoggingStateManager

otel_config = OtelConfig()
USE_OTEL = otel_config.use_otel


class Logger:
    """Singleton logger with configurable handlers and background logging.

    Uses ContextVar-based state management for request-specific context
    while maintaining singleton pattern for logger configuration.
    """
    _instance = None

    def __new__(cls):
        """Create or return the singleton logger instance."""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._configure_logger()
        return cls._instance

    def _configure_logger(self):
        """Configure the logger with appropriate handlers and settings."""
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
        """Add a handler to the logger with proper formatting.

        Args:
            handler: Logging handler to add
        """
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
        """Log a message with structured data in background.

        Args:
            level: Log level (debug, info, warning, error, etc.)
            message: Log message
            **data: Additional structured data to include
        """
        log_method = getattr(self._logger, level, self._logger.debug)
        if data:
            # Pass data as extra fields to the LogRecord
            log_method(message, extra={'data': data})
        else:
            log_method(message)

    @staticmethod
    def set_lambda_context(lambda_context, request_id=None, custom_fields=None):
        """Set Lambda context for current execution context.

        Args:
            lambda_context: AWS Lambda context object
            request_id: Optional custom request ID
                       (uses aws_request_id if not provided)
            custom_fields: Optional dictionary of custom fields to
                          include in logs
        """
        LoggingStateManager.set_lambda_context(
            lambda_context=lambda_context,
            request_id=request_id,
            custom_fields=custom_fields
        )

    @staticmethod
    def set_request_id(request_id, custom_fields=None):
        """Set request ID for current execution context.

        Args:
            request_id: Request ID for tracing
            custom_fields: Optional dictionary of custom fields to
                          include in logs
        """
        LoggingStateManager.set_request_id(
            request_id=request_id,
            custom_fields=custom_fields
        )

    @staticmethod
    def update_custom_fields(custom_fields):
        """Update custom fields for current execution context.

        Args:
            custom_fields: Dictionary of custom fields to add/update
        """
        LoggingStateManager.update_custom_fields(custom_fields)

    @staticmethod
    def clear_context():
        """Clear current execution context."""
        LoggingStateManager.clear()

    # Convenience methods for common log levels
    def info(self, message, **data):
        """Log info message."""
        self.log('info', message, **data)

    def debug(self, message, **data):
        """Log debug message."""
        self.log('debug', message, **data)

    def warning(self, message, **data):
        """Log warning message."""
        self.log('warning', message, **data)

    def error(self, message, **data):
        """Log error message."""
        self.log('error', message, **data)

    def critical(self, message, **data):
        """Log critical message."""
        self.log('critical', message, **data)
