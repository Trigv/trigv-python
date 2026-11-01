# Trigv Python SDK

Official Python client for the [Trigv](https://trigv.com) workspace ingest API. Send push notification events from scripts, cron jobs, CI pipelines, and backend services.

## Installation

```bash
pip install trigv
```

Requires Python 3.10 or newer. No runtime dependencies beyond the standard library.

## Quick start

```python
from trigv import Trigv

trigv = Trigv()

result = trigv.send_event(
    {
        "channel": "general",
        "title": "Hello from Python",
    }
)

print(result.event.public_id)
```

## Authentication

Create a workspace ingest API key in the Trigv dashboard. Keys look like `trgv_a1b2c3d4_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.

Pass the key when constructing the client, or set the `TRIGV_API_KEY` environment variable:

```python
from trigv import Trigv

trigv = Trigv(api_key="trgv_your_api_key")
```

Never commit API keys to source control. The SDK does not include your key in error messages or logs.

## Sending an event

```python
result = trigv.send_event(
    {
        "channel": "deploys",
        "title": "Production deploy complete",
        "description": "Build #42 succeeded in 38s (commit abc1234)",
        "level": "success",
        "event_type": "deploy.completed",
    }
)

print(result.event.public_id, result.event.status)
```

`send_event()` returns a `SendEventResult` with:

- `event` — server metadata (`public_id`, `status`, `target_device_count`, etc.)
- `duplicate` — `True` when the same `idempotency_key` was already accepted (HTTP 200)

Title, description, and image URL are delivered to devices but are **not** stored server-side.

## Event options

| Field | Required | Description |
|-------|:--------:|-------------|
| `channel` | Yes | Channel slug (e.g. `general`, `deploys`; max 120 characters) |
| `title` | Yes | Notification title (max 255 characters) |
| `description` | No | Body text (max 1000 characters) |
| `image_url` | No | Image URL (max 2048 characters) |
| `url` | No | Destination URL for the notification (max 2048 characters; not stored server-side) |
| `level` | No | `info`, `success`, `warning`, or `error` (default: `info`) |
| `delivery_urgency` | No | `standard` or `time_sensitive` (default: `standard`) |
| `event_type` | No | Free-form label (e.g. `deploy.completed`; max 120 characters) |
| `idempotency_key` | No | Dedup key per workspace (max 190 characters) |

Prohibited fields: `api_key` (use the `Authorization` header), `icon`.

## Levels

| Level | Use case |
|-------|----------|
| `info` | General updates (default) |
| `success` | Completed jobs, successful deploys |
| `warning` | Degraded service, retries |
| `error` | Failures requiring attention |

## Delivery urgency

| Value | Behaviour |
|-------|-----------|
| `standard` | Normal delivery (default) |
| `time_sensitive` | iOS time-sensitive interruption level |

## Idempotency

Set `idempotency_key` to safely retry delivery without creating duplicate events or billing twice:

```python
result = trigv.send_event(
    {
        "channel": "deploys",
        "title": "Production deploy complete",
        "idempotency_key": "deploy-prod-42",
    }
)

if result.duplicate:
    print("Already sent:", result.event.public_id)
```

- First request with a key → HTTP 202, `duplicate=False`, usage billed
- Retry with the same key → HTTP 200 (`already stored`), `duplicate=True`, no additional usage
- 409 (another request is delivering the key) and 503 (push unavailable) are retried automatically with the same key, honouring `Retry-After`

If `Retry-After` is longer than the client `timeout`, the SDK does not wait: it raises the 409, 429 or 503 error at once. 502 and 504 responses, network errors and timeouts are also retried (with an `idempotency_key`), and so is `verify_connection()`.

Without an `idempotency_key`, the SDK does not auto-retry `send_event()` on ambiguous failures.

## Error handling

```python
from trigv import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    Trigv,
    ValidationError,
)

trigv = Trigv()

try:
    trigv.send_event({"channel": "general", "title": "Hello"})
except ValidationError as exc:
    print(exc.errors)
except AuthenticationError:
    print("Check your API key")
except NotFoundError:
    print("Channel does not exist")
except (RateLimitError, ConflictError, ServiceUnavailableError) as exc:
    print(f"Retry in {exc.retry_after_seconds}s (request id {exc.request_id})")
```

| Exception | When |
|-----------|------|
| `ValidationError` | Client-side validation or HTTP 422 |
| `AuthenticationError` | HTTP 401 |
| `AuthorizationError` | HTTP 403 |
| `NotFoundError` | HTTP 404 (e.g. unknown channel) |
| `ConflictError` | HTTP 409 (same `idempotency_key` is being delivered); has `retry_after_seconds` |
| `RateLimitError` | HTTP 429, 60 requests per minute per workspace; has `retry_after_seconds` |
| `ServiceUnavailableError` | HTTP 503 (push unavailable); has `retry_after_seconds` |
| `ApiError` | Other HTTP errors |

Every API error has `request_id`, the `X-Request-ID` response header. Quote it to support.

| `NetworkError` | Connection failure |
| `TimeoutError` | Request timeout |

## Configuration

```python
trigv = Trigv(
    api_key="trgv_your_api_key",
    base_url="https://api.trigv.com",      # default; a URL ending in /api still works
    timeout=30.0,                          # seconds
    max_retries=2,                         # retryable errors only
)
```

The older `/api` prefix is kept for good: `base_url="https://api.trigv.com/api"` calls `/api/v1/events`.

### Verify connection

Check that your API key is valid without sending an event or consuming usage:

```python
connection = trigv.verify_connection()
print(connection.workspace.name)
print(connection.api_key.prefix)
```

## Examples

See the [`examples/`](examples/) directory:

- [`basic.py`](examples/basic.py) — minimal event
- [`deploy-completed.py`](examples/deploy-completed.py) — canonical deploy notification
- [`cron-failed.py`](examples/cron-failed.py) — scheduled job failure
- [`idempotency.py`](examples/idempotency.py) — safe retries with idempotency keys

## Development

```bash
git clone https://github.com/Trigv/trigv-python.git
cd trigv-python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or with PEP 735 dependency groups:

```bash
pip install pytest ruff black hatchling
pip install -e .
```

## Testing

```bash
pytest
ruff check src tests examples
black --check src tests examples
```

Tests use a mocked HTTP transport — no live API key required.

## Contributing

Contributions are welcome. Please open an issue or pull request on [GitHub](https://github.com/Trigv/trigv-python).

## Licence

MIT — see [LICENSE](LICENSE).
