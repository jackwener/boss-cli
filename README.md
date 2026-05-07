# boss-cli (recruiter fork)

[![PyPI version](https://img.shields.io/pypi/v/kabi-boss-cli.svg)](https://pypi.org/project/kabi-boss-cli/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://pypi.org/project/kabi-boss-cli/)

CLI for BOSS 直聘 **招聘方 (recruiter)** workflows — manage candidates, sync resumes to a local cache, and chat with applicants from the terminal.

> This fork is scoped to recruiter mode. Job-seeker commands still exist in the binary but are not documented here.

## Install

```bash
uv tool install kabi-boss-cli
# or: pipx install kabi-boss-cli
```

From source:

```bash
git clone git@github.com:qianjunye/boss-cli.git
cd boss-cli && uv sync
```

## Auth

```bash
boss login                       # auto-extract cookies from local browser
boss login --cookie-source chrome
boss login --cdp                 # cookies from running Chrome (no QR needed) — recommended
boss login --qrcode              # QR scan fallback
boss status
boss logout
```

### `boss login --cdp` (recommended)

If you've already logged into zhipin.com in a Chrome started with `--remote-debugging-port=9222`, this command reads cookies directly from that browser — **no QR scan**.

1. Launch Chrome with remote debugging:

   ```bash
   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 --user-data-dir=/tmp/boss-chrome
   # Linux
   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/boss-chrome
   ```

2. Log into `https://www.zhipin.com` in that Chrome.
3. `pip install websocket-client` (one-time).
4. `boss login --cdp` (or `--cdp --cdp-port 9333` for a custom port).

Required cookies: `wt2` / `wbg` / `zp_at`. `__zp_stoken__` is treated as optional — it's JS-generated and often unobtainable; recruiter APIs (recommend / inbox / chat / resume-sync) work without it. A few endpoints (search, some chat actions) may return `环境异常` when stoken is missing.

## Recruiter commands

```bash
# Jobs
boss recruiter jobs                                  # list posted jobs
boss recruiter job-close <encryptJobId> --yes
boss recruiter job-reopen <encryptJobId> --yes

# Candidate discovery
boss recruiter recommend --job <encryptJobId>
boss recruiter search "golang" --city 深圳 --exp 3-5年
boss recruiter geek <encryptUid> --job-id <jobId>
boss recruiter resume <encryptUid>
boss recruiter resume-download <encryptUid> --job <jobId>

# Local resume cache (incremental sync) ⭐
export BOSS_CACHE_DIR=./candidates
boss recruiter resume-sync                           # sync all online jobs
boss recruiter resume-sync <encryptJobId>            # sync one job
boss recruiter resume-sync --force                   # full re-fetch
boss recruiter resume-sync --dry-run

# Communication (requires __zp_stoken__)
boss recruiter inbox --job <encryptJobId>
boss recruiter chat <friendId>
boss recruiter reply <friendId> "感谢您的关注..."
boss recruiter greet <encryptGeekId>
boss recruiter request-resume <uid> --yes
boss recruiter exchange-phone <uid> --yes
boss recruiter exchange-wechat <uid> --yes
boss recruiter invite-interview <geekId> --job <id>
boss recruiter mark-unsuitable <geekId> --job <id>

# Export
boss recruiter export -o candidates.csv
boss recruiter export --format json -o out.json
```

### Resume cache layout

```
$BOSS_CACHE_DIR/{encrypt_job_id}/
  _meta.json         # job info, last_sync_at, candidates list
  {encrypt_uid}.md   # one Markdown resume per candidate
```

`resume-sync` is incremental: only new uids are fetched; vanished candidates are marked `archived` (files preserved). 300-person platform cap on the recommend list — periodic sync is how you accumulate a longer history.

## Output

Structured envelope `{ ok, schema_version, data }` for `--json` / `--yaml`. Rich output goes to stderr so pipes stay clean: `boss recruiter jobs --json | jq .data`.

## Use as AI agent skill

```bash
npx skills add qianjunye/boss-cli
# or manually:
git clone git@github.com:qianjunye/boss-cli.git .agents/skills/boss-cli
```

See [`SKILL.md`](./SKILL.md) for the agent contract.

## Troubleshooting

- `环境异常 (__zp_stoken__ 已过期)` → `boss logout && boss login` (use the CDP flow above)
- `code=9` rate-limit → built-in cooldown auto-retries; just wait
- CDP path skipped silently → install `websocket-client`, ensure Chrome is on port 9222 and logged in

## License

Apache-2.0
