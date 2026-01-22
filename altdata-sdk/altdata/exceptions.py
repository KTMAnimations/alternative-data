"""Custom exceptions for the AltData SDK."""

from typing import Optional


class AltDataError(Exception):
    """Base exception for AltData SDK errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(AltDataError):
    """Raised when API authentication fails (401)."""

    def __init__(self, message: str = "Invalid or missing API key") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(AltDataError):
    """Raised when a resource is not found (404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class RateLimitError(AltDataError):
    """Raised when API rate limit is exceeded (429)."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None
    ) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ValidationError(AltDataError):
    """Raised when request validation fails (422)."""

    def __init__(self, message: str = "Request validation failed") -> None:
        super().__init__(message, status_code=422)


class ServerError(AltDataError):
    """Raised when the server returns a 5xx error."""

    def __init__(self, message: str = "Server error") -> None:
        super().__init__(message, status_code=500)


class ConnectionError(AltDataError):
    """Raised when unable to connect to the API."""

    def __init__(self, message: str = "Unable to connect to API") -> None:
        super().__init__(message, status_code=None)
