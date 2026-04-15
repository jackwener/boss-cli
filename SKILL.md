---
name: boss-cli
description: Use boss-cli for ALL BOSS 直聘 operations — searching jobs, viewing recommendations, managing applications, chatting with recruiters, batch greeting, and recruiter/employer mode (managing candidates, syncing resumes to local cache). Invoke whenever the user requests any job search, recruitment, or candidate management on BOSS 直聘.
author: jackwener
version: "0.3.6"
tags:
  - boss
  - zhipin
  - boss直聘
  - job-search
  - recruitment
  - cli
---

# boss-cli — BOSS 直聘 CLI Tool

**Binary:** `boss`
**Credentials:** browser cookies (auto-extracted from 10+ browsers) or QR code login (`--qrcode`)

## Setup

```bash
# Install (requires Python 3.10+)
uv tool install kabi-boss-cli
# Or: pipx install kabi-boss-cli

# Upgrade to latest (recommended)
uv tool upgrade kabi-boss-cli
# Or: pipx upgrade kabi-boss-cli
```

## Authentication

**IMPORTANT FOR AGENTS**: Before executing ANY boss command, check if credentials exist first. Do NOT assume cookies are configured.

### Step 0: Check if already authenticated

```bash
boss status --json 2>/dev/null | jq -r '.authenticated' | grep -q true && echo "AUTH_OK" || echo "AUTH_NEEDED"
```

If `AUTH_OK`, skip to [Command Reference](#command-reference).
If `AUTH_NEEDED`, proceed to Step 1.

### Step 1: Guide user to authenticate

Ensure user is logged into zhipin.com in any supported browser (Chrome, Firefox, Edge, Brave, Arc, Chromium, Opera, Vivaldi, Safari, LibreWolf). Then:

```bash
boss login                              # auto-detect browser with valid cookies
boss login --cookie-source chrome       # specify browser explicitly
boss login --qrcode                     # QR code login — scan with Boss app
```

Verify with:

```bash
boss status
boss me --json | jq '.data.name'
```

### Step 2: Handle common auth issues

| Symptom | Agent action |
|---------|-------------|
| `环境异常 (__zp_stoken__ 已过期)` | Run `boss logout && boss login` |
| `未登录` | Run `boss login` |
| Rate limited (code=9) | Auto-cooldown built-in; wait and retry |
| API timeout | Check network, retry |

## Agent Defaults

All machine-readable output uses the envelope documented in [SCHEMA.md](./SCHEMA.md).
Payloads live under `.data`.

- Non-TTY stdout → auto YAML
- `--json` / `--yaml` → explicit format
- Rich output → **stderr** (safe for pipes: `boss search X --json | jq .data`)

## Command Reference

### Search & Browse

| Command | Description | Example |
|---------|-------------|---------|
| `boss search <keyword>` | Search jobs with filters | `boss search "golang" --city 杭州 --salary 20-30K` |
| `boss show <index>` | View job #N from last search | `boss show 3` |
| `boss detail <securityId>` | View full job details | `boss detail abc123 --json` |
| `boss export <keyword>` | Export search results to CSV/JSON | `boss export "Python" -n 50 -o jobs.csv` |
| `boss recommend` | Personalized recommendations | `boss recommend -p 2 --json` |
| `boss history` | View browsing history | `boss history --json` |
| `boss cities` | List supported cities | `boss cities` |

### Personal Center

| Command | Description | Example |
|---------|-------------|---------|
| `boss me` | View profile (name, age, degree) | `boss me --json` |
| `boss applied` | View applied jobs | `boss applied -p 1 --json` |
| `boss interviews` | View interview invitations | `boss interviews --json` |
| `boss chat` | View communicated bosses | `boss chat --json` |

### Actions

| Command | Description | Example |
|---------|-------------|---------|
| `boss greet <securityId>` | Greet a boss / apply | `boss greet abc123 --json` |
| `boss batch-greet <keyword>` | Batch greet from search | `boss batch-greet "Python" --city 杭州 -n 5` |
| `boss batch-greet <keyword> --dry-run` | Preview without sending | `boss batch-greet "golang" --dry-run` |

### Account

| Command | Description |
|---------|-------------|
| `boss login` | Extract cookies from browser (auto-detect, fallback QR) |
| `boss login --cookie-source <browser>` | Extract from specific browser |
| `boss login --qrcode` | QR code login only (terminal QR output) |
| `boss status` | Check authentication status (shows cookie names) |
| `boss logout` | Clear saved credentials |

## Search Filter Options

| Filter | Flag | Values |
|--------|------|--------|
| City | `--city` | 北京, 上海, 杭州, 深圳, etc. (use `boss cities` for full list) |
| Salary | `--salary` | 3K以下, 3-5K, 5-10K, 10-15K, 15-20K, 20-30K, 30-50K, 50K以上 |
| Experience | `--exp` | 不限, 在校/应届, 1年以内, 1-3年, 3-5年, 5-10年, 10年以上 |
| Degree | `--degree` | 不限, 大专, 本科, 硕士, 博士 |
| Industry | `--industry` | 互联网, 电子商务, 游戏, 人工智能, 金融, 教育培训, 医疗健康, etc. |
| Company Scale | `--scale` | 0-20人, 20-99人, 100-499人, 500-999人, 1000-9999人, 10000人以上 |
| Funding Stage | `--stage` | 未融资, 天使轮, A轮, B轮, C轮, D轮及以上, 已上市, 不需要融资 |
| Job Type | `--job-type` | 全职, 兼职, 实习 |

## Agent Workflow Examples

### Search → Batch Greet pipeline

```bash
# Preview first
boss batch-greet "golang" --city 杭州 --salary 20-30K --dry-run
# Then execute
boss batch-greet "golang" --city 杭州 --salary 20-30K -n 10 -y
```

### Search → Detail pipeline (structured)

```bash
# Search and extract securityId
SEC_ID=$(boss search "golang" --city 杭州 --json | jq -r '.data.jobList[0].securityId')
# Get full detail
boss detail "$SEC_ID" --json | jq '.data.jobInfo | {jobName, salaryDesc, skills}'
```

### Daily job check workflow

```bash
boss recommend --json | jq '.data.jobList | length'  # Check recommendations count
boss search "Python" --city 杭州 --json               # Search specific jobs
boss show 1                                            # View top result details
boss applied --json                                    # Check application status
boss interviews --json                                 # Check interview invitations
boss chat --json                                       # Check messages
boss history --json                                    # Review browsing history
```

### Export pipeline

```bash
boss export "golang" --city 杭州 --salary 20-30K -n 50 -o jobs.csv
boss export "Python" -n 100 --format json -o jobs.json
```

### Profile check

```bash
boss me --json | jq '.data | {name, age, degreeCategory}'
```

## Error Codes

Structured error codes returned in the `error.code` field (see [SCHEMA.md](./SCHEMA.md)):

- `not_authenticated` — cookies expired or missing
- `rate_limited` — too many requests (auto-cooldown built-in)
- `invalid_params` — missing or invalid parameters
- `api_error` — upstream API error
- `unknown_error` — unexpected error

## Recruiter Mode (雇主端)

All recruiter commands live under `boss recruiter <subcommand>`. Requires the same cookie auth as job-seeker mode.

### Candidate Cache Sync (本地缓存同步) ⭐

The most important recruiter workflow for AI analysis. Syncs candidate resumes to local Markdown files so they can be read and analyzed without real-time API calls.

```bash
# Sync all online jobs (incremental — skips already-cached candidates)
boss recruiter sync --output-dir /path/to/workspace/candidates

# Sync a specific job only
boss recruiter sync --job <encryptJobId> --output-dir /path/to/workspace/candidates

# Force full re-fetch (ignore 24h cooldown)
boss recruiter sync --output-dir /path/to/candidates --force

# Preview without writing files
boss recruiter sync --dry-run

# Set default cache dir via env var (openclaw workspace recommended)
export BOSS_CACHE_DIR=/path/to/workspace/candidates
boss recruiter sync
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

**24h cooldown:** Sync skips jobs updated within 24 hours unless `--force` is used.

**Performance:** ~1s per candidate due to built-in rate-limit delay. Initial full sync of 200 candidates ≈ 4 minutes; incremental updates (few new candidates) ≈ 10-30 seconds.

**To analyze cached candidates in openclaw:** Read `.md` files directly from `$BOSS_CACHE_DIR/{encrypt_job_id}/`. Use `_meta.json` to know which candidates exist and when data was last updated.

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

### Recruiter Agent Workflow

```bash
# Step 1: Get job list and encryptJobIds
boss recruiter jobs --json | jq '.data[] | select(.jobOnlineStatus==1) | {jobName, encryptJobId}'

# Step 2: Sync candidates to local cache
export BOSS_CACHE_DIR=./candidates
boss recruiter sync

# Step 3: Analyze from local files (no API needed)
ls ./candidates/{encrypt_job_id}/        # List candidate files
cat ./candidates/{encrypt_job_id}/_meta.json  # Check sync status
cat ./candidates/{encrypt_job_id}/{uid}.md    # Read one resume
```

## Limitations

- **No message sending** — cannot send chat messages (MQTT/Protobuf required)
- **No resume editing** — cannot edit resume from CLI
- **No company search** — company pages return HTML (need __zp_stoken__)
- **Single account** — one set of cookies at a time
- **Rate limited** — batch-greet has built-in 1.5s delay between greetings
- **Communication commands need __zp_stoken__** — obtained only via browser cookie extraction, not QR login

## Anti-Detection Notes for Agents

- **Do NOT parallelize requests** — built-in Gaussian jitter delays exist for account safety
- **Rate-limit auto-recovery**: if code=9 occurs, client auto-cools-down with increasing delays (10s→20s→40s→60s) and retries once
- **Use `-v` flag for debugging**: `boss -v search "Python"` shows request timing
- **Batch greet limit**: recommend ≤ 10 greetings per session to avoid detection
- **Cookies auto-refresh**: if ≥ 7 days old, boss-cli auto-tries browser extraction
- **Re-login if `__zp_stoken__` expires**: run `boss logout && boss login`

## Safety Notes

- Do not ask users to share raw cookie values in chat logs.
- Prefer local browser cookie extraction over manual secret copy/paste.
- If auth fails, ask the user to re-login via `boss login`.
- Agent should treat cookie values as secrets (do not echo to stdout).
- Built-in rate-limit delay protects accounts; do not bypass it.
