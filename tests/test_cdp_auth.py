"""CDP import boundary, fallback, and optional real-browser integration tests."""

import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import MagicMock

import httpx
import pytest

from boss_cli import auth
from boss_cli.constants import REQUIRED_COOKIES


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("BOSS_CDP_URL", raising=False)
    monkeypatch.setattr(auth, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth, "CREDENTIAL_FILE", tmp_path / "credential.json")


@pytest.fixture
def cdp(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(auth.httpx, "Client", client)
    response = client.return_value.__enter__.return_value.get.return_value
    response.json.return_value = [{"type": "page", "url": "https://www.zhipin.com/", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}]
    connect = MagicMock()
    monkeypatch.setattr(auth.websocket, "create_connection", connect)
    ws = connect.return_value
    ws.getstatus.return_value = 101
    cookies = [{"name": name, "value": "test-" + name, "domain": ".zhipin.com"} for name in REQUIRED_COOKIES]
    ws.recv.return_value = json.dumps({"id": 1, "result": {"cookies": cookies}})
    return client, response, connect, ws, cookies


def test_opt_in_only(cdp):
    assert auth._extract_via_cdp() == (None, [])
    cdp[0].assert_not_called()
    cdp[2].assert_not_called()


@pytest.mark.parametrize("url", ["http://example.com:9222", "http://192.168.1.1:9222", "file:///tmp/cdp", "http://user:pass@127.0.0.1:9222", "http://127.0.0.1:bad", "http://127.0.0.1:9222/?token=secret"])
def test_reject_endpoint_before_io(cdp, url):
    cred, diagnostics = auth._extract_via_cdp(url)
    assert cred is None and diagnostics
    cdp[0].assert_not_called()
    cdp[2].assert_not_called()


@pytest.mark.parametrize("url", ["ws://example.com/page", "ws://192.168.1.1/page", "https://127.0.0.1/page"])
def test_validate_discovered_websocket(cdp, url):
    cdp[1].json.return_value[0]["webSocketDebuggerUrl"] = url
    assert auth._extract_via_cdp("http://localhost:9222")[0] is None
    cdp[2].assert_not_called()


def test_import_filters_domains_and_ignores_events(cdp):
    client, _, connect, ws, cookies = cdp
    cookies += [{"name": "wt2", "value": "wrong", "domain": d} for d in ("evilzhipin.com", "zhipin.com.evil.test")]
    cookies += [{"name": "extra", "value": "allowed", "domain": "www.zhipin.com"}]
    ws.recv.side_effect = [json.dumps({"method": "event"}), json.dumps({"id": 1, "result": {"cookies": cookies}})]
    cred, diagnostics = auth._extract_via_cdp("http://localhost:9222")
    assert not diagnostics and cred.cookies["wt2"] == "test-wt2"
    assert cred.cookies["extra"] == "allowed"
    assert auth.load_credential().cookies == cred.cookies
    client.assert_called_once_with(trust_env=False, follow_redirects=False, timeout=3)
    client.return_value.__enter__.return_value.get.assert_called_once_with("http://127.0.0.1:9222/json/list")
    assert connect.call_args.kwargs["redirect_limit"] == 0
    assert connect.call_args.kwargs["http_no_proxy"] == ["*"]
    ws.close.assert_called_once()


@pytest.mark.parametrize("message", [{"id": 1, "error": {"message": "secret"}}, {"id": 1, "result": {"cookies": []}}, {"id": 1, "result": {"cookies": [{"name": "wt2", "value": "incomplete", "domain": ".zhipin.com"}]}}, "malformed"])
def test_failed_import_does_not_save(cdp, message):
    cdp[3].recv.return_value = json.dumps(message)
    cred, diagnostics = auth._extract_via_cdp("http://127.0.0.1:9222")
    assert cred is None and diagnostics and "secret" not in str(diagnostics)
    assert not auth.CREDENTIAL_FILE.exists()
    cdp[3].close.assert_called_once()


def test_continuous_events_have_deadline(cdp, monkeypatch):
    cdp[3].recv.return_value = json.dumps({"method": "event"})
    monkeypatch.setattr(auth.time, "monotonic", MagicMock(side_effect=[0, 1, 6]))
    cred, diagnostics = auth._extract_via_cdp("http://127.0.0.1:9222")
    assert cred is None and "TimeoutError" in diagnostics[0]
    cdp[3].close.assert_called_once()


def test_http_redirect_is_not_followed(cdp):
    cdp[1].raise_for_status.side_effect = httpx.HTTPStatusError("redirect", request=MagicMock(), response=MagicMock())
    assert auth._extract_via_cdp("http://127.0.0.1:9222")[0] is None
    cdp[2].assert_not_called()


def test_missing_page_and_websocket_redirect(cdp):
    cdp[1].json.return_value = []
    assert auth._extract_via_cdp("http://127.0.0.1:9222")[0] is None
    cdp[2].assert_not_called()
    cdp[1].json.return_value = [{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page"}]
    cdp[3].getstatus.return_value = 302
    assert auth._extract_via_cdp("http://127.0.0.1:9222")[0] is None
    cdp[3].send.assert_not_called()
    cdp[3].close.assert_called_once()


@pytest.mark.parametrize("source", [None, "firefox", "chrome"])
def test_existing_browser_fallback_and_explicit_source(monkeypatch, source):
    cdp = MagicMock(return_value=(None, ["cdp failed"]))
    monkeypatch.setattr(auth, "_extract_via_cdp", cdp)
    cred = auth.Credential({name: "test" for name in REQUIRED_COOKIES})
    local = MagicMock(return_value=(cred, []))
    monkeypatch.setattr(auth, "_extract_in_process", local)
    assert auth.extract_browser_credential(source)[0] is cred
    local.assert_called_once_with(source)
    assert cdp.call_count == (1 if source is None else 0)


def test_cdp_success_prevents_disk_extraction(monkeypatch):
    cred = auth.Credential({name: "test" for name in REQUIRED_COOKIES})
    monkeypatch.setattr(auth, "_extract_via_cdp", MagicMock(return_value=(cred, [])))
    local = MagicMock()
    monkeypatch.setattr(auth, "_extract_in_process", local)
    assert auth.extract_browser_credential() == (cred, [])
    local.assert_not_called()


def test_missing_websocket_dependency(monkeypatch):
    monkeypatch.setattr(auth, "websocket", None)
    cred, diagnostics = auth._extract_via_cdp("http://127.0.0.1:9222")
    assert cred is None and "not installed" in diagnostics[0]


def test_real_chromium_import(monkeypatch, tmp_path):
    """Run against an isolated browser with synthetic cookies, never a personal profile."""
    binary = os.environ.get("BOSS_TEST_CHROMIUM")
    if not binary:
        pytest.skip("Set BOSS_TEST_CHROMIUM to run the real-browser integration test")
    profile = tmp_path / "browser"
    process = subprocess.Popen([binary, "--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        active_port = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 15
        while not active_port.exists():
            if process.poll() is not None or time.monotonic() >= deadline:
                pytest.fail("Isolated Chromium failed to start")
            time.sleep(0.1)
        port = active_port.read_text().splitlines()[0]
        endpoint = f"http://127.0.0.1:{port}"
        with httpx.Client(trust_env=False) as client:
            target = client.get(endpoint + "/json/list").json()[0]
        ws = auth.websocket.create_connection(target["webSocketDebuggerUrl"], suppress_origin=True, http_no_proxy=["*"], timeout=5)
        try:
            cookies = [{"name": name, "value": "synthetic-" + name, "domain": ".zhipin.com", "path": "/", "secure": True} for name in REQUIRED_COOKIES]
            cookies.append({"name": "unrelated", "value": "exclude", "domain": ".example.com", "path": "/"})
            ws.send(json.dumps({"id": 42, "method": "Network.setCookies", "params": {"cookies": cookies}}))
            reply = json.loads(ws.recv())
            assert reply.get("id") == 42 and "error" not in reply
        finally:
            ws.close()
        monkeypatch.setenv("BOSS_CDP_URL", endpoint)
        cred, diagnostics = auth.extract_browser_credential()
        assert not diagnostics
        assert cred.cookies == {name: "synthetic-" + name for name in REQUIRED_COOKIES}
        assert json.loads(Path(auth.CREDENTIAL_FILE).read_text())["cookies"] == cred.cookies
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
