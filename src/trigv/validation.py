"""Client-side validation for event parameters."""

from __future__ import annotations

from collections.abc import Mapping

from trigv.constants import (
    DELIVERY_URGENCIES,
    FIELD_MAX_LENGTHS,
    LEVELS,
    PROHIBITED_FIELDS,
)
from trigv.errors import ValidationError
from trigv.types import SendEventParams


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _assert_max_length(field: str, value: str, maximum: int) -> None:
    if len(value) > maximum:
        message = f"{field} must be at most {maximum} characters"
        raise ValidationError(message, {field: [message]})


def _assert_enum(field: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        message = f"{field} must be one of: {', '.join(allowed)}"
        raise ValidationError(message, {field: [message]})


def validate_send_event_params(params: SendEventParams | Mapping[str, object]) -> dict[str, str]:
    """Validate and normalize send-event parameters for the JSON request body."""
    raw = dict(params)

    for prohibited in PROHIBITED_FIELDS:
        if prohibited in raw:
            raise ValidationError(
                f'Field "{prohibited}" is not allowed',
                {prohibited: [f"The {prohibited} field is prohibited"]},
            )

    channel = _trim(str(raw.get("channel", "")) if raw.get("channel") is not None else None)
    title = _trim(str(raw.get("title", "")) if raw.get("title") is not None else None)

    if not channel:
        raise ValidationError("channel is required", {"channel": ["channel is required"]})
    if not title:
        raise ValidationError("title is required", {"title": ["title is required"]})

    _assert_max_length("channel", channel, FIELD_MAX_LENGTHS["channel"])
    _assert_max_length("title", title, FIELD_MAX_LENGTHS["title"])

    body: dict[str, str] = {"channel": channel, "title": title}

    description = _trim(str(raw["description"]) if raw.get("description") is not None else None)
    if description is not None:
        _assert_max_length("description", description, FIELD_MAX_LENGTHS["description"])
        body["description"] = description

    image_url = _trim(str(raw["image_url"]) if raw.get("image_url") is not None else None)
    if image_url is not None:
        _assert_max_length("image_url", image_url, FIELD_MAX_LENGTHS["image_url"])
        body["image_url"] = image_url

    level = _trim(str(raw["level"]) if raw.get("level") is not None else None)
    if level is not None:
        _assert_enum("level", level, LEVELS)
        body["level"] = level

    delivery_urgency = _trim(
        str(raw["delivery_urgency"]) if raw.get("delivery_urgency") is not None else None
    )
    if delivery_urgency is not None:
        _assert_enum("delivery_urgency", delivery_urgency, DELIVERY_URGENCIES)
        body["delivery_urgency"] = delivery_urgency

    event_type = _trim(str(raw["event_type"]) if raw.get("event_type") is not None else None)
    if event_type is not None:
        _assert_max_length("event_type", event_type, FIELD_MAX_LENGTHS["event_type"])
        body["event_type"] = event_type

    idempotency_key = _trim(
        str(raw["idempotency_key"]) if raw.get("idempotency_key") is not None else None
    )
    if idempotency_key is not None:
        _assert_max_length("idempotency_key", idempotency_key, FIELD_MAX_LENGTHS["idempotency_key"])
        body["idempotency_key"] = idempotency_key

    return body
