"""Constants for Boss CLI — API endpoints, headers, and config paths."""

from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".config" / "boss-cli"
CREDENTIAL_FILE = CONFIG_DIR / "credential.json"
AUTH_HEALTH_CACHE_TTL_S = 45

# ── Base URL ────────────────────────────────────────────────────────
BASE_URL = "https://www.zhipin.com"
WEB_GEEK_BASE_URL = f"{BASE_URL}/web/geek"
WEB_GEEK_JOB_URL = f"{WEB_GEEK_BASE_URL}/job"
WEB_GEEK_RECOMMEND_URL = f"{WEB_GEEK_BASE_URL}/recommend"
WEB_GEEK_CHAT_URL = f"{WEB_GEEK_BASE_URL}/chat"
WEB_GEEK_HISTORY_URL = f"{WEB_GEEK_BASE_URL}/history"

# ── QR Login API ────────────────────────────────────────────────────
QR_RANDKEY_URL = "/wapi/zppassport/captcha/randkey"
QR_CODE_URL = "/wapi/zpweixin/qrcode/getqrcode"
QR_SCAN_URL = "/wapi/zppassport/qrcode/scan"
QR_SCAN_LOGIN_URL = "/wapi/zppassport/qrcode/scanLogin"
QR_DISPATCHER_URL = "/wapi/zppassport/qrcode/dispatcher"

# ── Job API ─────────────────────────────────────────────────────────
JOB_SEARCH_URL = "/wapi/zpgeek/search/joblist.json"
JOB_CARD_URL = "/wapi/zpgeek/job/card.json"
JOB_DETAIL_URL = "/wapi/zpgeek/job/detail.json"
JOB_HISTORY_URL = "/wapi/zpgeek/history/joblist.json"

# ── Personal Center API ─────────────────────────────────────────────
USER_INFO_URL = "/wapi/zpuser/wap/getUserInfo.json"
RESUME_BASEINFO_URL = "/wapi/zpgeek/resume/baseinfo/query.json"
RESUME_EXPECT_URL = "/wapi/zpgeek/resume/expect/query.json"
RESUME_STATUS_URL = "/wapi/zpgeek/resume/status.json"
DELIVER_LIST_URL = "/wapi/zprelation/resume/geekDeliverList"
INTERVIEW_DATA_URL = "/wapi/zpinterview/geek/interview/data.json"

# ── Social / Chat API ──────────────────────────────────────────────
FRIEND_LIST_URL = "/wapi/zprelation/friend/getGeekFriendList.json"
FRIEND_ADD_URL = "/wapi/zpgeek/friend/add.json"
GEEK_GET_JOB_URL = "/wapi/zprelation/interaction/geekGetJob"

# ── Recruiter (Boss) API ──────────────────────────────────────────
WEB_BOSS_CHAT_URL = f"{BASE_URL}/web/chat/index"
WEB_BOSS_RECOMMEND_URL = f"{BASE_URL}/web/chat/recommend"
BOSS_FRIEND_LIST_URL = "/wapi/zprelation/friend/filterByLabel"
BOSS_FRIEND_DETAIL_URL = "/wapi/zprelation/friend/getBossFriendListV2.json"
BOSS_LAST_MSG_URL = "/wapi/zpchat/boss/userLastMsg"
BOSS_HISTORY_MSG_URL = "/wapi/zpchat/boss/historyMsg"
BOSS_CHATTED_JOB_LIST_URL = "/wapi/zpjob/job/chatted/jobList"
BOSS_CHAT_GEEK_INFO_URL = "/wapi/zpjob/chat/geek/info"
BOSS_VIEW_GEEK_INFO_URL = "/wapi/zpjob/view/geek/info"
BOSS_FRIEND_LABELS_URL = "/wapi/zprelation/friend/label/get"
BOSS_FRIEND_NOTE_URL = "/wapi/zprelation/friend/getNoteAndLabels"
BOSS_GREET_SORT_LIST_URL = "/wapi/zprelation/friend/greetSort/getList"
BOSS_GREET_REC_SORT_URL = "/wapi/zprelation/friend/greetRecSortList"
BOSS_INTERVIEW_LIST_URL = "/wapi/zpinterview/boss/interview/valid/list"
BOSS_INTERVIEW_DETAIL_URL = "/wapi/zpinterview/boss/interview/detail"
BOSS_GREET_NEW_LIST_URL = "/wapi/zpchat/boss/newgreeting/getHistoryList"
BOSS_SEARCH_GEEK_URL = "/wapi/zpitem/web/boss/search/geek/info"
BOSS_VIEW_GEEK_URL = "/wapi/zpjob/view/geek/info"
BOSS_SEND_MSG_URL = "/wapi/zpchat/fastReply/sendReplyMsg"
BOSS_FRIEND_ADD_URL = "/wapi/zprelation/friend/bossAddFriend"

# ── Request Headers (Chrome 145, macOS) ─────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";v="145", "Not(A:Brand";v="99", "Google Chrome";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "DNT": "1",
    "Priority": "u=1, i",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}

# ── Cookie keys required for authenticated sessions ─────────────────
REQUIRED_COOKIES = {"__zp_stoken__", "wt2", "wbg", "zp_at"}

# ── City codes ──────────────────────────────────────────────────────
CITY_CODES: dict[str, str] = {
    "全国": "100010000",
    # 一线
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    # 新一线
    "杭州": "101210100",
    "成都": "101270100",
    "南京": "101190100",
    "武汉": "101200100",
    "西安": "101110100",
    "苏州": "101190400",
    "长沙": "101250100",
    "天津": "101030100",
    "重庆": "101040100",
    "郑州": "101180100",
    "东莞": "101281600",
    "佛山": "101280800",
    "合肥": "101220100",
    "青岛": "101120200",
    "宁波": "101210400",
    "沈阳": "101070100",
    "昆明": "101290100",
    # 二线
    "大连": "101070200",
    "厦门": "101230200",
    "珠海": "101280700",
    "无锡": "101190200",
    "福州": "101230100",
    "济南": "101120100",
    "哈尔滨": "101050100",
    "长春": "101060100",
    "南昌": "101240100",
    "贵阳": "101260100",
    "南宁": "101300100",
    "石家庄": "101090100",
    "太原": "101100100",
    "兰州": "101160100",
    "海口": "101310100",
    "常州": "101191100",
    "温州": "101210700",
    "嘉兴": "101210300",
    "徐州": "101190800",
    # 特别行政区
    "香港": "101320100",
}

# ── Salary filter codes ─────────────────────────────────────────────
SALARY_CODES: dict[str, str] = {
    "3K以下": "401",
    "3-5K": "402",
    "5-10K": "403",
    "10-15K": "404",
    "15-20K": "405",
    "20-30K": "406",
    "30-50K": "407",
    "50K以上": "408",
}

# ── Experience filter codes ─────────────────────────────────────────
EXP_CODES: dict[str, str] = {
    "不限": "0",
    "在校/应届": "108",
    "1年以内": "101",
    "1-3年": "102",
    "3-5年": "103",
    "5-10年": "104",
    "10年以上": "105",
}

# ── Degree filter codes ─────────────────────────────────────────────
DEGREE_CODES: dict[str, str] = {
    "不限": "0",
    "初中及以下": "209",
    "中专/中技": "208",
    "高中": "206",
    "大专": "202",
    "本科": "203",
    "硕士": "204",
    "博士": "205",
}

# ── Industry filter codes ──────────────────────────────────────────
INDUSTRY_CODES: dict[str, str] = {
    "不限": "0",
    "互联网": "100020",
    "电子商务": "100021",
    "游戏": "100024",
    "软件/信息服务": "100032",
    "人工智能": "100901",
    "大数据": "100902",
    "云计算": "100903",
    "区块链": "100904",
    "物联网": "100905",
    "金融": "100101",
    "银行": "100102",
    "保险": "100103",
    "证券/基金": "100104",
    "教育培训": "100200",
    "医疗健康": "100300",
    "房地产": "100400",
    "汽车": "100500",
    "物流/运输": "100600",
    "广告/传媒": "100700",
    "消费品": "100800",
    "制造业": "101000",
    "能源/环保": "101100",
    "政府/非营利": "101200",
    "农业": "101300",
}

# ── Company scale filter codes ─────────────────────────────────────
SCALE_CODES: dict[str, str] = {
    "不限": "0",
    "0-20人": "301",
    "20-99人": "302",
    "100-499人": "303",
    "500-999人": "304",
    "1000-9999人": "305",
    "10000人以上": "306",
}

# ── Company stage (funding) filter codes ───────────────────────────
STAGE_CODES: dict[str, str] = {
    "不限": "0",
    "未融资": "801",
    "天使轮": "802",
    "A轮": "803",
    "B轮": "804",
    "C轮": "805",
    "D轮及以上": "806",
    "已上市": "807",
    "不需要融资": "808",
}

# ── Job type filter codes ──────────────────────────────────────────
JOB_TYPE_CODES: dict[str, str] = {
    "全职": "1901",
    "兼职": "1903",
    "实习": "1903",
}
