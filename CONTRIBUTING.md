# Contributing

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
black --check .
```

## Pull requests

1. Fork `Trigv/trigv-python` and branch from `main`
2. Add tests for behaviour changes
3. Run `pytest`, `ruff check`, and `black --check`
4. Update `CHANGELOG.md` for user-visible changes

## API contract

Match [Trigv OpenAPI](https://api.trigv.com/openapi.yaml). Do not invent ingest fields.

## Security

Never commit API keys.
