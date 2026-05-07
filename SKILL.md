---
name: boss-cli
description: Use boss-cli for BOSS 直聘 recruiter/employer operations — managing posted jobs, discovering candidates, syncing resumes to a local cache for AI analysis, and communicating with candidates. Invoke whenever the user requests any recruitment or candidate management on BOSS 直聘.
author: jackwener
version: "0.3.6"
tags:
  - boss
  - zhipin
  - boss直聘
  - recruitment
  - recruiter
  - cli
---

# boss-cli — BOSS 直聘 招聘者 CLI

**Binary:** `boss`
**Scope of this skill:** recruiter (雇主端) commands only. Job-seeker commands exist but are not covered here.
**Credentials:** browser cookies (auto-extracted from 10+ browsers) or QR code login (`--qrcode`)

## Setup

```bash
# Install (requires Python 3.10+)
uv tool install kabi-boss-cli
# Or: pipx install kabi-boss-cli

# Upgrade to latest
uv tool upgrade kabi-boss-cli
```

## Authentication

**IMPORTANT FOR AGENTS**: Before executing ANY boss command, check if credentials exist first.

### Step 0: Check if already authenticated

```bash
boss status --json 2>/dev/null | jq -r '.authenticated' | grep -q true && echo "AUTH_OK" || echo "AUTH_NEEDED"
```

If `AUTH_OK`, skip to [Recruiter Commands](#recruiter-commands).
If `AUTH_NEEDED`, proceed to Step 1.

### Step 1: Guide user to authenticate

Ensure user is logged into zhipin.com (recruiter account) in any supported browser. Then:

```bash
boss login                              # auto-detect browser with valid cookies
boss login --cookie-source chrome       # specify browser explicitly
boss login --qrcode                     # QR code login — scan with Boss app
```

Verify with:

```bash
boss status
```

### Step 2: Handle common auth issues

| Symptom | Agent action |
|---------|-------------|
| `环境异常 (__zp_stoken__ 已过期)` | Run `boss logout && boss login` |
| `未登录` | Run `boss login` |
| Rate limited (code=9) | Auto-cooldown built-in; wait and retry |
| API timeout | Check network, retry |

## Agent Defaults

All machine-readable output uses the envelope documented in [SCHEMA.md](./SCHEMA.md). Payloads live under `.data`.

- Non-TTY stdout → auto YAML
- `--json` / `--yaml` → explicit format
- Rich output → **stderr** (safe for pipes: `boss recruiter jobs --json | jq .data`)

## Recruiter Commands

All recruiter commands live under `boss recruiter <subcommand>`.

### Candidate Cache Sync (本地缓存同步) ⭐

The most important recruiter workflow for AI analysis. Syncs candidate resumes to local Markdown files so they can be read and analyzed without real-time API calls.

```bash
# Sync all online jobs (incremental — skips already-cached candidates)
boss recruiter resume-sync

# Sync a specific job only
boss recruiter resume-sync <encryptJobId>

# Specify output directory
boss recruiter resume-sync <encryptJobId> --output-dir /path/to/workspace/candidates

# Force full re-fetch
boss recruiter resume-sync --force

# Preview without writing files
boss recruiter resume-sync --dry-run

# Set default cache dir via env var
export BOSS_CACHE_DIR=/path/to/workspace/candidates
boss recruiter resume-sync
```

**Cache directory structure:**
```
$BOSS_CACHE_DIR/
  /{encrypt_job_id}/
    _meta.json          # Job info + last sync time + candidate uid list
    /{encrypt_uid}.md   # Candidate resume in Markdown format
```

**_meta.json fields:** `job_name`, `encrypt_job_id`, `salary_desc`, `last_sync_at`, `total_candidates`, `new_this_sync`, `archived_candidates`, `candidates`

**Incremental logic:** Only fetches candidates whose `encrypt_uid` is not already present in `_meta.json`. Candidates who disappear from the recommend list are marked `archived` (files kept).

**Performance:** ~1s per candidate due to built-in rate-limit delay. Initial full sync of 200 candidates ≈ 4 minutes; incremental updates (few new candidates) ≈ 10-30 seconds.

**To analyze cached candidates:** Read `.md` files directly from `$BOSS_CACHE_DIR/{encrypt_job_id}/`. Use `_meta.json` to know which candidates exist and when data was last updated.

### Job Management

```bash
boss recruiter jobs                                    # List posted jobs (encryptJobId needed for sync)
boss recruiter jobs --json                             # JSON output
```

### Candidate Discovery

```bash
boss recruiter recommend --job <encryptJobId>          # Candidates who greeted this job (platform-sorted)
boss recruiter search "政府事务" --city 上海            # Active search for candidates
boss recruiter geek <encryptUid> --job-id <jobId>      # View one candidate's detail
boss recruiter resume <encryptUid>                     # View full resume in terminal
boss recruiter resume-download <encryptUid> --job <id> # Download resume as Markdown
```

### Communication (requires __zp_stoken__)

```bash
boss recruiter inbox --job <encryptJobId>              # Candidates who messaged you
boss recruiter reply <friendId> "消息内容"              # Reply to candidate
boss recruiter chat <friendId>                         # View chat history
boss recruiter greet <encryptGeekId>                   # Initiate chat with candidate
boss recruiter request-resume <uid> --yes              # Request resume from candidate
boss recruiter exchange-phone <uid> --yes              # Exchange phone number
boss recruiter invite-interview <geekId> --job <id>    # Invite for interview
boss recruiter mark-unsuitable <geekId> --job <id>     # Mark as unsuitable
```

### Export

```bash
boss recruiter export -o candidates.csv                # Export candidate list to CSV
boss recruiter export --format json -o out.json        # Export as JSON
```

## Recruiter Agent Workflow

```bash
# Step 1: Get job list and encryptJobIds
boss recruiter jobs --json | jq '.data[] | select(.jobOnlineStatus==1) | {jobName, encryptJobId}'

# Step 2: Sync candidates to local cache
export BOSS_CACHE_DIR=./candidates
boss recruiter resume-sync

# Step 3: Analyze from local files (no API needed)
ls ./candidates/{encrypt_job_id}/             # List candidate files
cat ./candidates/{encrypt_job_id}/_meta.json  # Check sync status
cat ./candidates/{encrypt_job_id}/{uid}.md    # Read one resume
```

## Error Codes

Structured error codes returned in the `error.code` field (see [SCHEMA.md](./SCHEMA.md)):

- `not_authenticated` — cookies expired or missing
- `rate_limited` — too many requests (auto-cooldown built-in)
- `invalid_params` — missing or invalid parameters
- `api_error` — upstream API error
- `unknown_error` — unexpected error

## Limitations

- **No message sending via MQTT** — only HTTP-based reply/greet
- **Single account** — one set of cookies at a time
- **Rate limited** — built-in delays between requests
- **Communication commands need __zp_stoken__** — obtained via browser cookie extraction or CDP hydration, not pure QR login

## Anti-Detection Notes for Agents

- **Do NOT parallelize requests** — built-in Gaussian jitter delays exist for account safety
- **Rate-limit auto-recovery**: if code=9 occurs, client auto-cools-down (10s→20s→40s→60s) and retries once
- **Use `-v` flag for debugging**: `boss -v recruiter jobs` shows request timing
- **Cookies auto-refresh**: if ≥ 7 days old, boss-cli auto-tries browser extraction
- **Re-login if `__zp_stoken__` expires**: run `boss logout && boss login`

## Safety Notes

- Do not ask users to share raw cookie values in chat logs.
- Prefer local browser cookie extraction over manual secret copy/paste.
- Treat cookie values as secrets (do not echo to stdout).
- Built-in rate-limit delay protects accounts; do not bypass it.

## 候选人缓存策略说明（Agent 必读）

### 300人上限问题
BOSS直聘推荐列表每次最多返回 **300 人**，翻页返回相同数据（无效翻页）。
这是平台硬限制，无法突破。

### 正确的增量同步策略
- 推荐列表会**动态变化**：新候选人投递后会出现，旧的会消失
- `resume-sync` 的增量逻辑：将新出现的 uid 与本地 `_meta.json` 中的 `candidates` 列表对比
- 消失的候选人标记为 `archived`，简历文件**保留不删除**
- 定期同步可以积累超过300人的历史候选人库

### 建议同步频率
- 热门岗位（候选人多）：每天同步 1 次
- 一般岗位：每 2-3 天同步 1 次
- 使用 `--force` 强制覆盖时，会重新拉取当前推荐列表中的所有人
