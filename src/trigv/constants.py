"""Shared constants for the Trigv Python SDK."""

VERSION = "1.1.0"

DEFAULT_BASE_URL = "https://api.trigv.com"

DEFAULT_TIMEOUT_SECONDS = 30.0

MAX_RETRIES = 2

LEVELS = ("info", "success", "warning", "error")

DELIVERY_URGENCIES = ("standard", "time_sensitive")

FIELD_MAX_LENGTHS = {
    "channel": 120,
    "title": 255,
    "description": 1000,
    "image_url": 2048,
    "url": 2048,
    "event_type": 120,
    "idempotency_key": 190,
}

PROHIBITED_FIELDS = ("api_key", "icon")
