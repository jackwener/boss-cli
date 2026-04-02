"""API client for Boss Zhipin with rate limiting, retry, and anti-detection."""

from __future__ import annotations

import logging
import random
import time
import urllib.parse
from collections import deque
from typing import Any

import httpx

from .constants import (
    BASE_URL,
    BOSS_CHAT_GEEK_INFO_URL,
    BOSS_CHATTED_JOB_LIST_URL,
    BOSS_EXCHANGE_CONTENT_URL,
    BOSS_EXCHANGE_REQUEST_URL,
    BOSS_FRIEND_DETAIL_URL,
    BOSS_FRIEND_LABELS_URL,
    BOSS_FRIEND_LIST_URL,
    BOSS_FRIEND_NOTE_URL,
    BOSS_GREET_REC_SORT_URL,
    BOSS_GREET_SORT_LIST_URL,
    BOSS_HISTORY_MSG_URL,
    BOSS_INTERVIEW_INVITE_URL,
    BOSS_INTERVIEW_LIST_URL,
    BOSS_JOB_OFFLINE_URL,
    BOSS_JOB_ONLINE_URL,
    BOSS_LAST_MSG_URL,
    BOSS_REMOVE_FILTER_URL,
    BOSS_SEARCH_GEEK_URL,
    BOSS_SEND_MSG_URL,
    BOSS_SESSION_ENTER_URL,
    BOSS_VIEW_GEEK_URL,
    CITY_CODES,
    DELIVER_LIST_URL,
    FRIEND_ADD_URL,
    FRIEND_LIST_URL,
    GEEK_GET_JOB_URL,
    HEADERS,
    INTERVIEW_DATA_URL,
    JOB_CARD_URL,
    JOB_DETAIL_URL,
    JOB_HISTORY_URL,
    JOB_SEARCH_URL,
    RESUME_BASEINFO_URL,
    RESUME_EXPECT_URL,
    RESUME_STATUS_URL,
    USER_INFO_URL,
    WEB_BOSS_CHAT_URL,
    WEB_GEEK_CHAT_URL,
    WEB_GEEK_HISTORY_URL,
    WEB_GEEK_JOB_URL,
    WEB_GEEK_RECOMMEND_URL,
)
from .exceptions import BossApiError, ParamError, RateLimitError, SessionExpiredError

logger = logging.getLogger(__name__)


class BossClient:
    """Boss Zhipin API client with Gaussian jitter, exponential backoff, and session-stable identity.

    Anti-detection strategy:
    - Gaussian jitter delay between requests (~1s mean, σ=0.3)
    - 5% chance of a random long pause (2-5s) to mimic reading behavior
    - Exponential backoff on HTTP 429/5xx (up to 3 retries)
    - Response cookies merged back into session jar
    - Request counter for monitoring
    """

    def __init__(
        self,
        credential: object | None = None,
        timeout: float = 30.0,
        request_delay: float = 1.0,
        max_retries: int = 3,
    ):
        self.credential = credential
        self._timeout = timeout
        self._request_delay = request_delay
        self._base_request_delay = request_delay
        self._max_retries = max_retries
        self._last_request_time = 0.0
        self._request_count = 0
        self._rate_limit_count = 0
        self._recent_request_times: deque[float] = deque(maxlen=12)
        self._http: httpx.Client | None = None

    def _build_client(self) -> httpx.Client:
        cookies = {}
        if self.credential:
            cookies = self.credential.cookies
        return httpx.Client(
            base_url=BASE_URL,
            headers=dict(HEADERS),
            cookies=cookies,
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        )

    @property
    def client(self) -> httpx.Client:
        if not self._http:
            raise RuntimeError("Client not initialized. Use 'with BossClient() as client:'")
        return self._http

    def __enter__(self) -> BossClient:
        self._http = self._build_client()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._http:
            self._http.close()
            self._http = None

    # ── Rate limiting ───────────────────────────────────────────────

    def _rate_limit_delay(self) -> None:
        """Enforce minimum delay with Gaussian jitter to mimic human browsing."""
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            # Gaussian jitter: mean=0.3, σ=0.15, clamped to [0, ∞)
            jitter = max(0, random.gauss(0.3, 0.15))
            # 5% chance of a long pause to mimic reading
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            sleep_time = self._request_delay - elapsed + jitter
            logger.debug("Rate-limit delay: %.2fs", sleep_time)
            time.sleep(sleep_time)

        burst_penalty = self._burst_penalty_delay()
        if burst_penalty > 0:
            logger.debug("Burst penalty delay: %.2fs", burst_penalty)
            time.sleep(burst_penalty)

    def _burst_penalty_delay(self) -> float:
        """Add extra delay when a burst pattern looks less like human browsing."""
        if not self._recent_request_times:
            return 0.0

        now = time.time()
        recent_15s = sum(1 for ts in self._recent_request_times if now - ts <= 15)
        recent_45s = sum(1 for ts in self._recent_request_times if now - ts <= 45)

        if recent_45s >= 6:
            return random.uniform(4.0, 7.0)
        if recent_15s >= 3:
            return random.uniform(1.2, 2.8)
        return 0.0

    def _mark_request(self) -> None:
        now = time.time()
        self._last_request_time = now
        self._request_count += 1
        self._recent_request_times.append(now)

    @property
    def request_stats(self) -> dict[str, int | float]:
        """Return current request statistics."""
        return {
            "request_count": self._request_count,
            "last_request_time": self._last_request_time,
        }

    # ── Response handling ───────────────────────────────────────────

    def _merge_response_cookies(self, resp: httpx.Response) -> None:
        """Persist response Set-Cookie headers back into the session jar."""
        for name, value in resp.cookies.items():
            if value:
                self.client.cookies.set(name, value)

    def _headers_for_request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, str]:
        """Build browser-like headers, including endpoint-specific Referer."""
        headers = dict(HEADERS)
        if url == JOB_SEARCH_URL:
            query = ""
            if params and params.get("query"):
                query = f"?{urllib.parse.urlencode({'query': params['query']})}"
            headers["Referer"] = f"{WEB_GEEK_JOB_URL}{query}"
        elif url == GEEK_GET_JOB_URL and params and params.get("tag") == 5:
            headers["Referer"] = WEB_GEEK_RECOMMEND_URL
        elif url == GEEK_GET_JOB_URL:
            headers["Referer"] = WEB_GEEK_CHAT_URL
        elif url in (JOB_CARD_URL, JOB_DETAIL_URL):
            headers["Referer"] = WEB_GEEK_JOB_URL
        elif url == JOB_HISTORY_URL:
            headers["Referer"] = WEB_GEEK_HISTORY_URL
        elif url in (FRIEND_LIST_URL, FRIEND_ADD_URL):
            headers["Referer"] = WEB_GEEK_CHAT_URL
        # Recruiter (boss) endpoints
        elif url == BOSS_SEARCH_GEEK_URL:
            headers["Referer"] = f"{BASE_URL}/web/chat/search"
        elif url in (BOSS_VIEW_GEEK_URL, BOSS_SEND_MSG_URL):
            headers["Referer"] = WEB_BOSS_CHAT_URL
        elif url in (BOSS_FRIEND_LIST_URL, BOSS_FRIEND_DETAIL_URL, BOSS_LAST_MSG_URL,
                      BOSS_HISTORY_MSG_URL, BOSS_CHAT_GEEK_INFO_URL, BOSS_FRIEND_LABELS_URL,
                      BOSS_FRIEND_NOTE_URL, BOSS_GREET_SORT_LIST_URL, BOSS_GREET_REC_SORT_URL,
                      BOSS_CHATTED_JOB_LIST_URL, BOSS_INTERVIEW_LIST_URL,
                      BOSS_EXCHANGE_REQUEST_URL, BOSS_EXCHANGE_CONTENT_URL,
                      BOSS_INTERVIEW_INVITE_URL, BOSS_REMOVE_FILTER_URL,
                      BOSS_SESSION_ENTER_URL):
            headers["Referer"] = WEB_BOSS_CHAT_URL
        return headers

    def _handle_response(self, data: dict[str, Any], action: str) -> dict[str, Any]:
        """Validate API response and return zpData, raise typed exceptions."""
        code = data.get("code", -1)

        if code == 0:
            return data.get("zpData", {})

        message = data.get("message", "Unknown error")

        if code == 37:
            raise SessionExpiredError()
        if code in (17, 19):
            raise ParamError(message, code=code)
        if code == 9:
            # Rate limited — auto-cooldown with exponential backoff
            self._rate_limit_count += 1
            cooldown = min(60, 10 * (2 ** (self._rate_limit_count - 1)))
            self._request_delay = max(self._request_delay, self._base_request_delay * 2)
            logger.warning(
                "Rate limited (count=%d), cooling down %.0fs, delay raised to %.1fs",
                self._rate_limit_count, cooldown, self._request_delay,
            )
            time.sleep(cooldown)
            raise RateLimitError()

        raise BossApiError(f"{action}: {message} (code={code})", code=code, response=data)

    # ── Request with retry ──────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Execute HTTP request with rate-limit delay, retry, and cookie merge."""
        self._rate_limit_delay()
        last_exc: Exception | None = None
        params = kwargs.get("params")
        merged_headers = self._headers_for_request(url, params=params)
        request_headers = kwargs.pop("headers", None)
        if request_headers:
            merged_headers.update(request_headers)

        for attempt in range(self._max_retries):
            t0 = time.time()
            try:
                resp = self.client.request(method, url, headers=merged_headers, **kwargs)
                elapsed = time.time() - t0
                self._merge_response_cookies(resp)
                self._mark_request()

                logger.info(
                    "[#%d] %s %s → %d (%.2fs)",
                    self._request_count, method, url[:60], resp.status_code, elapsed,
                )

                # Retry on server errors
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "HTTP %d from %s, retrying in %.1fs (attempt %d/%d)",
                        resp.status_code, url[:80], wait, attempt + 1, self._max_retries,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()

                # Check for HTML responses (redirect to login page)
                text = resp.text
                if text.startswith("<"):
                    raise BossApiError(f"Received HTML instead of JSON from {url} (possible auth redirect)")

                return resp.json()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                elapsed = time.time() - t0
                last_exc = exc
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "[#%d] %s %s → Network error: %s (%.2fs), retrying in %.1fs (attempt %d/%d)",
                    self._request_count + 1, method, url[:60], exc, elapsed, wait,
                    attempt + 1, self._max_retries,
                )
                time.sleep(wait)

        if last_exc:
            raise BossApiError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc
        raise BossApiError(f"Request failed after {self._max_retries} retries")

    def _get(self, url: str, params: dict[str, Any] | None = None, action: str = "") -> dict[str, Any]:
        """GET request with response validation and rate-limit retry."""
        data = self._request("GET", url, params=params)
        try:
            result = self._handle_response(data, action)
            # Reset rate-limit counter on success
            self._rate_limit_count = 0
            return result
        except RateLimitError:
            # Auto-retry once after cooldown (cooldown already happened in _handle_response)
            logger.info("Retrying after rate-limit cooldown...")
            data = self._request("GET", url, params=params)
            result = self._handle_response(data, action)
            self._rate_limit_count = 0
            return result

    # ── Job Search & Browse ─────────────────────────────────────────

    def search_jobs(
        self,
        query: str,
        city: str = "101010100",
        page: int = 1,
        page_size: int = 15,
        experience: str | None = None,
        degree: str | None = None,
        salary: str | None = None,
        industry: str | None = None,
        scale: str | None = None,
        stage: str | None = None,
        job_type: str | None = None,
    ) -> dict[str, Any]:
        """Search jobs."""
        params: dict[str, Any] = {
            "query": query,
            "city": city,
            "page": page,
            "pageSize": page_size,
        }
        if experience:
            params["experience"] = experience
        if degree:
            params["degree"] = degree
        if salary:
            params["salary"] = salary
        if industry:
            params["industry"] = industry
        if scale:
            params["scale"] = scale
        if stage:
            params["stage"] = stage
        if job_type:
            params["jobType"] = job_type
        return self._get(JOB_SEARCH_URL, params=params, action="搜索职位")

    def get_recommend_jobs(self, page: int = 1) -> dict[str, Any]:
        """Get personalized job recommendations.

        The live web page currently loads recommendation cards from
        ``/wapi/zprelation/interaction/geekGetJob`` with tag=5 rather
        than the older ``/wapi/zpgeek/pc/recommend/job/list.json`` path.
        Normalize that payload back into the CLI's historical shape.
        """
        data = self._get(
            GEEK_GET_JOB_URL,
            params={"page": page, "tag": 5, "isActive": "true"},
            action="推荐职位",
        )
        if "jobList" in data:
            return data

        card_list = data.get("cardList", [])
        return {
            "jobList": card_list,
            "hasMore": data.get("hasMore", False),
            "totalCount": data.get("totalCount", len(card_list)),
            "page": data.get("page", page),
            "startIndex": data.get("startIndex", 0),
            "type": data.get("type", 2),
            "lid": data.get("lid", ""),
        }

    def get_job_card(self, security_id: str, lid: str) -> dict[str, Any]:
        """Get job card info (hover preview)."""
        return self._get(JOB_CARD_URL, params={"securityId": security_id, "lid": lid}, action="职位卡片")

    def get_job_detail(self, security_id: str, lid: str = "") -> dict[str, Any]:
        """Get detailed information for a specific job."""
        params: dict[str, str] = {"securityId": security_id}
        if lid:
            params["lid"] = lid
        return self._get(JOB_DETAIL_URL, params=params, action="职位详情")

    # ── Personal Center ─────────────────────────────────────────────

    def get_user_info(self) -> dict[str, Any]:
        """Get current user info (userId, name, avatar, etc.)."""
        return self._get(USER_INFO_URL, action="用户信息")

    def get_resume_baseinfo(self) -> dict[str, Any]:
        """Get resume basic info (full profile: name, age, degree, etc.)."""
        return self._get(RESUME_BASEINFO_URL, action="简历基本信息")

    def get_resume_expect(self) -> dict[str, Any]:
        """Get job expectations (desired position, salary, city)."""
        return self._get(RESUME_EXPECT_URL, action="求职期望")

    def get_resume_status(self) -> dict[str, Any]:
        """Get resume status."""
        return self._get(RESUME_STATUS_URL, action="简历状态")

    def get_deliver_list(self, page: int = 1) -> dict[str, Any]:
        """Get list of jobs applied to (已投递)."""
        return self._get(DELIVER_LIST_URL, params={"page": page}, action="已投递列表")

    def get_interview_data(self) -> dict[str, Any]:
        """Get interview data (面试)."""
        return self._get(INTERVIEW_DATA_URL, action="面试数据")

    def get_job_history(self, page: int = 1) -> dict[str, Any]:
        """Get job browsing history."""
        return self._get(JOB_HISTORY_URL, params={"page": page}, action="浏览历史")

    # ── Social / Chat ───────────────────────────────────────────────

    def get_friend_list(self) -> dict[str, Any]:
        """Get geek friend list (沟通过的 Boss)."""
        return self._get(FRIEND_LIST_URL, action="好友列表")

    def add_friend(self, security_id: str, lid: str = "") -> dict[str, Any]:
        """Send greeting to a Boss (打招呼 / 投递简历)."""
        params: dict[str, str] = {"securityId": security_id}
        if lid:
            params["lid"] = lid
        return self._get(FRIEND_ADD_URL, params=params, action="打招呼")

    def get_geek_job(self, security_id: str) -> dict[str, Any]:
        """Get interacted job info."""
        return self._get(GEEK_GET_JOB_URL, params={"securityId": security_id}, action="互动职位")

    # ── Recruiter (Boss) Mode ────────────────────────────────────────

    def _post(self, url: str, data: dict[str, Any] | None = None, action: str = "") -> dict[str, Any]:
        """POST request with form-encoded body, response validation, and rate-limit retry."""
        resp = self._request("POST", url, data=data)
        try:
            result = self._handle_response(resp, action)
            self._rate_limit_count = 0
            return result
        except RateLimitError:
            logger.info("Retrying after rate-limit cooldown...")
            resp = self._request("POST", url, data=data)
            result = self._handle_response(resp, action)
            self._rate_limit_count = 0
            return result

    def get_boss_chatted_jobs(self) -> list[dict[str, Any]]:
        """Get list of jobs the boss has posted (chatted job list)."""
        return self._get(BOSS_CHATTED_JOB_LIST_URL, action="招聘职位列表")

    def get_boss_friend_list(self, label_id: int = 0, enc_job_id: str = "", sort: str = "", page: int = 1) -> dict[str, Any]:
        """Get boss friend list (candidates who have chatted)."""
        data: dict[str, Any] = {"labelId": label_id, "page": page}
        if enc_job_id:
            data["encJobId"] = enc_job_id
        if sort:
            data["sort"] = sort
        return self._post(BOSS_FRIEND_LIST_URL, data=data, action="候选人列表")

    def get_boss_friend_details(self, friend_ids: list[int]) -> dict[str, Any]:
        """Get detailed info for boss friends (candidates)."""
        ids_str = ",".join(str(fid) for fid in friend_ids)
        return self._post(BOSS_FRIEND_DETAIL_URL, data={"friendIds": ids_str}, action="候选人详情")

    def get_boss_last_messages(self, friend_ids: list[int], src: int = 0) -> list[dict[str, Any]]:
        """Get last message for each friend."""
        ids_str = ",".join(str(fid) for fid in friend_ids)
        return self._post(BOSS_LAST_MSG_URL, data={"friendIds": ids_str, "src": src}, action="最近消息")

    def get_boss_chat_history(self, gid: int, count: int = 20, max_msg_id: int = 0) -> dict[str, Any]:
        """Get chat history with a specific candidate."""
        params: dict[str, Any] = {"gid": gid, "c": count, "src": 0}
        if max_msg_id:
            params["maxMsgId"] = max_msg_id
        return self._get(BOSS_HISTORY_MSG_URL, params=params, action="聊天记录")

    def get_boss_chat_geek_info(
        self, encrypt_geek_id: str, security_id: str, job_id: int,
    ) -> dict[str, Any]:
        """Get detailed info for a candidate in chat context."""
        return self._get(
            BOSS_CHAT_GEEK_INFO_URL,
            params={"encryptGeekId": encrypt_geek_id, "securityId": security_id, "jobId": job_id},
            action="候选人信息",
        )

    def get_boss_friend_labels(self) -> dict[str, Any]:
        """Get recruiter's friend labels/tags."""
        return self._get(BOSS_FRIEND_LABELS_URL, action="标签列表")

    def get_boss_greet_list(self, enc_job_id: str = "", page: int = 1) -> dict[str, Any]:
        """Get list of new greetings (candidates who greeted the boss)."""
        params: dict[str, Any] = {"page": page}
        if enc_job_id:
            params["encJobId"] = enc_job_id
        return self._get(BOSS_GREET_SORT_LIST_URL, params=params, action="新招呼列表")

    def get_boss_greet_rec_list(self, enc_job_id: str = "", page: int = 1) -> dict[str, Any]:
        """Get recommended greeting sort list."""
        params: dict[str, Any] = {"page": page}
        if enc_job_id:
            params["encJobId"] = enc_job_id
        return self._get(BOSS_GREET_REC_SORT_URL, params=params, action="推荐招呼排序")

    def get_boss_interview_list(self) -> dict[str, Any]:
        """Get boss interview list."""
        return self._get(BOSS_INTERVIEW_LIST_URL, action="面试列表")

    def search_geeks(
        self, query: str, city: str = "101020100", page: int = 1,
        experience: str | None = None, degree: str | None = None,
        salary: str | None = None, encrypt_job_id: str = "",
    ) -> dict[str, Any]:
        """Search candidates (geeks) as a recruiter."""
        params: dict[str, Any] = {
            "query": query, "city": city, "page": page,
        }
        if encrypt_job_id:
            params["encryptJobId"] = encrypt_job_id
        if experience:
            params["experience"] = experience
        if degree:
            params["degree"] = degree
        if salary:
            params["salary"] = salary
        return self._get(BOSS_SEARCH_GEEK_URL, params=params, action="搜索候选人")

    def get_boss_recommend_geeks(self, page: int = 1, enc_job_id: str = "") -> dict[str, Any]:
        """Get recommended candidates (new greetings sorted by recommendation)."""
        params: dict[str, Any] = {"page": page}
        if enc_job_id:
            params["encJobId"] = enc_job_id
        return self._get(BOSS_GREET_REC_SORT_URL, params=params, action="推荐候选人")

    def get_boss_view_geek(
        self, encrypt_geek_id: str, encrypt_job_id: str, security_id: str = "",
    ) -> dict[str, Any]:
        """Get full candidate resume/profile view."""
        params: dict[str, Any] = {
            "encryptGeekId": encrypt_geek_id,
            "encryptJobId": encrypt_job_id,
        }
        if security_id:
            params["securityId"] = security_id
        return self._get(BOSS_VIEW_GEEK_URL, params=params, action="候选人简历")

    def boss_send_message(self, gid: int, content: str) -> dict[str, Any]:
        """Send a text message to a candidate as a recruiter."""
        return self._post(
            BOSS_SEND_MSG_URL,
            data={"gid": gid, "content": content},
            action="发送消息",
        )

    def boss_job_offline(self, encrypt_job_id: str) -> dict[str, Any]:
        """Take a job posting offline (close)."""
        return self._post(BOSS_JOB_OFFLINE_URL, data={"encryptJobId": encrypt_job_id}, action="关闭职位")

    def boss_job_online(self, encrypt_job_id: str) -> dict[str, Any]:
        """Bring a job posting online (reopen)."""
        return self._post(BOSS_JOB_ONLINE_URL, data={"encryptJobId": encrypt_job_id}, action="开启职位")

    # ── Recruiter Chat Actions ────────────────────────────────────────

    def boss_exchange_request(self, uid: int, job_id: int, exchange_type: int) -> dict[str, Any]:
        """Request exchange with candidate.

        exchange_type: 1=phone, 2=wechat, 3=resume
        """
        return self._post(
            BOSS_EXCHANGE_REQUEST_URL,
            data={"type": exchange_type, "uid": uid, "jobId": job_id},
            action="交换请求",
        )

    def boss_get_exchange_content(self, uid: int) -> dict[str, Any]:
        """Get exchanged contact info (phone/wechat) for a candidate."""
        return self._post(
            BOSS_EXCHANGE_CONTENT_URL,
            data={"uid": uid},
            action="查看交换内容",
        )

    def boss_interview_invite(
        self, encrypt_geek_id: str, encrypt_job_id: str, security_id: str,
        address: str = "", start_time: str = "", description: str = "",
    ) -> dict[str, Any]:
        """Invite candidate for an interview."""
        data: dict[str, Any] = {
            "encryptGeekId": encrypt_geek_id,
            "encryptJobId": encrypt_job_id,
            "securityId": security_id,
        }
        if address:
            data["address"] = address
        if start_time:
            data["startTime"] = start_time
        if description:
            data["description"] = description
        return self._post(BOSS_INTERVIEW_INVITE_URL, data=data, action="约面试")

    def boss_mark_unsuitable(self, encrypt_geek_id: str, encrypt_job_id: str) -> dict[str, Any]:
        """Mark candidate as unsuitable."""
        return self._post(
            BOSS_REMOVE_FILTER_URL,
            data={"encryptGeekId": encrypt_geek_id, "encryptJobId": encrypt_job_id},
            action="标记不合适",
        )

    def boss_session_enter(self, geek_id: str, expect_id: str, job_id: str, security_id: str) -> dict[str, Any]:
        """Enter a chat session with a candidate (required before sending messages)."""
        return self._post(
            BOSS_SESSION_ENTER_URL,
            data={"geekId": geek_id, "expectId": expect_id, "jobId": job_id, "securityId": security_id},
            action="进入会话",
        )


# ── City resolution ─────────────────────────────────────────────────

def resolve_city(name: str) -> str:
    """Resolve city name to code, passthrough if already a code."""
    if name.isdigit() and len(name) >= 6:
        return name
    return CITY_CODES.get(name, CITY_CODES["全国"])


def list_cities() -> dict[str, str]:
    """Return all supported city name -> code mappings."""
    return dict(CITY_CODES)
