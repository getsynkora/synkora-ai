"""Synkora SDK exceptions."""

from __future__ import annotations


class SynkoraError(Exception):
    """Base exception for all Synkora SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r})"


class AuthError(SynkoraError):
    """Raised when the API key is missing, invalid, or expired."""


class AgentNotFoundError(SynkoraError):
    """Raised when the requested agent does not exist or is not accessible."""


class RateLimitError(SynkoraError):
    """Raised when the API rate limit is exceeded."""


class StreamError(SynkoraError):
    """Raised when an error event is received during streaming."""

    def __init__(
        self,
        message: str,
        error_type: str | None = None,
        violation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.violation_id = violation_id


class APIError(SynkoraError):
    """Raised for unexpected API responses (5xx, malformed JSON, etc.)."""
