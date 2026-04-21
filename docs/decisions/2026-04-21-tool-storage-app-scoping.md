# Tool-Storage App: Architecture Decision

**Date:** 2026-04-21  
**Status:** Decided — Option C (Phase 1), Option A (Phase 2 if needed)

## Problem

The dynasty-mcp MCP server runs in stdio mode, making tools accessible only inside an active Claude Code session on a local machine. Goal: access tools from any device (phone, tablet, browser) without opening Claude Code, at minimal hosting cost.

## Options Considered

### Option A — FastMCP HTTP + thin Next.js frontend

Deploy the Python server over HTTP (one-line change in FastMCP), build a thin Next.js display layer on Vercel that calls it.

- **Pro:** Claude integration preserved; zero logic duplication; familiar Next.js/Vercel stack
- **Con:** Two services to manage; Python hosting required (~$0–$10/month on Fly.io/Cloud Run)

### Option B — Rewrite logic as Next.js API routes

Port all 12 tools to TypeScript, deploy to Vercel. No Python hosting.

- **Pro:** Single deployment, no Python infra
- **Con:** All business logic duplicated; every new tool written twice; Claude MCP integration lost
- **Rejected** — forks the codebase and removes advisory capability

### Option C — claude.ai remote MCP (chosen)

Switch the Python server to HTTP transport, deploy it publicly (Fly.io free tier or Google Cloud Run), and register it as a remote MCP server on claude.ai.

- **Local machine not required** — claude.ai calls the hosted server directly; your laptop can be off
- **Pro:** No frontend to build; Claude can reason and advise, not just display; $0 additional cost; ~1 day of effort
- **Con:** Conversational UI, not a dashboard; relies on claude.ai's remote MCP support

## Decision

**Phase 1 (implement now):** Option C.  
Switch to HTTP transport, deploy to Fly.io free tier, register with claude.ai. Unlocks full mobile access at zero cost with no frontend work.

**Phase 2 (if needed):** Option A.  
If a dedicated dashboard UI proves useful (roster snapshot without asking Claude a question), add a thin Next.js frontend on Vercel. Logic stays in Python — no duplication required.

## Phase 1 Implementation Steps

1. Add `transport`, `host`, and `port` fields to `Config` dataclass in `src/dynasty_mcp/config.py` (defaults: `stdio`, `0.0.0.0`, `8000`)
2. Pass `transport`, `host`, `port` to `server.run()` in `src/dynasty_mcp/__main__.py`
3. Add `[server]` section to `~/.config/dynasty-mcp/config.toml` schema
4. Write a `Dockerfile` + `fly.toml` for Fly.io deployment
5. Deploy to Fly.io free tier
6. Register the public endpoint with claude.ai as a remote MCP server
7. Smoke-test all 12 tools via claude.ai on mobile
