"""Tests for the Trigv Python SDK."""

from __future__ import annotations

import json

import pytest

from trigv import Trigv
from trigv.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)
from trigv.types import HttpResponse

API_KEY = "trgv_testkey1_abcdefghijklmnopqrstuvwxyz123456"

SAMPLE_EVENT = {
    "public_id": "01JXXXXXXXXXXXXXXXXXXXXXXX",
    "event_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "sent",
    "level": "info",
    "event_type": None,
    "target_device_count": 1,
    "received_at": "2026-06-16T12:00:00+00:00",
}


def make_transport(handler):
    def transport(method, url, headers, body, timeout):
        return handler(method, url, headers, body, timeout)

    return transport


class TestTrigv:
    def test_requires_api_key(self) -> None:
        with pytest.raises(ValidationError):
            Trigv(api_key="")

    def test_sends_minimum_valid_event(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, body, timeout):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = json.loads(body.decode("utf-8"))
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        result = client.send_event({"channel": "general", "title": "Hello"})

        assert captured["method"] == "POST"
        assert captured["body"] == {"channel": "general", "title": "Hello"}
        headers = captured["headers"]
        assert headers["Authorization"] == f"Bearer {API_KEY}"
        assert headers["Accept"] == "application/json"
        assert result.duplicate is False
        assert result.event.public_id == "01JXXXXXXXXXXXXXXXXXXXXXXX"

    def test_sends_all_optional_fields(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, body, timeout):
            captured["body"] = json.loads(body.decode("utf-8"))
            return HttpResponse(
                status=202,
                body=json.dumps({"event": {**SAMPLE_EVENT, "level": "success"}}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        client.send_event(
            {
                "channel": "deploys",
                "title": "Production deploy complete",
                "description": "Build #42 succeeded in 38s (commit abc1234)",
                "level": "success",
                "delivery_urgency": "standard",
                "event_type": "deploy.completed",
                "idempotency_key": "deploy-prod-42",
                "url": "https://example.com/deployments/42",
            }
        )

        assert captured["body"] == {
            "channel": "deploys",
            "title": "Production deploy complete",
            "description": "Build #42 succeeded in 38s (commit abc1234)",
            "level": "success",
            "delivery_urgency": "standard",
            "event_type": "deploy.completed",
            "idempotency_key": "deploy-prod-42",
            "url": "https://example.com/deployments/42",
        }

    def test_rejects_invalid_level_client_side(self) -> None:
        client = Trigv(
            api_key=API_KEY,
            transport=make_transport(lambda *args: HttpResponse(202, "{}", {})),
            max_retries=0,
        )
        with pytest.raises(ValidationError):
            client.send_event({"channel": "general", "title": "x", "level": "meta"})

    def test_rejects_prohibited_icon_field(self) -> None:
        client = Trigv(
            api_key=API_KEY,
            transport=make_transport(lambda *args: HttpResponse(202, "{}", {})),
            max_retries=0,
        )
        with pytest.raises(ValidationError):
            client.send_event({"channel": "general", "title": "x", "icon": "🚀"})

    def test_handles_duplicate_idempotency(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=200,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        result = client.send_event(
            {"channel": "general", "title": "x", "idempotency_key": "retry-123"}
        )
        assert result.duplicate is True

    def test_maps_401_to_authentication_error(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=401,
                body=json.dumps({"message": "Unauthorized"}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        with pytest.raises(AuthenticationError):
            client.send_event({"channel": "general", "title": "x"})

    def test_maps_404_to_not_found_error(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=404,
                body=json.dumps({"message": "Channel not found."}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        with pytest.raises(NotFoundError):
            client.send_event({"channel": "missing", "title": "x"})

    def test_retries_burst_rate_limit_with_idempotency_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}
        sleeps: list[float] = []

        def handler(method, url, headers, body, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                return HttpResponse(
                    status=429,
                    body=json.dumps({"message": "Too many requests for this API key."}),
                    headers={},
                )
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        monkeypatch.setattr("trigv.client.time.sleep", lambda seconds: sleeps.append(seconds))

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        result = client.send_event({"channel": "general", "title": "x", "idempotency_key": "k1"})

        assert calls["count"] == 2
        assert result.event.public_id == "01JXXXXXXXXXXXXXXXXXXXXXXX"
        assert len(sleeps) == 1

    def test_verify_connection_returns_metadata(self) -> None:
        def handler(method, url, headers, body, timeout):
            assert method == "GET"
            assert url.endswith("/v1/connection")
            return HttpResponse(
                status=200,
                body=json.dumps(
                    {
                        "workspace": {"public_id": "ws_1", "name": "Test"},
                        "api_key": {
                            "public_id": "key_1",
                            "name": "Default",
                            "prefix": "trgv_testkey1",
                        },
                    }
                ),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        result = client.verify_connection()
        assert result.workspace.name == "Test"

    def test_send_event_exposes_request_id(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={"x-request-id": "req_abc123"},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        result = client.send_event({"channel": "general", "title": "Hello"})
        assert result.request_id == "req_abc123"

    def test_send_event_request_id_is_none_when_header_missing(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        result = client.send_event({"channel": "general", "title": "Hello"})
        assert result.request_id is None

    def test_verify_connection_exposes_request_id(self) -> None:
        body = json.dumps(
            {
                "workspace": {"public_id": "ws_1", "name": "Test"},
                "api_key": {"public_id": "key_1", "name": "Default", "prefix": "trgv_testkey1"},
            }
        )

        def with_header(method, url, headers, payload, timeout):
            return HttpResponse(status=200, body=body, headers={"x-request-id": "req_conn1"})

        def without_header(method, url, headers, payload, timeout):
            return HttpResponse(status=200, body=body, headers={})

        present = Trigv(api_key=API_KEY, transport=make_transport(with_header), max_retries=0)
        absent = Trigv(api_key=API_KEY, transport=make_transport(without_header), max_retries=0)
        assert present.verify_connection().request_id == "req_conn1"
        assert absent.verify_connection().request_id is None

    def test_does_not_expose_api_key_in_error_messages(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=401,
                body=json.dumps({"message": "Unauthorized"}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        with pytest.raises(AuthenticationError) as exc_info:
            client.send_event({"channel": "general", "title": "x"})
        assert API_KEY not in str(exc_info.value)

    def test_sets_user_agent_header(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, body, timeout):
            captured["headers"] = headers
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        client.send_event({"channel": "general", "title": "x"})
        headers = captured["headers"]
        assert str(headers["User-Agent"]).startswith("trigv-python/")

    def test_rejects_negative_max_retries(self) -> None:
        with pytest.raises(ValidationError):
            Trigv(api_key=API_KEY, max_retries=-1)

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValidationError):
            Trigv(api_key=API_KEY, timeout=0)

    def test_does_not_retry_post_without_idempotency_on_503(self) -> None:
        calls = {"count": 0}

        def handler(method, url, headers, body, timeout):
            calls["count"] += 1
            return HttpResponse(
                status=503,
                body=json.dumps({"message": "Service unavailable"}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        with pytest.raises(ServiceUnavailableError):
            client.send_event({"channel": "general", "title": "x"})
        assert calls["count"] == 1

    def test_retries_burst_429_with_retry_after(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"count": 0}
        sleeps: list[float] = []

        def handler(method, url, headers, body, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                return HttpResponse(
                    status=429,
                    body=json.dumps({"message": "Too many requests for this API key."}),
                    headers={"retry-after": "2"},
                )
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        monkeypatch.setattr("trigv.client.time.sleep", lambda seconds: sleeps.append(seconds))

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        client.send_event({"channel": "general", "title": "x", "idempotency_key": "k1"})

        assert calls["count"] == 2
        assert sleeps == [2.0]

    def test_url_omitted_when_not_provided(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, body, timeout):
            captured["body"] = json.loads(body.decode("utf-8"))
            return HttpResponse(
                status=202,
                body=json.dumps({"event": SAMPLE_EVENT}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        client.send_event({"channel": "general", "title": "x"})
        assert "url" not in captured["body"]

    def test_rejects_overlength_url(self) -> None:
        client = Trigv(api_key=API_KEY, max_retries=0)
        with pytest.raises(ValidationError):
            client.send_event(
                {
                    "channel": "general",
                    "title": "x",
                    "url": "https://example.com/" + ("a" * 2040),
                }
            )


def _ok(**_kwargs):
    return HttpResponse(status=202, body=json.dumps({"event": SAMPLE_EVENT}), headers={})


class TestBaseUrl:
    def test_default_base_url(self) -> None:
        urls: list[str] = []

        def handler(method, url, headers, body, timeout):
            urls.append(url)
            return _ok()

        Trigv(api_key=API_KEY, transport=make_transport(handler)).send_event(
            {"channel": "general", "title": "x"}
        )
        assert urls == ["https://api.trigv.com/v1/events"]

    def test_old_api_base_url_still_works(self) -> None:
        urls: list[str] = []

        def handler(method, url, headers, body, timeout):
            urls.append(url)
            return _ok()

        Trigv(
            api_key=API_KEY,
            base_url="https://api.trigv.com/api/",
            transport=make_transport(handler),
        ).send_event({"channel": "general", "title": "x"})
        assert urls == ["https://api.trigv.com/api/v1/events"]

    def test_connection_path(self) -> None:
        urls: list[str] = []

        def handler(method, url, headers, body, timeout):
            urls.append(url)
            return HttpResponse(
                status=200,
                body=json.dumps(
                    {
                        "workspace": {"public_id": "01JXXXXXXXXXXXXXXXXXXXXXXX", "name": "Acme"},
                        "api_key": {
                            "public_id": "01JXXXXXXXXXXXXXXXXXXXXXXX",
                            "name": "Prod",
                            "prefix": "trgv_abcd1234",
                        },
                    }
                ),
                headers={},
            )

        Trigv(api_key=API_KEY, transport=make_transport(handler)).verify_connection()
        assert urls == ["https://api.trigv.com/v1/connection"]


class TestErrors:
    HEADERS = {"retry-after": "7", "x-request-id": "01JREQXXXXXXXXXXXXXXXXXXXX"}

    def _client(self, status: int, headers=None, max_retries: int = 0) -> Trigv:
        def handler(method, url, hdrs, body, timeout):
            return HttpResponse(
                status=status,
                body=json.dumps({"message": "nope"}),
                headers=headers if headers is not None else self.HEADERS,
            )

        return Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=max_retries)

    def test_409_conflict(self) -> None:
        with pytest.raises(ConflictError) as exc:
            self._client(409).send_event({"channel": "general", "title": "x"})
        assert exc.value.retry_after_seconds == 7.0
        assert exc.value.request_id == "01JREQXXXXXXXXXXXXXXXXXXXX"

    def test_503_unavailable(self) -> None:
        with pytest.raises(ServiceUnavailableError) as exc:
            self._client(503).send_event({"channel": "general", "title": "x"})
        assert exc.value.retry_after_seconds == 7.0

    def test_429_retry_after(self) -> None:
        with pytest.raises(RateLimitError) as exc:
            self._client(429).send_event({"channel": "general", "title": "x"})
        assert exc.value.retry_after_seconds == 7.0
        assert exc.value.request_id == "01JREQXXXXXXXXXXXXXXXXXXXX"

    def test_422_validation_error(self) -> None:
        def handler(method, url, hdrs, body, timeout):
            return HttpResponse(
                status=422,
                body=json.dumps(
                    {"message": "The channel field is required.", "errors": {"channel": ["x"]}}
                ),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        with pytest.raises(ValidationError) as exc:
            client.send_event({"channel": "general", "title": "x"})
        assert exc.value.errors == {"channel": ["x"]}

    def test_200_already_stored_is_duplicate(self) -> None:
        def handler(method, url, hdrs, body, timeout):
            return HttpResponse(
                status=200,
                body=json.dumps({"event": SAMPLE_EVENT, "message": "already stored"}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=0)
        result = client.send_event({"channel": "general", "title": "x", "idempotency_key": "k"})
        assert result.duplicate is True

    @pytest.mark.parametrize("status", [409, 503])
    def test_retries_with_same_key_after_retry_after(
        self, status: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bodies: list[bytes] = []
        sleeps: list[float] = []

        def handler(method, url, hdrs, body, timeout):
            bodies.append(body)
            if len(bodies) == 1:
                return HttpResponse(
                    status=status,
                    body=json.dumps({"message": "retry"}),
                    headers={"retry-after": "3"},
                )
            return _ok()

        monkeypatch.setattr("trigv.client.time.sleep", lambda s: sleeps.append(s))
        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        client.send_event({"channel": "general", "title": "x", "idempotency_key": "k1"})
        assert len(bodies) == 2 and bodies[0] == bodies[1]
        assert sleeps == [3.0]

    def test_409_not_retried_without_key(self) -> None:
        calls: list[int] = []

        def handler(method, url, hdrs, body, timeout):
            calls.append(1)
            return HttpResponse(status=409, body="{}", headers={})

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        with pytest.raises(ConflictError):
            client.send_event({"channel": "general", "title": "x"})
        assert len(calls) == 1


class TestRetryAfterCap:
    @pytest.mark.parametrize("status", [409, 429, 503])
    def test_retry_after_over_timeout_raises_without_sleeping(
        self, status: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[int] = []
        sleeps: list[float] = []

        def handler(method, url, hdrs, body, timeout):
            calls.append(1)
            return HttpResponse(
                status=status,
                body=json.dumps({"message": "slow down"}),
                headers={"retry-after": "3600"},
            )

        monkeypatch.setattr("trigv.client.time.sleep", lambda s: sleeps.append(s))
        client = Trigv(
            api_key=API_KEY, transport=make_transport(handler), max_retries=2, timeout=30
        )
        with pytest.raises((ConflictError, RateLimitError, ServiceUnavailableError)) as exc:
            client.send_event({"channel": "general", "title": "x", "idempotency_key": "k1"})
        assert exc.value.retry_after_seconds == 3600.0
        assert len(calls) == 1
        assert sleeps == []


class TestDeprecatedMembers:
    def test_retryable_property_is_true(self) -> None:
        assert RateLimitError("x").retryable is True

    def test_old_positional_order_still_works(self) -> None:
        error = RateLimitError("x", True, 7.0)
        assert error.retry_after_seconds == 7.0
        assert RateLimitError("x", False).retry_after_seconds is None

    def test_new_styles_work(self) -> None:
        assert RateLimitError("x", 5.0).retry_after_seconds == 5.0
        assert RateLimitError("x", retry_after_seconds=5.0).retry_after_seconds == 5.0
        assert RateLimitError("x", retryable=True).retry_after_seconds is None

    def test_is_monthly_limit_message_returns_false(self) -> None:
        from trigv import is_monthly_limit_message

        assert is_monthly_limit_message("Monthly event limit reached") is False
