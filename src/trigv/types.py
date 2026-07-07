"""Type definitions for the Trigv Python SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

NotificationLevel = Literal["info", "success", "warning", "error"]
DeliveryUrgency = Literal["standard", "time_sensitive"]


class SendEventParams(TypedDict, total=False):
    """Parameters for :meth:`Trigv.send_event`."""

    channel: str
    title: str
    description: str
    image_url: str
    level: NotificationLevel
    delivery_urgency: DeliveryUrgency
    event_type: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class Event:
    """Event metadata returned by the ingest API."""

    public_id: str
    event_uuid: str
    status: str
    level: str
    event_type: str | None
    target_device_count: int
    received_at: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Event:
        return cls(
            public_id=str(data["public_id"]),
            event_uuid=str(data["event_uuid"]),
            status=str(data["status"]),
            level=str(data["level"]),
            event_type=data.get("event_type") if data.get("event_type") is not None else None,
            target_device_count=int(data["target_device_count"]),  # type: ignore[arg-type]
            received_at=str(data["received_at"]),
        )


@dataclass(frozen=True, slots=True)
class SendEventResult:
    """Result of a successful event ingest."""

    event: Event
    duplicate: bool


@dataclass(frozen=True, slots=True)
class ConnectionWorkspace:
    public_id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ConnectionWorkspace:
        return cls(public_id=str(data["public_id"]), name=str(data["name"]))


@dataclass(frozen=True, slots=True)
class ConnectionApiKey:
    public_id: str
    name: str
    prefix: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ConnectionApiKey:
        return cls(
            public_id=str(data["public_id"]),
            name=str(data["name"]),
            prefix=str(data["prefix"]),
        )


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    workspace: ConnectionWorkspace
    api_key: ConnectionApiKey


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """HTTP response returned by the transport layer."""

    status: int
    body: str
    headers: dict[str, str]
