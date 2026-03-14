# boss-cli

[![PyPI version](https://img.shields.io/pypi/v/kabi-boss-cli.svg)](https://pypi.org/project/kabi-boss-cli/)
[![CI](https://github.com/jackwener/boss-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jackwener/boss-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://pypi.org/project/kabi-boss-cli/)

A CLI for BOSS 直聘 — search jobs, view recommendations, manage applications, and chat with recruiters via reverse-engineered API 🤝

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

`boss login` auto-extracts browser cookies first, falls back to QR login. Use `--cookie-source chrome` to specify a browser, or `--qrcode` to skip browser detection. The command now verifies the saved credential against a real authenticated API before reporting success.

`boss recommend` follows the live web app's current recommendation data source and request context, which improves compatibility when the legacy recommendation endpoint is rejected.

`boss status --json` now reports per-flow health such as `search_authenticated` and `recommend_authenticated`, which helps diagnose partial-session issues. To avoid turning repeated checks into their own anti-bot problem, health snapshots are cached briefly in-memory.

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
    └── social.py         # chat, greet (--json), batch-greet (1.5s delay)
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

## 使用示例

```bash
# 认证
boss login                             # 自动提取浏览器 Cookie，失败则二维码
boss login --cookie-source chrome      # 指定浏览器
boss status                            # 检查登录状态
boss logout                            # 清除 Cookie

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

## 常见问题

- `环境异常` — Cookie 过期，执行 `boss logout && boss login` 刷新
- 搜索无结果 — 检查城市筛选或关键词，使用 `boss cities` 查看支持的城市

## License

Apache-2.0
