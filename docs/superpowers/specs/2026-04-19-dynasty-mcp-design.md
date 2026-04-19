# dynasty-mcp: Design Spec

**Date:** 2026-04-19
**Status:** Approved for implementation planning

## Purpose

A local Model Context Protocol (MCP) server that gives Claude read-only access to a user's Sleeper-hosted empire-format dynasty fantasy football league, augmented with dynasty trade values from FantasyCalc. The server exposes thin data primitives; Claude composes them to answer questions about trades, lineups, waivers, rookie drafts, and long-term roster strategy.

The league in question is an empire dynasty league on Sleeper. Long-term roster strategy must account for **taxi squad management** (young-player stashing off the active roster) in addition to standard contend-vs-rebuild decisions.

## Scope

### v1 supports

- Trade evaluation ("should I do this trade?")
- Trade-partner scouting (who's overvalued/undervalued vs the market; who to shop)
- Weekly lineup decisions (start/sit, matchup projections)
- Waiver and free-agent pickups
- Rookie draft prep (pick ownership, rookie values, board during the draft)
- Long-term roster strategy including taxi squad
- League scouting (reading opponents' rosters to find trade partners)

### v1 explicitly excludes

- Thick opinionated tools (`evaluate_trade`, `recommend_lineup`, `suggest_waivers`) — will be added in v2 once usage patterns stabilize
- HTTP transport for co-owner access — v1 is local stdio only; FastMCP supports both transports so migration is a small refactor
- KeepTradeCut values (no public API; scraping is fragile)
- FantasyPros rankings (paid)
- Dedicated injury/news feeds beyond Sleeper's player status field
- IDP-specific data
- Web UI

## Architecture

```
Claude Code ──(stdio MCP)──▶ dynasty-mcp (Python, FastMCP)
                                  ├──▶ Sleeper API (public, unauth)
                                  ├──▶ FantasyCalc API (public, unauth)
                                  └──▶ SQLite cache (platformdirs user data dir)
```

- **Runtime:** Python 3.12+, FastMCP framework
- **Transport:** stdio (local), launched by Claude Code via the `mcpServers` config
- **Auth:** none required — both upstream APIs are public read-only
- **State:** local SQLite cache only; no server-side state, no user accounts
- **Shape:** hybrid thin-first — v1 exposes data primitives; v2 may add thick tools once usage patterns are clear

## Data sources

### Sleeper API (`https://api.sleeper.app/v1/`)

Used for all league state: settings, rosters, users, matchups, transactions, traded picks, drafts, trending adds/drops, NFL state, and weekly projections. The global players dataset (~5MB JSON) is fetched once and cached locally.

### FantasyCalc API (`https://api.fantasycalc.com/values/current`)

Used for dynasty trade values. Parameters (`isDynasty`, `numQbs`, `numTeams`, `ppr`) are auto-derived from the Sleeper league settings on startup so values match the league format.

### Local SQLite cache

Path: `platformdirs.user_data_dir("dynasty-mcp")` (macOS: `~/Library/Application Support/dynasty-mcp/cache.db`).

Tables:
- `players` — full Sleeper player dataset, refreshed weekly
- `values` — FantasyCalc snapshots with timestamps; enables week-over-week delta queries
- `league_snapshot` — weekly roster snapshots per team; enables "what changed" and long-term scouting
- `http_cache` — ETag / Last-Modified records for polite API usage

## v1 tool inventory

Ten thin primitives. Claude composes them to answer user questions.

| Tool | Returns | Primary use cases |
|---|---|---|
| `get_league_context` | Settings, scoring, roster/taxi slots, user's roster_id, current NFL week, season phase | all |
| `get_roster(team)` | Active + taxi + IR players with FantasyCalc values, ages, status | trade eval, lineup, long-term strategy |
| `list_rosters()` | Every team summarized: owner, total roster value, top 5 assets | scouting, finding trade partners |
| `get_player_values(position?, rookies_only?, trending_window?, limit?)` | FantasyCalc values with week-over-week deltas | trade eval, finding targets |
| `get_matchup(week?)` | User's starters + projections, opponent's starters, bench value | lineup decisions |
| `get_free_agents(position?, min_value?, limit?)` | Unrostered players, sorted by value | waivers |
| `get_transactions(days=7, type?)` | Recent trades/waivers/adds in the league | scouting, market signals |
| `get_trending(window="24h"\|"7d", type="add"\|"drop")` | Sleeper's global NFL-wide trending signal | waivers |
| `get_draft(year?)` | User's picks, traded picks, draft order, rookie pool with values | rookie draft prep and live draft |
| `get_team_value_breakdown(team)` | Value totals by position and age cohort (under-25, 25–28, 29+) | long-term strategy, contend-vs-rebuild |

### Shared parameter semantics

- **`team`** (used by `get_roster`, `get_team_value_breakdown`): accepts one of `"me"`, an integer Sleeper `roster_id`, or a Sleeper **username** (not display name — usernames are unique league-wide). Invalid input returns a clear error listing valid values.
- **`week`**: omitted → current NFL week during the regular season; during offseason, defaults to the most recent completed week and returns a `season_phase="offseason"` flag.
- **`year`** (for `get_draft`): omitted → the next scheduled draft; if none, returns the most recent completed draft with a `status="completed"` flag.

Plus one operational tool:

- `refresh_cache(what="players"\|"values"\|"all")` — forces a cache refresh mid-conversation.

### Taxi squad handling

- `get_roster` flags each player with `slot_type` ∈ {`active`, `taxi`, `ir`, `bench`}.
- `get_team_value_breakdown` reports taxi-stash value separately from active-roster value so contend-vs-rebuild decisions can weight them correctly.

### Composition examples

- *"Should I trade Player X for pick 1.03 plus Player Y?"* → `get_player_values` for both sides + `get_draft` for pick value + `get_team_value_breakdown` for positional context.
- *"Who should I shop?"* → `get_roster(me)` to find surplus + `list_rosters` + `get_team_value_breakdown` per team to find positional holes that match.
- *"Who should I start week 12?"* → `get_matchup` + player status from `get_roster`.

## Configuration

File: `~/.config/dynasty-mcp/config.toml`

```toml
[sleeper]
username = "your_sleeper_username"
league_id = "123456789012345678"  # optional if username resolves to exactly one league

[values]
source = "fantasycalc"
# numQbs, ppr, teams auto-derived from league settings
override = {}

[cache]
# path is optional; defaults to platformdirs.user_data_dir("dynasty-mcp") + "/cache.db"
# path = "~/Library/Application Support/dynasty-mcp/cache.db"
players_refresh_days = 7
values_refresh_hours = 24
```

Claude Code registration (`~/.claude.json` `mcpServers` block):

```json
{
  "mcpServers": {
    "dynasty": {
      "command": "python",
      "args": ["-m", "dynasty_mcp"]
    }
  }
}
```

## Project structure

```
dynasty-mcp/
├── pyproject.toml              # fastmcp, httpx, platformdirs, pydantic, pytest, respx
├── README.md
├── src/dynasty_mcp/
│   ├── __main__.py             # entrypoint: `python -m dynasty_mcp`
│   ├── server.py               # FastMCP app + tool registration
│   ├── config.py               # TOML loader, platformdirs paths
│   ├── cache.py                # SQLite schema + HTTP cache helpers
│   ├── sources/
│   │   ├── sleeper.py          # Sleeper API client
│   │   └── fantasycalc.py      # FantasyCalc client
│   ├── models.py               # pydantic: Player, Roster, LeagueContext, Value, Matchup
│   └── tools/
│       ├── league.py            # get_league_context
│       ├── rosters.py           # get_roster, list_rosters, get_team_value_breakdown
│       ├── values.py            # get_player_values
│       ├── matchups.py          # get_matchup
│       ├── waivers.py           # get_free_agents, get_trending
│       ├── transactions.py      # get_transactions
│       ├── draft.py             # get_draft
│       └── admin.py             # refresh_cache
└── tests/
    ├── fixtures/               # recorded Sleeper + FantasyCalc responses
    ├── test_sleeper.py
    ├── test_fantasycalc.py
    └── test_tools/             # one file per tool module
```

One module per tool group. `sources/` isolates API clients so tests use recorded fixtures rather than live HTTP.

## Caching and freshness

- **Sleeper player dataset:** refresh weekly (Sleeper recommends no more than daily).
- **FantasyCalc values:** refresh every 24h; keep timestamped snapshots for week-over-week deltas.
- **Rosters, matchups, transactions:** fetch live on each call; honor `If-Modified-Since` / ETag where available.
- **Manual refresh:** `refresh_cache` MCP tool forces an update mid-conversation.

## Error handling

- **Sleeper API down:** return cached data with `stale=true` and `as_of=<timestamp>` fields so Claude can disclose to the user.
- **FantasyCalc missing a player** (e.g., post-draft rookies before next update): return the player with `value=null`; never fail the tool.
- **Invalid or missing config:** MCP startup fails loudly with a clear message naming the missing field.
- **Transient network errors:** one retry with backoff, then surface the error. No silent fallbacks or hidden retry loops.

## Testing approach

- **Client tests:** fixture-based. A one-time recording script hits real Sleeper + FantasyCalc and saves JSON under `tests/fixtures/`. Client tests replay those via `respx`. Re-record quarterly or when endpoints change.
- **Tool tests:** run against a seeded SQLite cache populated from fixtures. Each tool gets a happy-path test plus one edge case (bye week for `get_matchup`, no-draft-scheduled for `get_draft`, etc.).
- **Contract test:** a manually-run test against the user's real Sleeper league verifies live-API assumptions. Not part of CI.
- **TDD discipline:** write the test against a fixture first, then implement the tool. Enforced by the `superpowers:test-driven-development` workflow.

## Future work (post-v1)

- **Thick tools:** promote repeated query patterns into deterministic tools — `evaluate_trade(send, receive)`, `find_trade_targets()`, `recommend_lineup(week)`, `suggest_waivers()`.
- **HTTP transport for co-owners:** refactor to FastMCP HTTP/SSE, deploy to Vercel/Fly/Railway, add per-user API keys. Share a trade-scenario/notes store across co-owners.
- **Secondary value source:** layer in DynastyProcess CSV data for a second opinion blended with FantasyCalc.
- **Richer injury/news feed** if Sleeper's player status field proves insufficient.
- **Live-draft assistant mode** with low-latency recommendations during the rookie draft.

## Success criteria

v1 is done when:

1. All ten primitive tools + `refresh_cache` are implemented with passing fixture-based tests.
2. The server registers cleanly in Claude Code and returns accurate live data for the user's real league.
3. Claude can correctly answer one realistic question from each of the seven v1 use cases using only composed primitives.
4. Cache survives server restart and respects refresh windows.
5. Running with invalid config fails with a clear error; running with the upstream APIs unreachable returns stale data with the `stale` flag set.
