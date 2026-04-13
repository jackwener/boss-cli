# boss-cli

[![PyPI version](https://img.shields.io/pypi/v/kabi-boss-cli.svg)](https://pypi.org/project/kabi-boss-cli/)
[![CI](https://github.com/jackwener/boss-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jackwener/boss-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://pypi.org/project/kabi-boss-cli/)

A CLI for BOSS 直聘 — search jobs, view recommendations, manage applications, chat with recruiters, **and manage candidates as a recruiter** via reverse-engineered API 🤝

[English](#features) | [中文](#功能特性)

## More Tools

- [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) — Xiaohongshu CLI for notes, search, and interactions
- [bilibili-cli](https://github.com/jackwener/bilibili-cli) — Bilibili CLI for videos, users, and search
- [twitter-cli](https://github.com/jackwener/twitter-cli) — Twitter/X CLI for timelines, bookmarks, and posting
- [discord-cli](https://github.com/jackwener/discord-cli) — Discord CLI for local-first sync, search, and export
- [tg-cli](https://github.com/jackwener/tg-cli) — Telegram CLI for local-first sync, search, and export
- [rdt-cli](https://github.com/jackwener/rdt-cli) — Reddit CLI for feed, search, posts, and interactions

## Features

- 🔐 **Auth** — auto-extract browser cookies (10+ browsers), QR code login, `--cookie-source` explicit browser selection, live validation against real search APIs
- 🔍 **Search** — jobs by keyword with city/salary/experience/degree/industry/scale/stage/job-type filters
- ⭐ **Recommendations** — personalized job recommendations based on profile
- 📋 **Detail & Export** — view full job details, short-index navigation (`boss show 3`), CSV/JSON export
- 📜 **History** — browse job viewing history
- 👤 **Profile** — view personal info, resume status
- 📮 **Applications** — view applied jobs list
- 📋 **Interviews** — view interview invitations
- 💬 **Chat** — view communicated boss list
- 🤝 **Greet** — send greetings to recruiters, single or batch (with 1.5s rate-limit delay)
- 🏙️ **Cities** — 40+ supported cities
- 🤖 **Agent-friendly** — structured output envelope (`{ok, schema_version, data}`), Rich output on stderr
- 👔 **Recruiter Mode** — view posted jobs, manage candidates, chat history, export candidate data (CSV/JSON)

## Installation

```bash
# Recommended: uv tool (fast, isolated)
uv tool install kabi-boss-cli

# Or: pipx
pipx install kabi-boss-cli

# Optional: YAML output support
pip install kabi-boss-cli[yaml]
```

Upgrade to the latest version:

```bash
uv tool upgrade kabi-boss-cli
# Or: pipx upgrade kabi-boss-cli
```

From source:

```bash
git clone git@github.com:jackwener/boss-cli.git
cd boss-cli
uv sync
```

## Usage

```bash
# ─── Auth ─────────────────────────────────────────
boss login                             # Auto-detect browser cookies, fallback to QR
boss login --cookie-source chrome      # Extract from specific browser
boss login --qrcode                    # QR code login only
boss login --cookie-file /path/cred.json   # Import cookies from file
boss login --cookie "k=v; k2=v2"           # Import cookies from string
boss cookie-server                       # Start local cookie bridge server
boss status                            # Check login status (validates real search session, shows cookie names)
boss logout                            # Clear saved cookies

# ─── Search ───────────────────────────────────────
boss search "golang"                   # Search jobs
boss search "Python" --city 杭州       # Filter by city
boss search "Java" --salary 20-30K     # Filter by salary
boss search "前端" --exp 3-5年          # Filter by experience
boss search "AI" --degree 硕士         # Filter by degree
boss search "后端" --industry 互联网    # Filter by industry
boss search "产品" --scale 1000-9999人  # Filter by company size
boss search "数据" --stage 已上市       # Filter by funding stage
boss search "运维" --job-type 全职      # Filter by job type
boss search "后端" --city 深圳 -p 2    # Pagination

# ─── Detail & Export ──────────────────────────────
boss show 3                            # View job #3 from last search
boss detail <securityId>               # View full job details
boss detail <securityId> --json        # JSON output (with schema envelope)
boss export "Python" -n 50 -o jobs.csv # Export search results to CSV
boss export "golang" --format json -o jobs.json  # Export as JSON

# ─── Recommendations ──────────────────────────────
boss recommend                         # View recommended jobs
boss recommend -p 2 --json             # Next page, JSON output

# ─── Personal Center ─────────────────────────────
boss me                                # View profile
boss me --json                         # JSON output
boss applied                           # View applied jobs
boss interviews                        # View interview invitations
boss history                           # View browsing history
boss chat                              # View communicated bosses

# ─── Greet ────────────────────────────────────────
boss greet <securityId>                # Send greeting to a boss
boss greet <securityId> --json         # JSON result
boss batch-greet "golang" --city 杭州 -n 5          # Batch greet top 5
boss batch-greet "Python" --salary 20-30K --dry-run  # Preview only

# ─── Utilities ────────────────────────────────────
boss cities                            # List supported cities
boss --version                         # Show version
boss -v search "Python"                # Verbose logging (request timing)
```

## Recruiter Mode (雇主端)

If you are an employer on BOSS直聘, these commands let you manage candidates from the terminal:

```bash
# ─── Search & Discover (搜索 & 发现) ─────────────
boss recruiter search "golang" --city 深圳 --exp 3-5年    # Search candidates
boss recruiter recommend                                    # Recommended candidates
boss recruiter recommend --job <encryptJobId>               # Switch to different 岗位
boss recruiter recommend -n 20                             # Limit display

# ─── Greet & Communicate (沟通) ──────────────────
boss recruiter greet <encryptGeekId>                        # Initiate chat with candidate
boss recruiter batch-greet "Python" --city 杭州 -n 10      # Batch greet top 10 matches
boss recruiter inbox                                        # View candidate messages
boss recruiter inbox --job <encryptJobId> -n 20             # Filter by job, limit display
boss recruiter reply <friendId> "感谢您的关注..."            # Reply to candidate
boss recruiter chat <friendId>                              # View chat history

# ─── Chat Actions (沟通页操作) ───────────────────
boss recruiter request-resume <friendId> --yes              # 求简历
boss recruiter exchange-phone <friendId> --yes              # 换电话
boss recruiter exchange-wechat <friendId> --yes             # 换微信
boss recruiter invite-interview <geekId> --job <id>         # 约面试
boss recruiter mark-unsuitable <geekId> --job <id>          # 不合适

# ─── Resume (简历) ───────────────────────────────
boss recruiter resume <encryptGeekId>                       # View full resume in terminal
boss recruiter resume-download <id> --job <jobId>           # Download resume as Markdown
boss recruiter geek <encryptGeekId> --job-id 526908510      # Quick candidate info

# ─── Job Management (职位管理) ───────────────────
boss recruiter jobs                                         # List your posted jobs
boss recruiter job-close <encryptJobId> --yes               # Take job offline
boss recruiter job-reopen <encryptJobId> --yes              # Bring job back online

# ─── Export & Tags ───────────────────────────────
boss recruiter labels                                       # View candidate tags
boss recruiter export -o candidates.csv                     # Export to CSV
boss recruiter export --format json -o out.json             # Export to JSON
```

### Recruiter Workflow Example

```bash
# 1. Check your posted jobs
boss recruiter jobs

# 2. Browse recommended candidates for a specific job
boss recruiter recommend --job f806096ea327cd610nZ80t21FVNQ

# 3. Search for specific skills
boss recruiter search "golang" --city 深圳

# 4. View a candidate's full resume
boss recruiter resume <encryptGeekId> --job <encryptJobId>

# 5. Download resume for offline review
boss recruiter resume-download <encryptGeekId> --job <encryptJobId>

# 6. Start a conversation
boss recruiter greet <encryptGeekId>

# 7. Check inbox and reply
boss recruiter inbox -n 20
boss recruiter reply <friendId> "感谢您的关注，方便电话聊聊吗？"

# 8. Export all candidates
boss recruiter export --format json -o candidates.json
```

## Structured Output

All commands with `--json` / `--yaml` use a unified output envelope (see [SCHEMA.md](./SCHEMA.md)):

```json
{
  "ok": true,
  "schema_version": "1",
  "data": { ... }
}
```

- **Non-TTY stdout** → auto YAML (agent-friendly)
- **`--json`** → explicit JSON
- **Rich output** → stderr (won't pollute pipes: `boss search X --json | jq .data`)

## Authentication

boss-cli supports multiple authentication methods:

1. **Saved cookies** — loads from `~/.config/boss-cli/credential.json`
2. **Browser cookies** — auto-detects installed browsers (Chrome, Firefox, Edge, Brave, Arc, Chromium, Opera, Vivaldi, Safari, LibreWolf)
3. **QR code login** — terminal QR output using Unicode half-blocks, scan with Boss 直聘 APP
4. **Cookie import** — `boss login --cookie-file` or `BOSS_COOKIES` env for headless servers

`boss login` auto-extracts browser cookies first, falls back to QR login. Use `--cookie-source chrome` to specify a browser, or `--qrcode` to skip browser detection. The command now verifies the saved credential against a real authenticated API before reporting success.

`boss recommend` follows the live web app's current recommendation data source and request context, which improves compatibility when the legacy recommendation endpoint is rejected.

`boss status --json` now reports per-flow health such as `search_authenticated` and `recommend_authenticated`, which helps diagnose partial-session issues. To avoid turning repeated checks into their own anti-bot problem, health snapshots are cached briefly in-memory.

### Headless / Server Login (无可视化页面)

If your server has no GUI, use one of these:

1. **Cookie file import**
   - Export cookies from a browser machine and copy to the server
   - `boss login --cookie-file /path/credential.json`

2. **Environment variable**
   - `export BOSS_COOKIES="k=v; k2=v2"`
   - `boss status --json`

### Chrome Extension (Real-time Cookie Extraction)

Some cookies (notably `__zp_stoken__`) are generated by browser JS and may not be written to disk immediately.
The included Chrome extension can extract cookies from browser memory and push them to a local bridge.

1. Start the local bridge:
   - `boss cookie-server`
2. Load the extension:
   - Open `chrome://extensions/`
   - Enable Developer mode
   - Load unpacked: `chrome-extension/zhipin-cookie-extractor`
3. Log in to `https://www.zhipin.com`, click the extension, then **Sync**.

### Cookie TTL & Auto-Refresh

Saved cookies auto-refresh from browser after **7 days**. If browser refresh fails, falls back to stale cookies and logs a warning.

## Rate Limiting & Anti-Detection

- **Gaussian jitter**: request delays with `random.gauss(0.3, 0.15)`
- **Random long pauses**: 5% chance of 2-5s pause to mimic reading
- **Rate-limit auto-cooldown**: code=9 triggers exponential backoff (10s→20s→40s→60s) + request delay doubling
- **Exponential backoff**: auto-retry on HTTP 429/5xx (max 3 retries)
- **Response cookie merge**: `Set-Cookie` headers merged back into session
- **HTML redirect detection**: catches auth redirects to login page
- **Browser fingerprint**: macOS Chrome 145 UA, `sec-ch-ua`, `DNT`, `Priority` headers
- **Request logging**: `boss -v` shows request URLs, status codes, and timing

## Use as AI Agent Skill

boss-cli ships with a [`SKILL.md`](./SKILL.md) that teaches AI agents how to use it.

### [Skills CLI](https://github.com/vercel-labs/skills) (Recommended)

```bash
npx skills add jackwener/boss-cli
```

| Flag | Description |
| --- | --- |
| `-g` | Install globally (user-level, shared across projects) |
| `-a claude-code` | Target a specific agent |
| `-y` | Non-interactive mode |

### Manual Install

```bash
mkdir -p .agents/skills
git clone git@github.com:jackwener/boss-cli.git .agents/skills/boss-cli
```

### ~~OpenClaw / ClawHub~~ (Deprecated)

> ⚠️ ClawHub install method is deprecated and no longer supported. Use [Skills CLI](#skills-cli-recommended) or Manual Install above.

## Project Structure

```text
boss_cli/
├── __init__.py           # Package version
├── cli.py                # Click entry point (lightweight, add_command only)
├── client.py             # API client (rate-limit, cooldown, retry, anti-detection)
├── auth.py               # Authentication (10+ browsers, QR login, TTL refresh)
├── constants.py          # URLs, headers (Chrome 145), city codes, filter enums
├── exceptions.py         # Structured exceptions (BossApiError hierarchy)
├── index_cache.py        # Short-index cache for `boss show`
└── commands/
    ├── _common.py        # SCHEMA envelope, handle_command, stderr console
    ├── auth.py           # login (--cookie-source/--qrcode), logout, status, me
    ├── search.py         # search, recommend, detail, show, export, history, cities
    ├── personal.py       # applied, interviews
    ├── social.py         # chat, greet (--json), batch-greet (1.5s delay)
    └── recruiter.py      # recruiter-jobs, inbox, geek, chat, labels, export
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Smoke tests (need cookies)
uv run pytest tests/ -v -m smoke

# Lint
uv run ruff check .
```

## Troubleshooting

**Q: `boss status` says not authenticated but local cookies still exist**

`boss status` now verifies the session against a real search API. If `authenticated=false`, your local credential file exists but the underlying web session is no longer usable.

**Q: `环境异常 (__zp_stoken__ 已过期)`**

Your session cookies have expired. Run `boss logout && boss login` to refresh. If QR login only returns a partial cookie set, log in from a browser first and then run `boss login`.

**Q: `暂无投递记录` but I have applied**

Some features require fresh `__zp_stoken__`. Try re-logging in from a browser, then `boss login`.

**Q: Search returns no results**

Check your city filter. Some keywords are city-specific. Use `boss cities` to see available cities.

---

## 功能特性

- 🔐 **认证** — 自动提取浏览器 Cookie（10+ 浏览器），二维码扫码登录，`--cookie-source` 指定浏览器
- 🔍 **搜索** — 按关键词搜索职位，支持城市/薪资/经验/学历/行业/规模/融资阶段/职位类型筛选
- ⭐ **推荐** — 基于求职期望的个性化推荐
- 📋 **详情 & 导出** — 职位详情，编号导航 (`boss show 3`)，CSV/JSON 导出
- 📜 **历史** — 查看浏览历史
- 👤 **个人** — 查看个人资料
- 📮 **投递** — 查看已投递职位列表
- 📋 **面试** — 查看面试邀请
- 💬 **沟通** — 查看沟通过的 Boss 列表
- 🤝 **打招呼** — 向 Boss 打招呼/投递，支持批量操作（内置 1.5s 防风控延迟）
- 🏙️ **城市** — 40+ 城市支持
- 🤖 **Agent 友好** — 结构化输出 envelope，Rich 输出走 stderr
- 👔 **招聘方模式** — 查看职位、候选人管理、聊天记录、导出候选人数据 (CSV/JSON)

## 使用示例

```bash
# 认证
boss login                             # 自动提取浏览器 Cookie，失败则二维码
boss login --cookie-source chrome      # 指定浏览器
boss status                            # 检查登录状态
boss logout                            # 清除 Cookie
boss login --cookie-file /path/cred.json   # 从文件导入 Cookie
boss cookie-server                       # 启动本地 Cookie Bridge

# 搜索 & 详情
boss search "golang" --city 杭州       # 按城市搜索
boss search "AI" --industry 互联网 --scale 1000-9999人  # 行业+规模
boss search "数据" --stage 已上市 --salary 30-50K       # 融资+薪资
boss show 3                            # 按编号查看详情
boss detail <securityId> --json        # 指定 ID 查看（JSON envelope）
boss export "Python" -n 50 -o jobs.csv # 导出 CSV

# 推荐 & 历史
boss recommend                         # 个性化推荐
boss history                           # 浏览历史

# 个人中心
boss me --json                         # 个人资料（JSON）
boss applied                           # 已投递
boss interviews                        # 面试邀请
boss chat                              # 沟通列表

# 打招呼
boss greet <securityId> --json         # 单个打招呼
boss batch-greet "golang" -n 10        # 批量打招呼
boss batch-greet "golang" --dry-run    # 预览

# 工具
boss cities                            # 城市列表
boss -v search "Python"                # 详细日志
```

## 招聘方模式

```bash
# 搜索 & 推荐
boss recruiter search "golang" --city 深圳 --exp 3-5年
boss recruiter recommend --job <encryptJobId>  # 按岗位查看推荐牛人
boss recruiter recommend -n 20                 # 限制显示

# 沟通
boss recruiter greet <encryptGeekId>           # 向候选人打招呼
boss recruiter batch-greet "Python" -n 10      # 批量打招呼
boss recruiter inbox -n 20                     # 查看候选人消息
boss recruiter reply <friendId> "您好..."       # 回复候选人

# 沟通页操作
boss recruiter request-resume <friendId>       # 求简历
boss recruiter exchange-phone <friendId>       # 换电话
boss recruiter exchange-wechat <friendId>      # 换微信
boss recruiter invite-interview <id> --job <id> # 约面试
boss recruiter mark-unsuitable <id> --job <id>  # 不合适

# 简历
boss recruiter resume <encryptGeekId>          # 终端查看简历
boss recruiter resume-download <id> --job <id> # 下载简历为 Markdown

# 职位管理
boss recruiter jobs                            # 查看招聘职位
boss recruiter job-close <encryptJobId>        # 关闭职位
boss recruiter job-reopen <encryptJobId>       # 重新开启

# 导出
boss recruiter labels                          # 查看标签
boss recruiter export -o candidates.csv        # 导出候选人
```

## 常见问题

- `环境异常` — Cookie 过期，执行 `boss logout && boss login` 刷新
- 搜索无结果 — 检查城市筛选或关键词，使用 `boss cities` 查看支持的城市

## 无可视化页面 / 服务器登录

如果服务器没有浏览器界面，推荐以下方案：

1. **导入 Cookie 文件**
   - 在有浏览器的机器上登录后导出 `credential.json`
   - 复制到服务器后执行 `boss login --cookie-file /path/credential.json`

2. **环境变量**
   - `export BOSS_COOKIES="k=v; k2=v2"`
   - `boss status --json`

3. **Chrome 扩展实时同步**
   - `boss cookie-server`
   - 在 Chrome 中加载 `chrome-extension/zhipin-cookie-extractor`

## License

Apache-2.0
