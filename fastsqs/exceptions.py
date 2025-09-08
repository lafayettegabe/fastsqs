class RouteNotFound(Exception):
    """Exception raised when no route handler is found for a message."""
    pass


class InvalidMessage(Exception):
    """Exception raised when a message has invalid format or content."""
    pass