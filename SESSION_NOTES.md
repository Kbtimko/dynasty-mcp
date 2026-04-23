# Dynasty MCP — Session Notes
_Last updated: 2026-04-22_

---

## What This App Is
A local Model Context Protocol (MCP) server that gives Claude Code read/write access to Keith's Sleeper dynasty fantasy football league. Exposes 11 tools backed by the Sleeper API and FantasyCalc dynasty values, including a reset optimizer and reset-aware trade finder. Development has transitioned to a companion Next.js web app at `~/projects/dynasty-app`; this repo is in maintenance mode.

**Stack:** Python 3.12, FastMCP, httpx, pytest, Fly.io

**Working directory:** `/Users/keithtimko/projects/dynasty-mcp`

**Run locally (stdio MCP):**
```bash
cd /Users/keithtimko/projects/dynasty-mcp
.venv/bin/python -m dynasty_mcp
```

**Run tests:**
```bash
.venv/bin/pytest -v
```

---

## Config

Config file: `~/.config/dynasty-mcp/config.toml`
```toml
[sleeper]
username = "dakeif"
league_id = "1335327387256119296"
```

Claude Code registration (in `~/.claude.json`):
```json
{
  "mcpServers": {
    "dynasty": {
      "command": "/Users/keithtimko/projects/dynasty-mcp/.venv/bin/python",
      "args": ["-m", "dynasty_mcp"]
    }
  }
}
```

---

## Deployment (Fly.io)

- Live at: `https://dynasty-mcp.fly.dev/mcp` (HTTP transport)
- Config: `fly.toml` in repo root
- VM: 512 MB (bumped from 256 MB to prevent OOM kills)
- **Planned shutdown:** `fly apps destroy dynasty-mcp` once dynasty-app Phase 1 is verified on Vercel

---

## League Reference

- 14-team superflex, 0.5 PPR, TE premium (full 1.0 PPR for TEs)
- Semi-hard reset: protects 1 QB / 1 RB-TE / 1 WR-TE / 3 TAXI per team; traded future picks voided
- Empire pot triggers: back-to-back championships OR 2-of-3 championships + 1-seed in 2-of-3
- Full rules in `docs/league-context.md` and `~/.claude/projects/.../memory/project_league_rules.md`

---

## 2026-04-22
**Completed:** All Phase 1 dynasty-app tasks done including Neon migration (PR #1 `b5c3e69`). HTTP transport deployed to Fly.io (PR #3). `reset_optimizer` and `reset_trades` tools merged. `ConfigError` fix for unknown Sleeper username merged.
**Key Decisions:** Active development moved to `~/projects/dynasty-app`; this repo enters maintenance mode until dynasty-app is verified, then Fly.io instance is destroyed.
**Blockers:** none for this repo; dynasty-app smoke test + Vercel deploy pending
**Next Session:** Verify dynasty-app on Vercel, then run `fly apps destroy dynasty-mcp`
