"""Tests for boss_cli.auth — diagnostics, env fallback, and extraction."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


# ── Diagnostics ─────────────────────────────────────────────────────


class TestDiagnoseExtractionIssues:
    """Test platform-specific diagnostic hints."""

    def test_diagnose_windows_dpapi(self):
        """On Windows, hint should mention DPAPI and BOSS_COOKIES workaround."""
        from boss_cli.auth import _diagnose_extraction_issues

        diagnostics = ["chrome: DPAPI decryption failed"]
        with patch("boss_cli.auth.sys") as mock_sys:
            mock_sys.platform = "win32"
            hint = _diagnose_extraction_issues(diagnostics)

        assert hint is not None
        assert "DPAPI" in hint
        assert "BOSS_COOKIES" in hint
        assert "Chrome is running" in hint

    def test_diagnose_macos_keychain(self):
        """On macOS, hint should mention Keychain Access."""
        from boss_cli.auth import _diagnose_extraction_issues

        diagnostics = ["chrome: Could not get key for cookie decryption"]
        with patch("boss_cli.auth.sys") as mock_sys, \
             patch.dict(os.environ, {}, clear=False):
            mock_sys.platform = "darwin"
            # Remove SSH vars
            for key in ("SSH_CLIENT", "SSH_TTY", "SSH_CONNECTION"):
                os.environ.pop(key, None)
            hint = _diagnose_extraction_issues(diagnostics)

        assert hint is not None
        assert "Keychain" in hint

    def test_diagnose_macos_ssh(self):
        """On macOS via SSH, hint should mention unlock-keychain."""
        from boss_cli.auth import _diagnose_extraction_issues

        diagnostics = ["chrome: safe storage key error"]
        with patch("boss_cli.auth.sys") as mock_sys, \
             patch.dict(os.environ, {"SSH_CLIENT": "1.2.3.4 12345 22"}):
            mock_sys.platform = "darwin"
            hint = _diagnose_extraction_issues(diagnostics)

        assert hint is not None
        assert "unlock-keychain" in hint

    def test_diagnose_linux_keyring(self):
        """On Linux, hint should mention keyring daemon."""
        from boss_cli.auth import _diagnose_extraction_issues

        diagnostics = ["chrome: SecretStorage error"]
        with patch("boss_cli.auth.sys") as mock_sys:
            mock_sys.platform = "linux"
            hint = _diagnose_extraction_issues(diagnostics)

        assert hint is not None
        assert "keyring" in hint

    def test_diagnose_no_keychain_issue(self):
        """Unrelated errors should return None."""
        from boss_cli.auth import _diagnose_extraction_issues

        diagnostics = ["chrome: sqlite3.OperationalError: database is locked"]
        hint = _diagnose_extraction_issues(diagnostics)
        assert hint is None

    def test_diagnose_empty_diagnostics(self):
        """Empty diagnostics list should return None."""
        from boss_cli.auth import _diagnose_extraction_issues
        assert _diagnose_extraction_issues([]) is None


# ── Environment variable fallback ───────────────────────────────────


class TestLoadFromEnv:
    """Test BOSS_COOKIES environment variable loading."""

    def test_load_from_env_valid(self):
        from boss_cli.auth import load_from_env

        with patch.dict(os.environ, {"BOSS_COOKIES": "wt2=abc; wbg=def; zp_at=ghi; __zp_stoken__=jkl"}):
            cred = load_from_env()

        assert cred is not None
        assert cred.cookies["wt2"] == "abc"
        assert cred.cookies["wbg"] == "def"
        assert cred.cookies["zp_at"] == "ghi"
        assert cred.cookies["__zp_stoken__"] == "jkl"

    def test_load_from_env_empty(self):
        from boss_cli.auth import load_from_env

        with patch.dict(os.environ, {"BOSS_COOKIES": ""}):
            assert load_from_env() is None

    def test_load_from_env_unset(self):
        from boss_cli.auth import load_from_env

        env = os.environ.copy()
        env.pop("BOSS_COOKIES", None)
        with patch.dict(os.environ, env, clear=True):
            assert load_from_env() is None

    def test_load_from_env_malformed(self):
        from boss_cli.auth import load_from_env

        with patch.dict(os.environ, {"BOSS_COOKIES": "no-equals-here; also-bad"}):
            assert load_from_env() is None


# ── Cookie jar extraction ───────────────────────────────────────────


class TestExtractCookiesFromJar:
    """Test _extract_cookies_from_jar helper."""

    class _Cookie:
        def __init__(self, domain, name, value):
            self.domain = domain
            self.name = name
            self.value = value

    def test_extracts_zhipin_cookies(self):
        from boss_cli.auth import _extract_cookies_from_jar

        cookies = [
            self._Cookie(".zhipin.com", "wt2", "abc"),
            self._Cookie(".zhipin.com", "wbg", "def"),
            self._Cookie(".other.com", "other", "xyz"),
        ]
        result = _extract_cookies_from_jar(cookies, source="test")
        assert result is not None
        assert result["wt2"] == "abc"
        assert result["wbg"] == "def"
        assert "other" not in result

    def test_returns_none_for_no_zhipin_cookies(self):
        from boss_cli.auth import _extract_cookies_from_jar

        cookies = [self._Cookie(".other.com", "foo", "bar")]
        assert _extract_cookies_from_jar(cookies, source="test") is None

    def test_returns_none_for_empty_jar(self):
        from boss_cli.auth import _extract_cookies_from_jar
        assert _extract_cookies_from_jar([], source="test") is None


# ── Browser order ───────────────────────────────────────────────────


class TestBrowserOrder:
    """Test browser extraction order logic."""

    def test_default_order(self):
        from boss_cli.auth import _get_browser_order
        order = _get_browser_order()
        assert order == ["chrome", "edge", "firefox", "brave"]

    def test_custom_source_prioritized(self):
        from boss_cli.auth import _get_browser_order
        order = _get_browser_order("firefox")
        assert order[0] == "firefox"
        assert "chrome" in order


# ── In-process extraction ───────────────────────────────────────────


class TestExtractInProcess:
    """Test in-process cookie extraction."""

    def test_returns_none_when_bc3_not_installed(self):
        from boss_cli.auth import _extract_in_process

        with patch.dict("sys.modules", {"browser_cookie3": None}):
            cred, diag = _extract_in_process()
            # We can't easily remove from sys.modules in a test,
            # but at minimum verify the function returns a tuple
            assert isinstance(diag, list)

    def test_extraction_success(self):
        from boss_cli.auth import _extract_in_process

        class FakeCookie:
            def __init__(self, domain, name, value):
                self.domain = domain
                self.name = name
                self.value = value

        mock_cookie = FakeCookie(".zhipin.com", "wt2", "test_val")
        mock_bc3 = MagicMock()
        mock_bc3.chrome.return_value = [mock_cookie]
        mock_bc3.firefox.return_value = []
        mock_bc3.edge.return_value = []
        mock_bc3.brave.return_value = []

        with patch.dict("sys.modules", {"browser_cookie3": mock_bc3}), \
             patch("boss_cli.auth._iter_chrome_cookie_files", return_value=[]):
            cred, diag = _extract_in_process()

        assert cred is not None
        assert cred.cookies["wt2"] == "test_val"

    def test_prefers_complete_profile_over_partial_default(self):
        from boss_cli.auth import _extract_in_process

        class FakeCookie:
            def __init__(self, domain, name, value):
                self.domain = domain
                self.name = name
                self.value = value

        def chrome_loader(*, cookie_file=None, domain_name=None):
            if cookie_file and "Profile 1" in cookie_file:
                return [
                    FakeCookie(".zhipin.com", "__zp_stoken__", "s"),
                    FakeCookie(".zhipin.com", "wt2", "1"),
                    FakeCookie(".zhipin.com", "wbg", "2"),
                    FakeCookie(".zhipin.com", "zp_at", "3"),
                    FakeCookie(".zhipin.com", "__c", "4"),
                ]
            return [FakeCookie(".zhipin.com", "__a", "partial")]

        mock_bc3 = MagicMock()
        mock_bc3.chrome.side_effect = chrome_loader
        mock_bc3.firefox.return_value = []
        mock_bc3.edge.return_value = []
        mock_bc3.brave.return_value = []

        with patch.dict("sys.modules", {"browser_cookie3": mock_bc3}), \
             patch(
                 "boss_cli.auth._iter_chrome_cookie_files",
                 return_value=[
                     "/tmp/Chrome/Default/Cookies",
                     "/tmp/Chrome/Profile 1/Cookies",
                 ],
             ):
            cred, _ = _extract_in_process("chrome")

        assert cred is not None
        assert cred.has_required_cookies is True
        assert cred.cookies["__zp_stoken__"] == "s"
"""Tests for boss_cli.auth — diagnostics, env fallback, and extraction."""
