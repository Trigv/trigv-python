"""Tests for the default urllib transport against a local HTTP server."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from trigv import RateLimitError, Trigv


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = json.dumps({"message": "slow down"}).encode()
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Retry-After", "7")
        self.send_header("X-Request-ID", "01TESTREQUESTID0000000000AB")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server_url() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_default_transport_maps_http_error_headers(server_url: str) -> None:
    client = Trigv(api_key="trgv_test_key", base_url=server_url, max_retries=0)
    with pytest.raises(RateLimitError) as caught:
        client.send_event({"channel": "general", "title": "Hi"})
    assert caught.value.retry_after_seconds == 7.0
    assert caught.value.request_id == "01TESTREQUESTID0000000000AB"
