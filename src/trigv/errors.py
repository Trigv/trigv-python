"""Exception types for the Trigv Python SDK."""

from __future__ import annotations

from typing import Any


class TrigvError(Exception):
    """Base exception for all Trigv SDK errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
        #: Value of the ``X-Request-ID`` response header, when the API answered.
        self.request_id: str | None = None

    def __str__(self) -> str:
        return self.message


class ValidationError(TrigvError):
    """Client-side or HTTP 422 validation failure."""

    def __init__(self, message: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(message)
        self.errors: dict[str, list[str]] = errors or {}


class AuthenticationError(TrigvError):
    """HTTP 401 — invalid or missing API key."""

    status_code = 401


class AuthorizationError(TrigvError):
    """HTTP 403 — revoked, expired, or insufficient scope."""

    status_code = 403


class NotFoundError(TrigvError):
    """HTTP 404 — channel or resource not found."""

    status_code = 404


class RateLimitError(TrigvError):
    """HTTP 429 — 60 requests per minute per workspace. Honor ``retry_after_seconds``."""

    status_code = 429

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ConflictError(TrigvError):
    """HTTP 409 — another request is delivering the same idempotency key."""

    status_code = 409

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ServiceUnavailableError(TrigvError):
    """HTTP 503 — push delivery is unavailable. Retry with the same idempotency key."""

    status_code = 503

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ApiError(TrigvError):
    """Other HTTP 4xx/5xx responses."""

    def __init__(self, message: str, status_code: int, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class NetworkError(TrigvError):
    """DNS, connection reset, or other transport failure."""

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class TimeoutError(TrigvError):
    """Request exceeded the configured timeout."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message)
