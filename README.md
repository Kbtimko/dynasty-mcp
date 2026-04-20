# dynasty-mcp

Local Model Context Protocol (MCP) server for managing a Sleeper dynasty fantasy football league. Exposes read-only tools backed by the Sleeper API and FantasyCalc dynasty values. See `docs/superpowers/specs/` for the design spec.

## Install

```bash
git clone <this-repo> ~/projects/dynasty-mcp
cd ~/projects/dynasty-mcp
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Configure

```bash
mkdir -p ~/.config/dynasty-mcp
cp examples/config.toml ~/.config/dynasty-mcp/config.toml
# Edit ~/.config/dynasty-mcp/config.toml and set sleeper.username (and optionally league_id)
```

## Register with Claude Code

Add to `~/.claude.json` (or your project's `.claude/mcp.json`):

```json
{
  "mcpServers": {
    "dynasty": {
      "command": "/Users/<you>/projects/dynasty-mcp/.venv/bin/python",
      "args": ["-m", "dynasty_mcp"]
    }
  }
}
```

Restart Claude Code. The `dynasty` server should appear and expose 11 tools.

## Tools

- `get_league_context` — settings, scoring, roster/taxi slots, current week
- `get_roster` — one team's roster with values and slot types (active, taxi, IR, bench)
- `list_rosters` — summary of every team
- `get_team_value_breakdown` — value by position and age cohort; taxi stash separated
- `get_player_values` — ranked FantasyCalc values with week-over-week delta
- `get_matchup` — your matchup for a week with best-effort projections
- `get_free_agents` — unrostered players ranked by value
- `get_trending` — Sleeper's global trending adds/drops
- `get_transactions` — recent league trades, waivers, adds
- `get_draft` — next draft's picks and rookie pool
- `refresh_cache` — force refresh of the players dataset and/or FantasyCalc values

## Development

Run the tests:

```bash
.venv/bin/pytest -v
```

Re-record fixtures (quarterly or when APIs change):

```bash
SLEEPER_USERNAME=<you> SLEEPER_LEAGUE_ID=<id> .venv/bin/python scripts/record_fixtures.py
```
