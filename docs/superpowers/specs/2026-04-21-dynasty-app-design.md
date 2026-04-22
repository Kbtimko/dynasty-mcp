# Dynasty App — Design Spec

**Date:** 2026-04-21
**Status:** Approved

## Problem

The dynasty-mcp MCP server requires an active Claude Code session to access dynasty fantasy football tools. This creates friction: tools are only usable from a desktop with Claude running, not from a phone or another device.

## Solution

A hosted personal web app (`dynasty-app`) that replaces the MCP server entirely. Exposes all 11 tools in a hybrid UI: structured data output with an AI-generated summary at the top of each page.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, App Router |
| Styling | Tailwind 4 |
| Cache / DB | Supabase (replaces SQLite) |
| AI summaries | Anthropic SDK — Sonnet 4.6 (Phase 1), Haiku 4.5 (Phase 2–4) |
| Hosting | Vercel hobby (free) |
| External APIs | Sleeper, FantasyCalc |

**No auth required** — personal use, Supabase service role key is server-side only.

**Config env vars:** `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `SLEEPER_USERNAME=dakeif`, `SLEEPER_LEAGUE_ID=1335327387256119296`

## Architecture

```
Browser
  → Next.js Server Action
      → Sleeper API / FantasyCalc API  (direct HTTP, cache-first)
      → Supabase (check staleness; read/write cache)
      → Anthropic API (Claude generates 2–4 sentence summary)
  → Page: AI Summary card (streaming) + structured data below
```

### Per-page pattern

1. Check Supabase cache (players: 24h TTL, values: 6h TTL)
2. Fetch from external API only if stale
3. Run tool logic (TypeScript port of Python functions)
4. Call Claude with league-aware system prompt + tool output → summary
5. Render: AI Summary card → controls → structured data table/cards
6. "Refresh data" button bypasses cache and regenerates summary

### AI system prompts

Each tool gets a tailored system prompt embedding league rules from `docs/league-context.md`: 0.5 per-1st-down bonus, TE premium (full 1.0 PPR), reset mechanics (1 QB / 1 RB-TE / 1 WR-TE / 3 TAXI), so summaries give specific advice rather than generic fantasy takes.

## Supabase Schema

Replaces the SQLite 4-table schema in `src/dynasty_mcp/cache.py`:

```sql
players          -- id serial PK, data jsonb, updated_at timestamptz
values_snapshots -- id serial PK, data jsonb, updated_at timestamptz
league_snapshot  -- id serial PK, data jsonb, updated_at timestamptz
http_cache       -- url text PK, body text, updated_at timestamptz
```

## Pages & Phases

### Phase 1 — Foundation + Reset Tools
Dashboard, Reset Optimizer, Reset Trades, Team Value Breakdown.
These are the highest-value tools and exercise the full stack (cache, AI, reset math).

### Phase 2 — Player Tools
Player Values, Free Agents + Trending, Matchup.

### Phase 3 — League Views
Transactions, Draft, League Context, All Rosters.

### Phase 4 — Reset Draft *(needs separate brainstorm)*
Draft order / auction value recommendations for the post-reset draft. Spec to be written when Phase 3 ships.

## Reference Files (dynasty-mcp → port to TypeScript)

| Python source | Port target |
|---|---|
| `src/dynasty_mcp/sources/sleeper.py` | `lib/sleeper.ts` |
| `src/dynasty_mcp/sources/fantasycalc.py` | `lib/fantasycalc.ts` |
| `src/dynasty_mcp/cache.py` | `lib/cache.ts` (Supabase) |
| `src/dynasty_mcp/reset_scoring.py` | `lib/reset-scoring.ts` (pure math) |
| `src/dynasty_mcp/tools/reset_optimizer.py` | `lib/tools/reset-optimizer.ts` |
| `src/dynasty_mcp/tools/reset_trades.py` | `lib/tools/reset-trades.ts` |
| `src/dynasty_mcp/tools/rosters.py` | `lib/tools/rosters.ts` |
| `src/dynasty_mcp/tools/values.py` | `lib/tools/values.ts` |
| `src/dynasty_mcp/tools/waivers.py` | `lib/tools/waivers.ts` |
| `src/dynasty_mcp/tools/matchups.py` | `lib/tools/matchups.ts` |
| `src/dynasty_mcp/tools/transactions.py` | `lib/tools/transactions.ts` |
| `src/dynasty_mcp/tools/draft.py` | `lib/tools/draft.ts` |
| `src/dynasty_mcp/tools/league.py` | `lib/tools/league.ts` |
| `src/dynasty_mcp/models.py` | `lib/types.ts` |
| `docs/league-context.md` | Embedded in AI system prompts |

## Deferred

- **League-scoring-adjusted values** (dynasty-mcp TODO #5) — possible toggle on Player Values page post-Phase-2
- **Reset Draft spec** — Phase 4 needs its own brainstorm session
