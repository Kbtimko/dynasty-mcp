# dynasty-mcp — Implementation Status

**As of:** 2026-04-19
**Branch:** `implement-v1`
**Plan:** `docs/superpowers/plans/2026-04-19-dynasty-mcp-v1.md`
**Spec:** `docs/superpowers/specs/2026-04-19-dynasty-mcp-design.md`

## Done

- **Task 1 — Project scaffold** (`5373589`, `c7038f3`): `pyproject.toml` (fastmcp, httpx, pydantic, platformdirs; dev: pytest, pytest-asyncio, respx), `.gitignore`, `src/` layout with empty `__init__.py` files, stub `__main__.py`, venv at `.venv/` (Python 3.12 via Homebrew).
- **Task 2 — TOML config loader** (`94ba278`, `c0db335`): `src/dynasty_mcp/config.py` with `Config` frozen dataclass, `load_config()`, `ConfigError`. Rejects missing or whitespace-only username, wraps int-cast errors as `ConfigError`. 6 tests in `tests/test_config.py`.
- **Task 3 — SQLite cache layer** (`19c16be`, `9dcd711`): `src/dynasty_mcp/cache.py` — `Cache` dataclass, 4-table schema (players, values_snapshots, league_snapshot, http_cache), round-trip methods, `players_stale()` / `values_stale()` helpers. Rejects naive datetimes at write time. 8 tests in `tests/test_cache.py`.
- **Task 4 — Pydantic models** (`e2d9718`): `src/dynasty_mcp/models.py` — `SlotType` enum, `Player`, `Value`, `RosterEntry`, `RosterView`, `LeagueContext`, `StaleFlag`. 4 tests in `tests/test_models.py`.

**Full suite:** 18 passing (6 config + 8 cache + 4 models).

Each task went through implementer → spec reviewer → code quality reviewer loop; fixes applied where latent bugs were found (tz-aware datetimes, ConfigError contract, whitespace username).

## Paused Before

**Task 5 — Fixture recording script.** Read the plan, did not dispatch the implementer. This task hits live Sleeper + FantasyCalc APIs using credentials `dakeif` / `1335327387256119296` and writes ~16 JSON fixtures to `tests/fixtures/`. Resume by dispatching the Task 5 implementer; credentials will flow to the subagent via env vars in the recording command.

## Left

- **Task 5** — Record live fixtures from Sleeper + FantasyCalc.
- **Task 6** — Sleeper API client (`sources/sleeper.py`) with retry + cache fallback.
- **Task 7** — FantasyCalc API client (`sources/fantasycalc.py`).
- **Tasks 8–17** — 10 primitive MCP tools + `refresh_cache`: `get_league_context`, `get_roster`, `list_rosters`, `get_player_values`, `get_matchup`, `get_free_agents`, `get_trending`, `get_transactions`, `get_draft`, `get_team_value_breakdown`, `refresh_cache`.
- **Task 18** — FastMCP server wiring + entrypoint.
- **Task 19** — README + Claude Code `mcpServers` registration snippet.
- **Task 20** — Manual live contract test against the real league.
- **Final** — End-to-end code review across the branch.

## Open Questions / Deferred Decisions

These were surfaced by code reviews but consciously deferred per YAGNI + plan intent. Revisit when their first real consumer lands.

- **`Cache.get_league_snapshot()`** — writer exists, reader does not. The plan deferred it. Add when the first tool needs to read league snapshots back (likely Task 10 `list_rosters` or Task 17 `get_team_value_breakdown`).
- **`values_stale()` untested** — identical logic to `players_stale()` but not exercised. Add a test when the FantasyCalc client (Task 7) uses it.
- **`Value.current: int | None` is required (no default)** — if a FantasyCalc response omits a player's value, callers must pass `current=None` explicitly or pydantic raises. Consider adding `= None` after Task 7 shows whether this is real friction.
- **Unused `Field` import in `models.py`** — plan keeps it for future validators. No linter configured yet; will need `# noqa: F401` or removal once linting is added.
- **`SlotType` + `model_dump()` serialization** — `model_dump()` returns enum objects, `model_dump(mode='json')` returns strings. Tool authors in Tasks 8–17 need to use `mode='json'` for MCP responses. Document in Task 18 (server wiring) or when building the first tool.
- **`Cache.close()`** — no explicit close/WAL-checkpoint hook. Fine for v1; revisit if the MCP server lifecycle (Task 18) needs orderly shutdown.
- **`list_tables()` synthetic `"values"` alias** — internal table is `values_snapshots`; `list_tables()` injects a virtual `"values"` to match the spec's outward-facing name. Footgun if a future caller expects to `SELECT FROM <name>` the result. Only used by the schema test today.
- **`INSERT OR REPLACE` vs `ON CONFLICT` inconsistency** — `http_cache` uses `INSERT OR REPLACE`; `league_snapshot` uses `ON CONFLICT DO UPDATE`. Not a bug (no AUTOINCREMENT on `http_cache`), just inconsistent.

## How to Resume

```bash
cd ~/projects/dynasty-mcp
git status                      # confirm clean on implement-v1
git log --oneline -10           # confirm head at 9dcd711 or e2d9718
.venv/bin/pytest -v             # confirm 18 passing
```

Then in Claude: "resume subagent-driven execution of the dynasty-mcp plan at Task 5." The controller re-reads the plan + this file and dispatches the Task 5 implementer.
