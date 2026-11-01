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
    """HTTP 401, invalid or missing API key."""

    status_code = 401


class AuthorizationError(TrigvError):
    """HTTP 403, revoked, expired, or insufficient scope."""

    status_code = 403


class NotFoundError(TrigvError):
    """HTTP 404, channel or resource not found."""

    status_code = 404


class RateLimitError(TrigvError):
    """HTTP 429, 60 requests per minute per workspace. Honor ``retry_after_seconds``."""

    status_code = 429

    def __init__(
        self,
        message: str,
        retry_after_seconds: float | bool | None = None,
        *legacy_args: float | None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        # Old 1.0 call style: RateLimitError(message, retryable, retry_after_seconds).
        # A bool in the second position is the old ``retryable`` flag, never seconds.
        if isinstance(retry_after_seconds, bool):
            if len(legacy_args) > 1:
                raise TypeError("RateLimitError got too many positional arguments")
            retry_after_seconds = legacy_args[0] if legacy_args else None
        elif legacy_args:
            raise TypeError("RateLimitError got too many positional arguments")
        self.retry_after_seconds: float | None = retry_after_seconds

    @property
    def retryable(self) -> bool:
        """Always True.

        Deprecated: kept so code written for 1.0 still works. Every 429 is a rate limit,
        so wait ``retry_after_seconds`` and try again. There is no monthly cap any more.
        """
        return True


class ConflictError(TrigvError):
    """HTTP 409, another request is delivering the same idempotency key."""

    status_code = 409

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ServiceUnavailableError(TrigvError):
    """HTTP 503, push delivery is unavailable. Retry with the same idempotency key."""

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


def is_monthly_limit_message(message: str) -> bool:
    """Always returns False.

    Deprecated: kept so code written for 1.0 still works. The monthly event cap was removed.
    """
    return False
