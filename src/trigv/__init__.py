"""Official Trigv SDK for Python."""

from trigv.client import Trigv
from trigv.constants import (
    DEFAULT_BASE_URL,
    DELIVERY_URGENCIES,
    LEVELS,
    VERSION,
)
from trigv.errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    TrigvError,
    ValidationError,
)
from trigv.types import (
    ConnectionApiKey,
    ConnectionResult,
    ConnectionWorkspace,
    DeliveryUrgency,
    Event,
    NotificationLevel,
    SendEventParams,
    SendEventResult,
)

__all__ = [
    "ApiError",
    "AuthenticationError",
    "AuthorizationError",
    "ConnectionApiKey",
    "ConnectionResult",
    "ConnectionWorkspace",
    "DEFAULT_BASE_URL",
    "DELIVERY_URGENCIES",
    "DeliveryUrgency",
    "Event",
    "LEVELS",
    "NetworkError",
    "NotFoundError",
    "NotificationLevel",
    "RateLimitError",
    "SendEventParams",
    "SendEventResult",
    "TimeoutError",
    "Trigv",
    "TrigvError",
    "ValidationError",
    "VERSION",
]

__version__ = VERSION
