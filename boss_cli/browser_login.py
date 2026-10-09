"""Browser-assisted login enhancement via Camoufox or CDP.

Hybrid approach:
1. Complete the QR login flow via HTTP (httpx) to obtain session cookies
   (wt2, wbg, zp_at).
2. If ``__zp_stoken__`` is missing, first try to obtain it via Chrome
   DevTools Protocol (CDP) from a running real Chrome instance.  A real
   browser session bypasses Boss Zhipin's anti-bot fingerprinting more
   reliably than a headless browser.
3. If CDP is unavailable, fall back to injecting cookies into a Camoufox
   browser and navigating to the site so that client-side JavaScript
   generates ``__zp_stoken__``.
4. Export all cookies from whichever method succeeded.

This gives us the complete cookie set that pure HTTP cannot achieve.

NOTE: Boss Zhipin uses aggressive anti-bot detection that may prevent
``__zp_stoken__`` generation even in Camoufox.  The QR login still
works without it for most APIs (recommend, chat, applied, etc.).

CDP usage
---------
Launch Chrome with the remote-debugging port enabled before running
``boss login --qrcode``::

    chrome --remote-debugging-port=9222 --user-data-dir=/tmp/boss-chrome

The CDP path requires the ``websocket-client`` package
(``pip install websocket-client``).  It is tried first and silently
skipped when the package is absent or Chrome is not running.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import time
from typing import Any

from .auth import Credential, qr_login, save_credential
from .constants import BASE_URL

logger = logging.getLogger(__name__)

# Cookie domains to export from browser
BROWSER_EXPORT_DOMAINS = (".zhipin.com", "zhipin.com", "www.zhipin.com")


class BrowserLoginUnavailable(RuntimeError):
    """Raised when the camoufox browser backend cannot be started."""


def _ensure_camoufox_ready() -> None:
    """Validate that the Camoufox package and browser binary are available."""
    try:
        import camoufox  # noqa: F401
    except ImportError as exc:
        raise BrowserLoginUnavailable(
            "camoufox 未安装。安装: pip install 'kabi-boss-cli[browser]'"
        ) from exc

    try:
        result = subprocess.run(
            [sys.executable, "-m", "camoufox", "path"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BrowserLoginUnavailable(
            "无法验证 Camoufox 浏览器安装状态。"
        ) from exc

    if result.returncode != 0 or not result.stdout.strip():
        raise BrowserLoginUnavailable(
            "Camoufox 浏览器运行时缺失。运行: python -m camoufox fetch"
        )


def _normalize_browser_cookies(raw_cookies: list[dict[str, Any]]) -> dict[str, str]:
    """Convert Playwright cookie entries into a flat dict, filtering to zhipin.com."""
    cookies: dict[str, str] = {}
    for entry in raw_cookies:
        name = entry.get("name")
        value = entry.get("value")
        domain = entry.get("domain", "")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        if not any(domain.endswith(d) for d in BROWSER_EXPORT_DOMAINS):
            continue
        cookies[name] = value
    return cookies


def _hydrate_stoken_via_cdp(
    debug_port: int = 9222,
    wait_seconds: float = 4.0,
) -> dict[str, str] | None:
    """Try to obtain ``__zp_stoken__`` from a running Chrome instance via CDP.

    Boss Zhipin's anti-bot JS generates ``__zp_stoken__`` during a real
    browser page load.  By connecting to a Chrome instance that the user
    already has open (via the Chrome DevTools Protocol), we can trigger
    that JS in a genuine browser environment — defeating fingerprint
    checks that block headless browsers like Camoufox.

    Prerequisites
    -------------
    * Chrome must be running with ``--remote-debugging-port=9222``.
    * ``websocket-client`` must be installed (``pip install websocket-client``).

    Parameters
    ----------
    debug_port:
        CDP port Chrome was started with (default: 9222).
    wait_seconds:
        How long to wait after navigation for JS to set the cookie.

    Returns
    -------
    dict[str, str] | None
        Flat dict of zhipin.com cookies (including ``__zp_stoken__``) on
        success, or ``None`` when CDP is unavailable / the token was not
        generated.
    """
    try:
        import websocket  # type: ignore[import]
    except ImportError:
        logger.debug("CDP hydration skipped: websocket-client not installed")
        return None

    try:
        import urllib.request
        with urllib.request.urlopen(
            f"http://127.0.0.1:{debug_port}/json", timeout=3
        ) as resp:
            tabs = json.loads(resp.read())
    except Exception as exc:
        logger.debug("Chrome CDP not available on port %d: %s", debug_port, exc)
        return None

    if not tabs:
        logger.debug("CDP: no open tabs found")
        return None

    ws_url = tabs[0].get("webSocketDebuggerUrl")
    if not ws_url:
        logger.debug("CDP: no webSocketDebuggerUrl in first tab")
        return None

    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1,
            "method": "Page.navigate",
            "params": {"url": f"{BASE_URL}/"},
        }))
        ws.recv()  # navigation ack

        time.sleep(wait_seconds)  # let JS generate __zp_stoken__

        ws.send(json.dumps({"id": 2, "method": "Network.getAllCookies"}))
        result = json.loads(ws.recv())
        ws.close()
    except Exception as exc:
        logger.warning("CDP WebSocket error: %s", exc)
        return None

    all_cookies = result.get("result", {}).get("cookies", [])
    cookies: dict[str, str] = {}
    for c in all_cookies:
        domain = c.get("domain", "")
        name = c.get("name")
        value = c.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        if any(domain.endswith(d) for d in BROWSER_EXPORT_DOMAINS):
            cookies[name] = value

    if "__zp_stoken__" not in cookies:
        logger.debug("CDP: connected but __zp_stoken__ not generated")
        return None

    return cookies


def _hydrate_stoken_via_browser(cookies: dict[str, str]) -> dict[str, str]:
    """Inject session cookies into a Camoufox browser and harvest __zp_stoken__.

    Boss Zhipin's client-side JS generates __zp_stoken__ on page load.
    We open a browser with the session cookies already set, visit the
    site, and let JS run.

    NOTE: This may fail if the anti-bot JS fingerprints the browser
    environment and refuses to generate the token.
    """
    from camoufox.sync_api import Camoufox

    playwright_cookies = []
    for name, value in cookies.items():
        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": ".zhipin.com",
            "path": "/",
        })

    with Camoufox(headless=True) as browser:
        context = browser.new_context()
        context.add_cookies(playwright_cookies)
        page = context.new_page()

        try:
            page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=20_000)
        except Exception:
            logger.debug("Camoufox page load did not reach networkidle")

        # Give JS time to set cookies
        try:
            page.wait_for_timeout(3000)
        except Exception:
            pass

        result = _normalize_browser_cookies(context.cookies())

    return result


def browser_qr_login(
    *,
    on_status: callable | None = None,
) -> Credential:
    """Hybrid QR login: HTTP for session + Camoufox for __zp_stoken__.

    1. Run the standard HTTP QR login flow (user scans in terminal)
    2. If __zp_stoken__ is missing, try headless Camoufox to generate it
    3. Return the credential (complete or partial)
    """
    _ensure_camoufox_ready()

    def _emit(msg: str) -> None:
        if on_status:
            on_status(msg)
        else:
            print(msg)

    # Step 1: Complete QR login via HTTP (reuse existing flow)
    cred = asyncio.run(qr_login())

    # Step 2: If __zp_stoken__ is missing, try CDP first, then Camoufox
    if "__zp_stoken__" not in cred.cookies:
        _emit("\n🔧 正在补全 __zp_stoken__...")

        # --- Attempt 1: CDP (real Chrome, best anti-bot bypass) ---
        cdp_result = _hydrate_stoken_via_cdp()
        if cdp_result is not None:
            merged = {**cred.cookies, **cdp_result}
            cred = Credential(cookies=merged)
            save_credential(cred)
            _emit("✅ __zp_stoken__ 补全成功（CDP）！所有接口可正常使用")
            return cred

        # CDP unavailable or Chrome not running — fall back to Camoufox
        _emit("   （未检测到运行中的 Chrome，尝试 Camoufox 补全...）")
        _emit("   提示：以 --remote-debugging-port=9222 启动 Chrome 可提高成功率")

        # --- Attempt 2: Camoufox headless browser ---
        try:
            enriched = _hydrate_stoken_via_browser(cred.cookies)
        except Exception as exc:
            logger.warning("Browser __zp_stoken__ hydration failed: %s", exc)
            _emit("⚠️  浏览器补全 __zp_stoken__ 失败")
            return cred

        if "__zp_stoken__" in enriched:
            merged = {**cred.cookies, **enriched}
            cred = Credential(cookies=merged)
            save_credential(cred)
            _emit("✅ __zp_stoken__ 补全成功（Camoufox）！所有接口可正常使用")
        else:
            _emit("⚠️  浏览器未能生成 __zp_stoken__（Boss 直聘反爬检测）")
            _emit("   recommend/chat/applied 等接口仍可使用，search 可能受限")
            _emit("   如需完整功能，请以 --remote-debugging-port=9222 启动 Chrome 后重试")

    return cred
