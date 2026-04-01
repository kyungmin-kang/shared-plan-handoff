class BridgeError(Exception):
    """Base exception for bridge failures."""


class APIError(BridgeError):
    """Raised when the Notion API returns an unexpected response."""

    def __init__(self, message: str, *, status: int | None = None, payload: object | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


class StateError(BridgeError):
    """Raised when local bridge state is invalid."""
