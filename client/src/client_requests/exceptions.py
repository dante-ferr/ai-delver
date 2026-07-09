class ClientError(Exception):
    """Base exception for client-side errors."""
    pass


class APIError(ClientError):
    """Raised when the intelligence API returns a bad status code or failure."""

    def __init__(self, endpoint: str, status_code: int, detail: str):
        super().__init__(
            f"API Server error on {endpoint} (HTTP {status_code}): {detail}"
        )
        self.endpoint = endpoint
        self.status_code = status_code
        self.detail = detail


class WebSocketError(ClientError):
    """Raised when communication with the WebSocket fails or receives an error frame."""
    pass
