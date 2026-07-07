"""Exception types for the Trigv Python SDK."""

from __future__ import annotations

from typing import Any


class TrigvError(Exception):
    """Base exception for all Trigv SDK errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

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
    """HTTP 429 — per-minute burst or monthly workspace cap."""

    status_code = 429

    def __init__(
        self,
        message: str,
        retryable: bool = True,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
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


def is_monthly_limit_message(message: str) -> bool:
    """Return True when a 429 message indicates the monthly workspace cap."""
    return "Monthly event limit" in message
