"""Retry helpers for Trigv HTTP clients."""

from __future__ import annotations

import time
from datetime import timezone
from email.utils import parsedate_to_datetime


def parse_retry_after_header(value: str | None, now: float | None = None) -> float | None:
    """Parse Retry-After (integer seconds or HTTP-date). Returns wait seconds when valid."""
    if not value or not value.strip():
        return None

    trimmed = value.strip()

    # Only ASCII digits count: str.isdigit() also accepts characters such as "²" that int() rejects.
    if trimmed.isascii() and trimmed.isdigit():
        try:
            return float(int(trimmed))
        except OverflowError:
            return float("inf")
        except ValueError:
            # Digit string longer than Python's int conversion limit: nonsense, ignore it.
            return None

    try:
        retry_at = parsedate_to_datetime(trimmed)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current = time.time() if now is None else now
        wait = retry_at.timestamp() - current
        if wait < 0:
            return None
        return wait
    except (TypeError, ValueError, OverflowError):
        return None
