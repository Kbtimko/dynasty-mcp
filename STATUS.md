# Dynasty MCP — Status as of 2026-04-22

## Current State
The MCP server is fully built, deployed to Fly.io (dynasty-mcp.fly.dev/mcp), and wired into Claude Code via stdio. It is feature-complete for v1 (11 tools including `reset_optimizer` and `reset_trades`). Active development has shifted to a companion Next.js app (`~/projects/dynasty-app`) that wraps the same logic in a web UI — the MCP server is in maintenance mode until dynasty-app Phase 1 is verified on Vercel.

## Recent Work
- Implemented `reset_optimizer` MCP tool: pure `reset_scoring.py` module + async tool wrapper, 75 tests passing, merged to `main` via PR #1
- Implemented `reset_trades` MCP tool (merged via PR #2 per git log)
- Added HTTP transport + Fly.io deployment (PR #3 merged, live at dynasty-mcp.fly.dev/mcp)
- Bumped Fly.io VM to 512 MB to prevent OOM kills
- Added `ConfigError` for unknown Sleeper username; fixed bare `dakeif` name bug in `__main__.py`
- Wrote dynasty-app Phase 1 implementation plan (`docs/superpowers/plans/2026-04-21-dynasty-app.md`)
- dynasty-app Phase 1: all tasks complete including Neon migration (Task 1 merged at PR #1 `b5c3e69`)

## Open Blockers
- dynasty-app Phase 1 needs smoke test + Vercel deploy before the Fly.io instance can be destroyed
- Fly.io is still running and incurring cost — shut down with `fly apps destroy dynasty-mcp` after dynasty-app is verified

## Next Up
1. In `~/projects/dynasty-app`: run `npm test` + `npx tsc --noEmit`, then add `DATABASE_URL` + `ANTHROPIC_API_KEY` to Vercel env vars and deploy
2. Smoke-test all four dynasty-app pages (Dashboard, Reset Optimizer, Reset Trades, Team Value Breakdown)
3. `fly apps destroy dynasty-mcp` once dynasty-app is confirmed working on Vercel
4. League-scoring-adjusted values — deferred; candidate for dynasty-app Phase 2

## Key Context
- Config lives at `~/.config/dynasty-mcp/config.toml` — `username = "dakeif"`, `league_id = "1335327387256119296"`
- MCP server registered in `~/.claude.json` (stdio transport: `.venv/bin/python -m dynasty_mcp`)
- League: 14-team superflex, 0.5 PPR, TE premium (full 1.0 PPR); semi-hard reset protects 1 QB / 1 RB-TE / 1 WR-TE / 3 TAXI; traded future picks voided on reset
- All future dynasty work is in `~/projects/dynasty-app` — see that project's NOTES.md for authoritative status
- Run tests: `.venv/bin/pytest -v` (75 passing on `main`)
