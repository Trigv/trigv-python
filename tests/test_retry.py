"""Tests for Retry-After parsing."""

from __future__ import annotations

from email.utils import formatdate

from trigv.retry import parse_retry_after_header


class TestParseRetryAfterHeader:
    def test_parses_integer_seconds(self) -> None:
        assert parse_retry_after_header("2", now=0.0) == 2.0

    def test_rejects_invalid_values(self) -> None:
        assert parse_retry_after_header("not-a-number", now=0.0) is None
        assert parse_retry_after_header("-1", now=0.0) is None
        assert parse_retry_after_header("", now=0.0) is None

    def test_parses_http_date(self) -> None:
        now = 1_700_000_000.0
        retry_at = formatdate(now + 3, usegmt=True)
        wait = parse_retry_after_header(retry_at, now=now)
        assert wait is not None
        assert 2.9 <= wait <= 3.1
