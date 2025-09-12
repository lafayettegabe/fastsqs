"""Context-aware state management for request-specific logging."""

from contextvars import ContextVar
from typing import Optional, Any, Dict


class LoggingState:
    """Data model for request-specific logging state."""

    def __init__(self):
        self.request_id: Optional[str] = None
        self.lambda_context: Optional[Any] = None
        self.custom_fields: Dict[str, Any] = {}

    def to_context_info(self) -> Dict[str, Any]:
        """Convert to context_info format for build_log_entry."""
        return {
            'request_id': self.request_id,
            'lambda_context': self.lambda_context,
            'custom_fields': self.custom_fields
        }


class LoggingStateManager:
    """Manages request-specific logging state using ContextVar."""

    _logging_state: ContextVar[Optional[LoggingState]] = ContextVar(
        "_logging_state", default=None
    )

    @staticmethod
    def set_lambda_context(lambda_context: Any,
                          request_id: Optional[str] = None,
                          custom_fields: Optional[Dict[str, Any]] = None
                          ) -> None:
        """Set Lambda context and related information."""
        state = LoggingState()
        state.lambda_context = lambda_context
        state.request_id = (request_id or
                           getattr(lambda_context, 'aws_request_id', None))
        state.custom_fields = custom_fields or {}
        LoggingStateManager._logging_state.set(state)

    @staticmethod
    def set_request_id(request_id: str,
                      custom_fields: Optional[Dict[str, Any]] = None
                      ) -> None:
        """Set request ID and custom fields."""
        state = LoggingState()
        state.request_id = request_id
        state.custom_fields = custom_fields or {}
        LoggingStateManager._logging_state.set(state)

    @staticmethod
    def update_custom_fields(custom_fields: Dict[str, Any]) -> None:
        """Update custom fields in current state."""
        current_state = LoggingStateManager.get_state()
        current_state.custom_fields.update(custom_fields)
        LoggingStateManager._logging_state.set(current_state)

    @staticmethod
    def get_state() -> LoggingState:
        """Get current logging state."""
        current_state = LoggingStateManager._logging_state.get()
        if current_state is None:
            current_state = LoggingState()
            LoggingStateManager._logging_state.set(current_state)
        return current_state

    @staticmethod
    def get_context_info() -> Dict[str, Any]:
        """Get context info for logging."""
        return LoggingStateManager.get_state().to_context_info()

    @staticmethod
    def clear() -> None:
        """Clear current state."""
        LoggingStateManager._logging_state.set(None)
