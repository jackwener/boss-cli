"""Unit tests for Boss CLI commands using Click's test runner and monkeypatch."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from boss_cli.cli import cli

runner = CliRunner()


# ── CLI Basics ──────────────────────────────────────────────────────


class TestCliBasic:
    """Test CLI basics without requiring cookies or network."""

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0." in result.output

    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "BOSS 直聘" in result.output

    def test_all_commands_registered(self):
        result = runner.invoke(cli, ["--help"])
        expected = [
            "login", "status", "logout", "me",
            "search", "recommend", "cities", "detail", "show", "export", "history",
            "applied", "interviews",
            "chat", "greet", "batch-greet",
            "messages", "unread", "reply", "chat-history",
            "send-resume", "request-phone", "request-wechat", "accept",
        ]
        for cmd in expected:
            assert cmd in result.output, f"Command '{cmd}' not found in CLI help"


class TestCommandHelp:
    """Verify every command has --help without errors."""

    @pytest.mark.parametrize("cmd", [
        "login", "logout", "status", "me",
        "search", "recommend", "cities", "detail", "show", "export", "history",
        "applied", "interviews",
        "chat", "greet", "batch-greet",
        "messages", "unread", "reply", "chat-history", "accept",
        "send-resume", "request-phone", "request-wechat",
    ])
    def test_help(self, cmd: str):
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"

    def test_search_has_filter_options(self):
        result = runner.invoke(cli, ["search", "--help"])
        assert "--city" in result.output
        assert "--salary" in result.output
        assert "--exp" in result.output
        assert "--degree" in result.output

    def test_me_has_output_options(self):
        result = runner.invoke(cli, ["me", "--help"])
        assert "--json" in result.output
        assert "--yaml" in result.output

    def test_batch_greet_has_options(self):
        result = runner.invoke(cli, ["batch-greet", "--help"])
        assert "--dry-run" in result.output
        assert "--count" in result.output or "-n" in result.output
        assert "--yes" in result.output or "-y" in result.output

    def test_greet_has_output_options(self):
        result = runner.invoke(cli, ["greet", "--help"])
        assert "--json" in result.output
        assert "--yaml" in result.output

    def test_login_has_cookie_source(self):
        result = runner.invoke(cli, ["login", "--help"])
        assert "--cookie-source" in result.output
        assert "--qrcode" in result.output

    def test_history_has_options(self):
        result = runner.invoke(cli, ["history", "--help"])
        assert "--page" in result.output or "-p" in result.output
        assert "--json" in result.output

    def test_chat_history_has_options(self):
        result = runner.invoke(cli, ["chat-history", "--help"])
        assert "-n" in result.output or "--count" in result.output
        assert "--json" in result.output


# ── Auth commands (mocked) ──────────────────────────────────────────


class TestAuthCommands:
    """Test auth commands with mocked credentials."""

    def test_status_without_auth(self):
        with patch("boss_cli.auth.get_credential", return_value=None):
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            assert "未登录" in result.output

    def test_status_yaml_without_auth(self):
        with patch("boss_cli.auth.get_credential", return_value=None):
            result = runner.invoke(cli, ["status", "--yaml"])
            assert result.exit_code == 0
            try:
                import yaml

                data = yaml.safe_load(result.output)
            except ImportError:
                data = json.loads(result.output)
            assert data["authenticated"] is False
            assert data["credential_present"] is False

    def test_status_with_auth(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}
        with patch("boss_cli.auth.get_credential", return_value=mock_cred), \
             patch("boss_cli.auth.verify_credential_details", return_value={
                 "authenticated": True,
                 "search_authenticated": True,
                 "recommend_authenticated": True,
             }):
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            assert "已登录" in result.output

    def test_status_json(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}
        with patch("boss_cli.auth.get_credential", return_value=mock_cred), \
             patch("boss_cli.auth.verify_credential_details", return_value={
                 "authenticated": True,
                 "search_authenticated": True,
                 "recommend_authenticated": True,
             }):
            result = runner.invoke(cli, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["authenticated"] is True
            assert data["credential_present"] is True
            assert data["search_authenticated"] is True
            assert data["recommend_authenticated"] is True

    def test_status_with_invalid_saved_auth(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"wt2": "1", "wbg": "2", "zp_at": "3"}
        with patch("boss_cli.auth.get_credential", return_value=mock_cred), \
             patch("boss_cli.auth.verify_credential_details", return_value={
                 "authenticated": False,
                 "search_authenticated": False,
                 "recommend_authenticated": False,
                 "reason": "缺少关键 Cookie: __zp_stoken__",
             }):
            result = runner.invoke(cli, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["authenticated"] is False
            assert data["credential_present"] is True
            assert "__zp_stoken__" in data["reason"]

    def test_status_with_partial_health(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}
        with patch("boss_cli.auth.get_credential", return_value=mock_cred), \
             patch("boss_cli.auth.verify_credential_details", return_value={
                 "authenticated": True,
                 "search_authenticated": True,
                 "recommend_authenticated": False,
                 "reason": "recommend: 环境异常 (__zp_stoken__ 已过期)。请重新登录: boss logout && boss login",
             }):
            result = runner.invoke(cli, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["authenticated"] is True
            assert data["search_authenticated"] is True
            assert data["recommend_authenticated"] is False

    def test_me_without_auth(self):
        with patch("boss_cli.commands._common.get_credential", return_value=None):
            result = runner.invoke(cli, ["me"])
            assert result.exit_code == 1
            assert "未登录" in result.output

    def test_logout(self):
        with patch("boss_cli.auth.clear_credential"):
            result = runner.invoke(cli, ["logout"])
            assert result.exit_code == 0
            assert "已退出" in result.output


# ── Personal commands (mocked) ──────────────────────────────────────


class TestPersonalCommands:
    """Test personal center commands with mocked client."""

    def test_me_render(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"wt2": "x"}

        mock_data = {
            "name": "张三", "gender": 1, "age": "25岁",
            "degreeCategory": "本科", "account": "138****1234",
        }

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.get_resume_baseinfo.return_value = mock_data
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, ["me"])
            assert result.exit_code == 0
            # CliRunner is non-TTY so auto-outputs JSON
            assert "张三" in result.output

    def test_me_json(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"wt2": "x"}

        mock_data = {"name": "张三", "gender": 1, "age": "25岁"}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.get_resume_baseinfo.return_value = mock_data
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, ["me", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["data"]["name"] == "张三"

    def test_applied_without_auth(self):
        with patch("boss_cli.commands._common.get_credential", return_value=None):
            result = runner.invoke(cli, ["applied"])
            assert result.exit_code == 1

    def test_interviews_without_auth(self):
        with patch("boss_cli.commands._common.get_credential", return_value=None):
            result = runner.invoke(cli, ["interviews"])
            assert result.exit_code == 1


# ── Cities ──────────────────────────────────────────────────────────


class TestCities:
    """Test cities command output."""

    def test_cities_output(self):
        result = runner.invoke(cli, ["cities"])
        assert result.exit_code == 0
        assert "北京" in result.output
        assert "上海" in result.output
        assert "杭州" in result.output
        assert "101010100" in result.output


# ── City resolution logic ───────────────────────────────────────────


class TestCityResolution:
    """Test city name to code resolution."""

    def test_resolve_known_city(self):
        from boss_cli.client import resolve_city
        assert resolve_city("北京") == "101010100"
        assert resolve_city("上海") == "101020100"
        assert resolve_city("杭州") == "101210100"

    def test_resolve_unknown_city_returns_nationwide(self):
        from boss_cli.client import resolve_city
        assert resolve_city("不存在的城市") == "100010000"

    def test_resolve_code_passthrough(self):
        from boss_cli.client import resolve_city
        assert resolve_city("101010100") == "101010100"

    def test_list_cities(self):
        from boss_cli.client import list_cities
        cities = list_cities()
        assert len(cities) > 30
        assert "北京" in cities
        assert "杭州" in cities


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    """Test constants are properly defined."""

    def test_salary_codes(self):
        from boss_cli.constants import SALARY_CODES
        assert len(SALARY_CODES) >= 8
        assert "20-30K" in SALARY_CODES

    def test_exp_codes(self):
        from boss_cli.constants import EXP_CODES
        assert len(EXP_CODES) >= 7
        assert "3-5年" in EXP_CODES

    def test_degree_codes(self):
        from boss_cli.constants import DEGREE_CODES
        assert len(DEGREE_CODES) >= 5
        assert "本科" in DEGREE_CODES

    def test_api_urls_defined(self):
        from boss_cli import constants
        assert constants.JOB_SEARCH_URL
        assert constants.JOB_DETAIL_URL
        assert constants.DELIVER_LIST_URL
        assert constants.INTERVIEW_DATA_URL
        assert constants.FRIEND_LIST_URL
        assert constants.USER_INFO_URL
        assert constants.RESUME_BASEINFO_URL


# ── Credential ──────────────────────────────────────────────────────


class TestCredential:
    """Test credential management."""

    def test_credential_creation(self):
        from boss_cli.auth import Credential
        cred = Credential(cookies={"foo": "bar", "baz": "qux"})
        assert cred.is_valid
        assert cred.cookies == {"foo": "bar", "baz": "qux"}
        assert cred.has_required_cookies is False
        assert "__zp_stoken__" in cred.missing_required_cookies

    def test_credential_empty(self):
        from boss_cli.auth import Credential
        cred = Credential(cookies={})
        assert not cred.is_valid

    def test_credential_serialization(self):
        from boss_cli.auth import Credential
        cred = Credential(cookies={"a": "1"})
        data = cred.to_dict()
        assert "cookies" in data
        assert "saved_at" in data

        cred2 = Credential.from_dict(data)
        assert cred2.cookies == cred.cookies

    def test_cookie_header(self):
        from boss_cli.auth import Credential
        cred = Credential(cookies={"a": "1", "b": "2"})
        header = cred.as_cookie_header()
        assert "a=1" in header
        assert "b=2" in header


# ── Exceptions ──────────────────────────────────────────────────────


class TestExceptions:
    """Test custom exception hierarchy."""

    def test_boss_api_error(self):
        from boss_cli.exceptions import BossApiError
        err = BossApiError("test error", code=42, response={"a": 1})
        assert err.code == 42
        assert err.response == {"a": 1}
        assert "test error" in str(err)

    def test_session_expired_error(self):
        from boss_cli.exceptions import SessionExpiredError
        err = SessionExpiredError()
        assert err.code == 37
        assert "stoken" in str(err)

    def test_auth_required_error(self):
        from boss_cli.exceptions import AuthRequiredError
        err = AuthRequiredError()
        assert "登录" in str(err)

    def test_rate_limit_error(self):
        from boss_cli.exceptions import RateLimitError
        err = RateLimitError()
        assert "频繁" in str(err)

    def test_param_error(self):
        from boss_cli.exceptions import ParamError
        err = ParamError("missing field", code=17)
        assert err.code == 17

    def test_error_code_mapping(self):
        from boss_cli.exceptions import (
            AuthRequiredError,
            BossApiError,
            RateLimitError,
            SessionExpiredError,
            error_code_for_exception,
        )
        assert error_code_for_exception(SessionExpiredError()) == "not_authenticated"
        assert error_code_for_exception(AuthRequiredError()) == "not_authenticated"
        assert error_code_for_exception(RateLimitError()) == "rate_limited"
        assert error_code_for_exception(BossApiError("test")) == "api_error"
        assert error_code_for_exception(ValueError("test")) == "unknown_error"


# ── Client ──────────────────────────────────────────────────────────


class TestClient:
    """Test client initialization and helpers."""

    def test_client_context_manager(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={"test": "value"})
        with BossClient(cred) as client:
            assert client.client is not None
            assert client._request_count == 0

    def test_client_not_initialized_error(self):
        from boss_cli.client import BossClient
        client = BossClient()
        with pytest.raises(RuntimeError, match="Client not initialized"):
            _ = client.client

    def test_handle_response_success(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={})
        with BossClient(cred) as client:
            data = {"code": 0, "zpData": {"key": "value"}}
            result = client._handle_response(data, "test")
            assert result == {"key": "value"}

    def test_handle_response_session_expired(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient
        from boss_cli.exceptions import SessionExpiredError

        cred = Credential(cookies={})
        with BossClient(cred) as client:
            data = {"code": 37, "message": "env error"}
            with pytest.raises(SessionExpiredError):
                client._handle_response(data, "test")

    def test_handle_response_param_error(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient
        from boss_cli.exceptions import ParamError

        cred = Credential(cookies={})
        with BossClient(cred) as client:
            data = {"code": 17, "message": "missing param"}
            with pytest.raises(ParamError):
                client._handle_response(data, "test")

    def test_handle_response_generic_error(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient
        from boss_cli.exceptions import BossApiError

        cred = Credential(cookies={})
        with BossClient(cred) as client:
            data = {"code": 999, "message": "unknown"}
            with pytest.raises(BossApiError):
                client._handle_response(data, "test")

    def test_search_request_uses_search_referer(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        with BossClient(cred) as client:
            headers = client._headers_for_request("/wapi/zpgeek/search/joblist.json", params={"query": "Python"})
            assert headers["Referer"].endswith("/web/geek/job?query=Python")

    def test_search_chinese_keyword_encoded_in_referer(self):
        """Verify Chinese keywords are percent-encoded in Referer to avoid ASCII errors."""
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        with BossClient(cred) as client:
            headers = client._headers_for_request("/wapi/zpgeek/search/joblist.json", params={"query": "前端开发"})
            referer = headers["Referer"]
            # Must not contain raw Chinese characters
            assert "前端开发" not in referer
            # Must contain percent-encoded form
            assert "query=%E5%89%8D%E7%AB%AF%E5%BC%80%E5%8F%91" in referer

    def test_recommend_request_uses_recommend_referer(self):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        with BossClient(cred) as client:
            headers = client._headers_for_request("/wapi/zprelation/interaction/geekGetJob", params={"tag": 5})
            assert headers["Referer"].endswith("/web/geek/recommend")

    def test_burst_penalty_kicks_in_after_multiple_requests(self, monkeypatch):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        with BossClient(cred) as client:
            now = 1000.0
            client._recent_request_times.extend([now - 12, now - 8, now - 3])
            monkeypatch.setattr("boss_cli.client.time.time", lambda: now)
            delay = client._burst_penalty_delay()
            assert delay >= 1.2

    def test_get_recommend_jobs_normalizes_card_list(self, monkeypatch):
        from boss_cli.auth import Credential
        from boss_cli.client import BossClient

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        with BossClient(cred) as client:
            monkeypatch.setattr(
                client,
                "_get",
                lambda url, params=None, action="": {
                    "cardList": [{"jobName": "Java", "securityId": "abc"}],
                    "hasMore": True,
                    "totalCount": 1,
                    "page": 1,
                    "startIndex": 0,
                },
            )
            data = client.get_recommend_jobs(page=1)
            assert data["jobList"][0]["jobName"] == "Java"
            assert data["hasMore"] is True


class TestAuthHealthVerification:
    """Test auth health caching and refresh behavior."""

    def test_verify_credential_details_uses_ttl_cache(self, monkeypatch):
        from boss_cli.auth import Credential, _AUTH_HEALTH_CACHE, verify_credential_details

        calls = {"count": 0}

        class FakeClient:
            def __init__(self, credential, request_delay=0.2):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def search_jobs(self, **kwargs):
                calls["count"] += 1
                return {"jobList": []}

            def get_recommend_jobs(self, page=1):
                calls["count"] += 1
                return {"jobList": []}

        _AUTH_HEALTH_CACHE.clear()
        monkeypatch.setattr("boss_cli.client.BossClient", FakeClient)

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        first = verify_credential_details(cred)
        second = verify_credential_details(cred)

        assert first["authenticated"] is True
        assert second["recommend_authenticated"] is True
        assert calls["count"] == 2
        assert len(_AUTH_HEALTH_CACHE) == 1

    def test_verify_credential_force_refresh_bypasses_cache(self, monkeypatch):
        from boss_cli.auth import Credential, _AUTH_HEALTH_CACHE, verify_credential_details

        calls = {"count": 0}

        class FakeClient:
            def __init__(self, credential, request_delay=0.2):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def search_jobs(self, **kwargs):
                calls["count"] += 1
                return {"jobList": []}

            def get_recommend_jobs(self, page=1):
                calls["count"] += 1
                return {"jobList": []}

        _AUTH_HEALTH_CACHE.clear()
        monkeypatch.setattr("boss_cli.client.BossClient", FakeClient)

        cred = Credential(cookies={"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"})
        verify_credential_details(cred)
        verify_credential_details(cred, force_refresh=True)

        assert calls["count"] == 4


# ── Index Cache ─────────────────────────────────────────────────────


class TestIndexCache:
    """Test short-index cache system."""

    def test_save_and_get(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "index_cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        jobs = [
            {"securityId": "abc123", "jobName": "Go Dev", "brandName": "Company A"},
            {"securityId": "def456", "jobName": "Python Dev", "brandName": "Company B"},
        ]
        index_cache.save_index(jobs, source="test")

        result = index_cache.get_job_by_index(1)
        assert result is not None
        assert result["securityId"] == "abc123"
        assert result["jobName"] == "Go Dev"

        result2 = index_cache.get_job_by_index(2)
        assert result2 is not None
        assert result2["securityId"] == "def456"

    def test_get_out_of_range(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "index_cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        jobs = [{"securityId": "abc", "jobName": "Test"}]
        index_cache.save_index(jobs, source="test")
        assert index_cache.get_job_by_index(99) is None

    def test_get_no_cache(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "nonexistent.json")
        assert index_cache.get_job_by_index(1) is None

    def test_get_index_info(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "index_cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        info = index_cache.get_index_info()
        assert not info["exists"]

        jobs = [{"securityId": "x", "jobName": "T"}]
        index_cache.save_index(jobs)
        info = index_cache.get_index_info()
        assert info["exists"]
        assert info["count"] == 1

    def test_zero_and_negative_index(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "index_cache.json")
        assert index_cache.get_job_by_index(0) is None
        assert index_cache.get_job_by_index(-1) is None


# ── Show command ────────────────────────────────────────────────────


class TestShowCommand:
    """Test show command behavior without network."""

    def test_show_no_cache(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "nonexistent.json")
        result = runner.invoke(cli, ["show", "1"])
        assert result.exit_code == 0
        assert "暂无缓存" in result.output

    def test_show_out_of_range(self, tmp_path, monkeypatch):
        from boss_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "index_cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)
        index_cache.save_index([{"securityId": "x", "jobName": "T"}])
        result = runner.invoke(cli, ["show", "99"])
        assert result.exit_code == 0
        assert "超出范围" in result.output


# ── Detail / Export help ────────────────────────────────────────────


class TestNewCommandHelp:
    """Test help output for new commands."""

    def test_detail_help(self):
        result = runner.invoke(cli, ["detail", "--help"])
        assert result.exit_code == 0
        assert "securityId" in result.output
        assert "--json" in result.output

    def test_show_help(self):
        result = runner.invoke(cli, ["show", "--help"])
        assert result.exit_code == 0
        assert "编号" in result.output

    def test_export_help(self):
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "csv" in result.output
        assert "--output" in result.output

    def test_history_help(self):
        result = runner.invoke(cli, ["history", "--help"])
        assert result.exit_code == 0
        assert "浏览历史" in result.output


# ── Search mock test ────────────────────────────────────────────────


class TestSearchMock:
    """Test search command with mocked client."""

    def test_search_json(self):
        mock_cred = MagicMock()
        mock_cred.cookies = {"wt2": "x"}

        mock_data = {"jobList": [{"jobName": "Go Dev", "securityId": "abc"}], "hasMore": False}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.search_jobs.return_value = mock_data
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, ["search", "golang", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert "data" in data

    def test_search_new_filter_help(self):
        """Verify new filter options appear in search --help."""
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        for opt in ("--industry", "--scale", "--stage", "--job-type"):
            assert opt in result.output, f"{opt} missing from search --help"

    def test_search_mock_with_filters(self):
        """Verify new filter params are forwarded to client.search_jobs()."""
        mock_cred = MagicMock()
        mock_cred.cookies = {"wt2": "x"}

        mock_data = {"jobList": [{"jobName": "Eng", "securityId": "x"}], "hasMore": False}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.search_jobs.return_value = mock_data
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, [
                "search", "Python", "--json",
                "--industry", "互联网",
                "--scale", "1000-9999人",
                "--stage", "已上市",
                "--job-type", "全职",
            ])
            assert result.exit_code == 0
            # Verify the call was made with the new params
            call_kwargs = mock_instance.search_jobs.call_args
            assert call_kwargs.kwargs.get("industry") == "100020"
            assert call_kwargs.kwargs.get("scale") == "305"
            assert call_kwargs.kwargs.get("stage") == "807"
            assert call_kwargs.kwargs.get("job_type") == "1901"

    def test_export_new_filter_help(self):
        """Verify new filter options appear in export --help."""
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        for opt in ("--industry", "--scale", "--stage", "--job-type"):
            assert opt in result.output, f"{opt} missing from export --help"


# ── Constants test ──────────────────────────────────────────────────


class TestNewConstants:
    """Test that new filter code mappings are correct."""

    def test_industry_codes_present(self):
        from boss_cli.constants import INDUSTRY_CODES
        assert len(INDUSTRY_CODES) >= 10
        assert "互联网" in INDUSTRY_CODES
        assert "人工智能" in INDUSTRY_CODES

    def test_scale_codes_present(self):
        from boss_cli.constants import SCALE_CODES
        assert len(SCALE_CODES) >= 6
        assert "1000-9999人" in SCALE_CODES

    def test_stage_codes_present(self):
        from boss_cli.constants import STAGE_CODES
        assert len(STAGE_CODES) >= 8
        assert "已上市" in STAGE_CODES
        assert "A轮" in STAGE_CODES

    def test_job_type_codes_present(self):
        from boss_cli.constants import JOB_TYPE_CODES
        assert len(JOB_TYPE_CODES) >= 3
        assert "全职" in JOB_TYPE_CODES


class TestSchemaEnvelope:
    """Test that structured output uses the schema envelope."""

    def test_status_json_has_no_envelope(self):
        """status uses direct output, not envelope (for backward compat)."""
        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}
        with patch("boss_cli.auth.get_credential", return_value=mock_cred), \
             patch("boss_cli.auth.verify_credential_details", return_value={
                 "authenticated": True,
                 "search_authenticated": True,
                 "recommend_authenticated": True,
             }):
            result = runner.invoke(cli, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["authenticated"] is True

    def test_me_json_has_envelope(self):
        """me command uses handle_command, should have envelope."""
        mock_cred = MagicMock()
        mock_cred.cookies = {"wt2": "x"}

        mock_data = {"name": "张三", "gender": 1}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.get_resume_baseinfo.return_value = mock_data
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, ["me", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["schema_version"] == "1"
            assert data["data"]["name"] == "张三"


class TestCommandFailures:
    """API failures should return non-zero exit codes."""

    def test_search_session_expired_exits_nonzero(self):
        from boss_cli.exceptions import SessionExpiredError

        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient, \
             patch("boss_cli.auth.extract_browser_credential", return_value=(None, [])), \
             patch("boss_cli.auth.clear_credential") as clear_credential:
            mock_instance = MagicMock()
            mock_instance.search_jobs.side_effect = SessionExpiredError()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, ["search", "golang", "--json"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["ok"] is False
            assert data["error"]["code"] == "not_authenticated"
            clear_credential.assert_called_once()

    def test_export_failure_exits_nonzero(self):
        from boss_cli.exceptions import BossApiError

        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands.search.run_client_action", side_effect=BossApiError("boom")):
            result = runner.invoke(cli, ["export", "Python"])
            assert result.exit_code == 1
            assert "导出失败" in result.output

    def test_batch_greet_search_failure_exits_nonzero(self):
        from boss_cli.exceptions import BossApiError

        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.search_jobs.side_effect = BossApiError("boom")
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            result = runner.invoke(cli, ["batch-greet", "Python", "--dry-run"])
            assert result.exit_code == 1
            assert "搜索失败" in result.output

    def test_batch_greet_refreshes_after_session_expiry(self):
        from boss_cli.exceptions import SessionExpiredError

        mock_cred = MagicMock()
        mock_cred.cookies = {"__zp_stoken__": "s", "wt2": "1", "wbg": "2", "zp_at": "3"}
        fresh_cred = MagicMock()
        fresh_cred.cookies = {"__zp_stoken__": "fresh", "wt2": "1", "wbg": "2", "zp_at": "3"}

        initial_client = MagicMock()
        initial_client.__enter__ = MagicMock(return_value=initial_client)
        initial_client.__exit__ = MagicMock(return_value=False)
        initial_client.search_jobs.return_value = {
            "jobList": [{"jobName": "Python", "brandName": "Acme", "securityId": "sec-1", "lid": "lid-1"}]
        }
        initial_client.add_friend.side_effect = SessionExpiredError()

        refreshed_client = MagicMock()
        refreshed_client.__enter__ = MagicMock(return_value=refreshed_client)
        refreshed_client.__exit__ = MagicMock(return_value=False)
        refreshed_client.add_friend.return_value = {"success": True}

        with patch("boss_cli.commands._common.get_credential", return_value=mock_cred), \
             patch("boss_cli.commands._common.BossClient", side_effect=[initial_client, initial_client, refreshed_client]), \
             patch("boss_cli.auth.extract_browser_credential", return_value=(fresh_cred, [])), \
             patch("boss_cli.auth.clear_credential") as clear_credential:
            result = runner.invoke(cli, ["batch-greet", "Python", "-n", "1", "-y"])
            assert result.exit_code == 0
            assert "1/1" in result.output
            clear_credential.assert_not_called()


# ── Geek Chat commands (mocked) ─────────────────────────────────────


def _mock_cred():
    cred = MagicMock()
    cred.cookies = {"__zp_stoken__": "s", "wt2": "tok", "wbg": "2", "zp_at": "3"}
    return cred


def _mock_client_ctx(client_mock):
    """Return a context manager that yields the mock client."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=client_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestMessagesCommand:
    """Tests for `boss messages`."""

    def test_help(self):
        result = runner.invoke(cli, ["messages", "--help"])
        assert result.exit_code == 0
        assert "-n" in result.output or "--count" in result.output

    def test_messages_no_auth(self):
        with patch("boss_cli.commands._common.get_credential", return_value=None):
            result = runner.invoke(cli, ["messages", "--json"])
            assert result.exit_code != 0 or "not_authenticated" in result.output

    def test_messages_empty(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_friend_list.return_value = {"friendList": []}
        client.get_user_info.return_value = {"userId": 123}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["messages", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["data"]["friends"] == []

    def test_messages_with_friends(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_friend_list.return_value = {"friendList": [
            {"friendId": 111, "name": "张老板", "brandName": "ACME", "jobName": "Python工程师",
             "encryptFriendId": "enc111"},
        ]}
        client.get_user_info.return_value = {"userId": 999}
        client.get_geek_last_messages.return_value = [{
            "uid": 999,
            "lastTime": "10:00",
            "lastTS": 1000000,
            "lastMsgInfo": {"msgId": 1, "showText": "你好", "fromId": 111, "toId": 999,
                            "status": 0, "msgTime": 1000000},
        }]
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["messages", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert len(data["data"]["friends"]) == 1
            assert len(data["data"]["messages"]) == 1


class TestUnreadCommand:
    """Tests for `boss unread`."""

    def test_help(self):
        result = runner.invoke(cli, ["unread", "--help"])
        assert result.exit_code == 0

    def test_unread_no_auth(self):
        with patch("boss_cli.commands._common.get_credential", return_value=None):
            result = runner.invoke(cli, ["unread", "--json"])
            assert result.exit_code != 0 or "not_authenticated" in result.output

    def test_unread_filters_self_messages(self):
        """Messages sent by me (fromId == my_uid) should not appear in unread."""
        cred = _mock_cred()
        client = MagicMock()
        my_uid = 999
        client.get_geek_friend_list.return_value = {"friendList": [
            {"friendId": 111, "name": "张老板", "brandName": "ACME", "jobName": "工程师",
             "encryptFriendId": "enc111"},
            {"friendId": 222, "name": "李老板", "brandName": "XYZ", "jobName": "开发",
             "encryptFriendId": "enc222"},
        ]}
        client.get_user_info.return_value = {"userId": my_uid}
        client.get_geek_last_messages.return_value = [
            # from boss → unread
            {"uid": my_uid, "lastTime": "10:00", "lastTS": 2000,
             "lastMsgInfo": {"msgId": 2, "showText": "感兴趣吗", "fromId": 111, "toId": my_uid,
                             "status": 0, "msgTime": 2000}},
            # from me → NOT unread
            {"uid": my_uid, "lastTime": "09:00", "lastTS": 1000,
             "lastMsgInfo": {"msgId": 1, "showText": "好的", "fromId": my_uid, "toId": 222,
                             "status": 2, "msgTime": 1000}},
        ]
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["unread", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            unread = data["data"]["unread"]
            assert len(unread) == 1
            assert unread[0]["friend"]["friendId"] == 111


class TestExchangeCommands:
    """Tests for send-resume / request-phone / request-wechat / accept."""

    def test_send_resume_help(self):
        result = runner.invoke(cli, ["send-resume", "--help"])
        assert result.exit_code == 0
        assert "friendId" in result.output.lower() or "FRIEND_ID" in result.output

    def test_request_phone_help(self):
        result = runner.invoke(cli, ["request-phone", "--help"])
        assert result.exit_code == 0

    def test_request_wechat_help(self):
        result = runner.invoke(cli, ["request-wechat", "--help"])
        assert result.exit_code == 0

    def test_accept_help(self):
        result = runner.invoke(cli, ["accept", "--help"])
        assert result.exit_code == 0
        assert "--reject" in result.output

    def test_send_resume_success(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        client.geek_exchange_request.return_value = {"type": 3, "status": 0}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["send-resume", "111", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            client.geek_exchange_request.assert_called_once_with(111, "sec123", 3)

    def test_request_phone_success(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        client.geek_exchange_request.return_value = {"type": 1, "status": 0}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["request-phone", "111", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            client.geek_exchange_request.assert_called_once_with(111, "sec123", 1)

    def test_request_wechat_success(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        client.geek_exchange_request.return_value = {"type": 2, "status": 0}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["request-wechat", "111", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            client.geek_exchange_request.assert_called_once_with(111, "sec123", 2)

    def test_accept_resume_request(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_last_messages.return_value = [{
            "uid": 999,
            "lastMsgInfo": {"msgId": 12345, "showText": "我想要一份您的附件简历，您是否同意",
                            "fromId": 111, "toId": 999, "status": 0, "msgTime": 1000},
        }]
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        client.geek_accept_exchange.return_value = {}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["accept", "111", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            client.geek_accept_exchange.assert_called_once_with(111, 12345, "sec123")

    def test_accept_wechat_request(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_last_messages.return_value = [{
            "uid": 999,
            "lastMsgInfo": {"msgId": 99999, "showText": "我想要和您交换微信，您是否同意",
                            "fromId": 111, "toId": 999, "status": 0, "msgTime": 1000},
        }]
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        client.geek_accept_wechat.return_value = {}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["accept", "111", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            client.geek_accept_wechat.assert_called_once_with(111, 99999, "sec123")

    def test_reject_request(self):
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_last_messages.return_value = [{
            "uid": 999,
            "lastMsgInfo": {"msgId": 12345, "showText": "我想要一份您的附件简历，您是否同意",
                            "fromId": 111, "toId": 999, "status": 0, "msgTime": 1000},
        }]
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        client.geek_reject_exchange.return_value = {}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["accept", "111", "--reject", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            client.geek_reject_exchange.assert_called_once_with(111, 12345, "sec123")

    def test_accept_no_exchange_request(self):
        """Should fail if latest message is not an exchange request."""
        cred = _mock_cred()
        client = MagicMock()
        client.get_geek_last_messages.return_value = [{
            "uid": 999,
            "lastMsgInfo": {"msgId": 1, "showText": "你好，请问有时间聊聊吗",
                            "fromId": 111, "toId": 999, "status": 0, "msgTime": 1000},
        }]
        client.get_geek_boss_data.return_value = {"securityId": "sec123"}
        with patch("boss_cli.auth.get_credential", return_value=cred), \
             patch("boss_cli.commands._common.BossClient", return_value=_mock_client_ctx(client)):
            result = runner.invoke(cli, ["accept", "111", "--json"])
            assert result.exit_code != 0 or (
                json.loads(result.output)["ok"] is False
            )


class TestProtobufEncoding:
    """Tests for the hand-written Protobuf encoder in mqtt_chat.py."""

    def test_varint_single_byte(self):
        from boss_cli.mqtt_chat import _varint
        assert _varint(0) == b'\x00'
        assert _varint(1) == b'\x01'
        assert _varint(127) == b'\x7f'

    def test_varint_multibyte(self):
        from boss_cli.mqtt_chat import _varint
        assert _varint(128) == b'\x80\x01'
        assert _varint(300) == b'\xac\x02'
        assert _varint(16383) == b'\xff\x7f'
        assert _varint(16384) == b'\x80\x80\x01'

    def test_build_text_message_is_bytes(self):
        from boss_cli.mqtt_chat import build_text_message
        payload = build_text_message(111, "encA", 222, "encB", "hello")
        assert isinstance(payload, bytes)
        assert len(payload) > 0

    def test_build_text_message_starts_with_type1(self):
        from boss_cli.mqtt_chat import build_text_message, _varint
        payload = build_text_message(111, "encA", 222, "encB", "hi")
        # First field: f1 (type), varint, value=1 → tag=0x08, value=0x01
        assert payload[0] == 0x08
        assert payload[1] == 0x01

    def test_build_text_message_contains_text(self):
        from boss_cli.mqtt_chat import build_text_message
        payload = build_text_message(111, "encA", 222, "encB", "测试消息")
        assert "测试消息".encode("utf-8") in payload

    def test_build_text_message_different_uids(self):
        from boss_cli.mqtt_chat import build_text_message
        p1 = build_text_message(111, "encA", 222, "encB", "hi")
        p2 = build_text_message(333, "encC", 444, "encD", "hi")
        assert p1 != p2
