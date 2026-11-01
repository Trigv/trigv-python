# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-11-01

### Changed

- Changed: README and package metadata link to trigv.com docs

## [1.1.0] - 2026-11-01

### Changed

- Default `base_url` is now `https://api.trigv.com`; paths are `/v1/events` and `/v1/connection`. A base URL ending in `/api` keeps working.
- `public_id` values are 26 character ULIDs (no `evt_` prefix).
- Rate limit is 60 requests per minute per workspace.
- Invalid JSON bodies return 422 and map to `ValidationError`.
- `RateLimitError(message, retry_after_seconds)`. The old `(message, retryable, retry_after_seconds)` call style still works.
- A `Retry-After` longer than the client `timeout` is not waited for: the 409, 429 or 503 error is raised at once.

### Added

- `ConflictError` (409) and `ServiceUnavailableError` (503), retried with `Retry-After` when an `idempotency_key` is set.
- `request_id` on every API error (from the `X-Request-ID` header).
- `request_id` on `SendEventResult` and `ConnectionResult` (`None` if the header is missing).

### Deprecated

- `RateLimitError.retryable` (always `True`) and `is_monthly_limit_message` (always `False`) are kept for compatibility.

### Removed

- Monthly event cap handling.

## [1.0.0] - 2026-07-07

### Added

- Initial stable release of the `trigv` Python package
- Sync `Trigv` client with `send_event()` and `verify_connection()`
- Stdlib `urllib` transport (no runtime dependencies)
- Type hints, validation, typed exceptions, and retry policy
