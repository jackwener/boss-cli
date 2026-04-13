"""Local cookie bridge server for boss-cli."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .auth import Credential, load_from_cookie_string, save_credential

logger = logging.getLogger(__name__)


def _cookie_dict_from_payload(payload: Any) -> dict[str, str]:
    if isinstance(payload, dict):
        cookies = payload.get("cookies")
        if isinstance(cookies, dict):
            return {str(k): str(v) for k, v in cookies.items() if v}
        cookie_str = payload.get("cookie")
        if isinstance(cookie_str, str):
            cred = load_from_cookie_string(cookie_str)
            return cred.cookies if cred else {}
    return {}


class _CookieHandler(BaseHTTPRequestHandler):
    server_version = "boss-cli-cookie-bridge/0.1"
    auth_token: str | None = None

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Boss-Cookie-Token")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        self._send_json(HTTPStatus.NO_CONTENT, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        if path in ("", "/health", "/status"):
            self._send_json(HTTPStatus.OK, {"ok": True, "service": "boss-cli-cookie-bridge"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        if path not in ("", "/cookies", "/ingest"):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        if self.auth_token:
            token = self.headers.get("X-Boss-Cookie-Token", "")
            if token != self.auth_token:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return

        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8", "ignore")

        payload: Any = None
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw

        cookies: dict[str, str] = {}
        if isinstance(payload, str):
            cred = load_from_cookie_string(payload)
            cookies = cred.cookies if cred else {}
        else:
            cookies = _cookie_dict_from_payload(payload)

        if not cookies:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "no_cookies"})
            return

        cred = Credential(cookies=cookies)
        save_credential(cred)
        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "cookie_count": len(cookies)},
        )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.info("%s - %s", self.address_string(), format % args)


def run_cookie_server(host: str = "127.0.0.1", port: int = 9876, token: str | None = None) -> None:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("Cookie bridge只允许绑定到本地回环地址（127.0.0.1/localhost/::1）")
    _CookieHandler.auth_token = token
    server = ThreadingHTTPServer((host, port), _CookieHandler)
    logger.warning("Cookie bridge listening on http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Cookie bridge shutdown requested")
    finally:
        server.server_close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    run_cookie_server()


if __name__ == "__main__":
    main()
