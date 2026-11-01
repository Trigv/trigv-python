"""HTTP client for the Trigv ingest API."""

from __future__ import annotations

import builtins
import json
import os
import random
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from trigv.constants import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_SECONDS, MAX_RETRIES, VERSION
from trigv.errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    TrigvError,
    ValidationError,
)
from trigv.errors import (
    TimeoutError as TrigvTimeoutError,
)
from trigv.retry import parse_retry_after_header
from trigv.types import (
    ConnectionApiKey,
    ConnectionResult,
    ConnectionWorkspace,
    Event,
    HttpResponse,
    SendEventParams,
    SendEventResult,
)
from trigv.validation import validate_send_event_params

T = TypeVar("T")

HttpTransport = Callable[[str, str, dict[str, str], bytes | None, float], HttpResponse]

_RETRYABLE_STATUSES = {502, 504}


def _parse_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _error_from_response(
    status: int,
    body: dict[str, Any] | None,
    headers: dict[str, str] | None = None,
) -> None:
    message = str(body.get("message")) if body and body.get("message") is not None else None
    if not message:
        message = f"Trigv API returned HTTP {status}"

    retry_after = None
    request_id = None
    if headers is not None:
        retry_after = parse_retry_after_header(headers.get("retry-after"))
        request_id = headers.get("x-request-id")

    error: TrigvError
    if status == 401:
        error = AuthenticationError(message)
    elif status == 403:
        error = AuthorizationError(message)
    elif status == 404:
        error = NotFoundError(message)
    elif status == 409:
        error = ConflictError(message, retry_after)
    elif status == 422:
        errors = body.get("errors") if body else None
        if not isinstance(errors, dict):
            errors = {}
        normalized: dict[str, list[str]] = {}
        for field, messages in errors.items():
            if isinstance(messages, list):
                normalized[str(field)] = [str(item) for item in messages]
            else:
                normalized[str(field)] = [str(messages)]
        error = ValidationError(message, normalized)
    elif status == 429:
        error = RateLimitError(message, retry_after)
    elif status == 503:
        error = ServiceUnavailableError(message, retry_after)
    else:
        error = ApiError(message, status, body)
    error.request_id = request_id
    raise error


def _is_retryable_status(status: int) -> bool:
    return status in _RETRYABLE_STATUSES


def _jitter(max_ms: int) -> float:
    return random.randint(0, max_ms) / 1000.0


def _default_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> HttpResponse:
    request = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return HttpResponse(
                status=response.status,
                body=response_body,
                headers=response_headers,
            )
    except urllib.error.HTTPError as exc:
        with exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return HttpResponse(status=exc.code, body=response_body, headers=response_headers)
    except (builtins.TimeoutError, socket.timeout) as exc:  # noqa: UP041
        raise TrigvTimeoutError() from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (builtins.TimeoutError, socket.timeout)):  # noqa: UP041
            raise TrigvTimeoutError() from exc
        message = str(exc.reason) if exc.reason else "Network request failed"
        raise NetworkError(message, exc) from exc


class Trigv:
    """Trigv workspace ingest client."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.environ.get("TRIGV_API_KEY")
        if not resolved_key or not resolved_key.strip():
            raise ValidationError("api_key is required (or set TRIGV_API_KEY)")

        if max_retries is not None and max_retries < 0:
            raise ValidationError(
                "max_retries must be zero or greater",
                {"max_retries": ["max_retries must be zero or greater"]},
            )

        if timeout is not None and timeout <= 0:
            raise ValidationError(
                "timeout must be greater than zero",
                {"timeout": ["timeout must be greater than zero"]},
            )

        self._api_key = resolved_key.strip()
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS
        self._max_retries = max_retries if max_retries is not None else MAX_RETRIES
        self._transport = transport or _default_transport

    @property
    def user_agent(self) -> str:
        return f"trigv-python/{VERSION}"

    def send_event(self, params: SendEventParams | Mapping[str, object]) -> SendEventResult:
        body = validate_send_event_params(params)
        has_idempotency = bool(body.get("idempotency_key"))

        def parse_success(
            status: int, parsed: dict[str, Any] | None, request_id: str | None
        ) -> SendEventResult:
            if status in (200, 202) and parsed and isinstance(parsed.get("event"), dict):
                return SendEventResult(
                    event=Event.from_dict(parsed["event"]),
                    duplicate=status == 200,
                    request_id=request_id,
                )
            _error_from_response(status, parsed)
            raise AssertionError("unreachable")

        return self._request_with_retry(
            method="POST",
            path="/v1/events",
            body=body,
            allow_retry=has_idempotency,
            parse_success=parse_success,
        )

    def verify_connection(self) -> ConnectionResult:
        def parse_success(
            status: int, parsed: dict[str, Any] | None, request_id: str | None
        ) -> ConnectionResult:
            if (
                status == 200
                and parsed
                and isinstance(parsed.get("workspace"), dict)
                and isinstance(parsed.get("api_key"), dict)
            ):
                return ConnectionResult(
                    workspace=ConnectionWorkspace.from_dict(parsed["workspace"]),
                    api_key=ConnectionApiKey.from_dict(parsed["api_key"]),
                    request_id=request_id,
                )
            _error_from_response(status, parsed)
            raise AssertionError("unreachable")

        return self._request_with_retry(
            method="GET",
            path="/v1/connection",
            body=None,
            allow_retry=True,
            parse_success=parse_success,
        )

    def _request_with_retry(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, str] | None,
        allow_retry: bool,
        parse_success: Callable[[int, dict[str, Any] | None, str | None], T],
    ) -> T:
        last_error: BaseException | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._request_once(
                    method=method,
                    path=path,
                    body=body,
                    parse_success=parse_success,
                )
            except TrigvError as error:
                last_error = error

                if not allow_retry or attempt >= self._max_retries:
                    raise

                if isinstance(error, ApiError):
                    if not _is_retryable_status(error.status_code):
                        raise
                elif not isinstance(
                    error,
                    (
                        NetworkError,
                        TrigvTimeoutError,
                        RateLimitError,
                        ConflictError,
                        ServiceUnavailableError,
                    ),
                ):
                    raise

                backoff = 0.5 * (2**attempt) + _jitter(250)
                retry_after = getattr(error, "retry_after_seconds", None)
                if retry_after is not None:
                    # Waiting longer than the timeout is pointless: raise the real error.
                    if retry_after > self._timeout:
                        raise
                    backoff = retry_after
                time.sleep(min(backoff, self._timeout))

        assert last_error is not None
        raise last_error

    def _request_once(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, str] | None,
        parse_success: Callable[[int, dict[str, Any] | None, str | None], T],
    ) -> T:
        url = f"{self._base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": self.user_agent,
        }
        payload = json.dumps(body).encode("utf-8") if body is not None else None

        try:
            response = self._transport(method, url, headers, payload, self._timeout)
        except TrigvTimeoutError:
            raise
        except NetworkError:
            raise
        except Exception as exc:
            raise NetworkError(str(exc), exc) from exc

        parsed = _parse_json(response.body)

        if 200 <= response.status < 300:
            return parse_success(response.status, parsed, response.headers.get("x-request-id"))

        _error_from_response(response.status, parsed, response.headers)
        raise AssertionError("unreachable")
