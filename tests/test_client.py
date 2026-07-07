"""Tests for the Trigv Python SDK."""

from __future__ import annotations

import json

import pytest

from trigv import Trigv
from trigv.errors import AuthenticationError, NotFoundError, RateLimitError, ValidationError
from trigv.types import HttpResponse

API_KEY = "trgv_testkey1_abcdefghijklmnopqrstuvwxyz123456"

SAMPLE_EVENT = {
    "public_id": "evt_abc",
    "event_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
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
        assert result.event.public_id == "evt_abc"

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

    def test_monthly_rate_limit_is_non_retryable(self) -> None:
        def handler(method, url, headers, body, timeout):
            return HttpResponse(
                status=429,
                body=json.dumps({"message": "Monthly event limit reached for this workspace."}),
                headers={},
            )

        client = Trigv(api_key=API_KEY, transport=make_transport(handler), max_retries=2)
        with pytest.raises(RateLimitError) as exc_info:
            client.send_event({"channel": "general", "title": "x"})
        assert exc_info.value.retryable is False

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
        assert result.event.public_id == "evt_abc"
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
