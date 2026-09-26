# dynasty-mcp

Local MCP server giving Claude access to Keith's Sleeper dynasty fantasy football league.

## Session start

Read `.claude/notes.md` first — it has current state, blockers, and the prioritized backlog.

## Adding a new MCP tool

1. **Pure logic** → `src/dynasty_mcp/tools/<module>.py` (or a standalone pure module like `reset_scoring.py` for math-heavy work with zero I/O)
2. **Wire** → `src/dynasty_mcp/server.py` with `@mcp.tool()` decorator; call `.model_dump(mode='json')` on the result before returning (MCP transport requires a JSON-serializable dict, not a Pydantic model)
3. **Test** → `tests/test_tools/test_<module>.py` with fixture-seeded `Context` + respx HTTP mocking

## Test conventions

- TDD: write a failing test against a recorded fixture first, then implement
- All HTTP calls mocked via respx; no live network in unit tests
- Live-test file: `tests/test_contract.py` — gated by `DYNASTY_LIVE=1` env var
- Fixtures at `tests/fixtures/` — recorded once from real APIs, replayed in tests
- Run targeted: `pytest tests/test_tools/test_<module>.py -v`
- Run full suite: `pytest -v`

## League reference

For scoring rules, reset mechanics, TAXI rules, and roster context: [`docs/league-context.md`](docs/league-context.md)

Load this when doing strategy or advisory work. Skip it for infrastructure tasks (cache, config, tests).

## Database

If any tool or feature needs persistent storage, use **Neon Postgres** (not Supabase). Neon project: create one at neon.tech when needed. Use `@neondatabase/serverless` for the client in Next.js contexts; use `psycopg2` or `asyncpg` in Python.

## Key files

| File | Purpose |
|---|---|
| `src/dynasty_mcp/server.py` | Tool registration (`@mcp.tool()` wiring) |
| `src/dynasty_mcp/models.py` | All Pydantic models |
| `src/dynasty_mcp/reset_scoring.py` | Pure reset math (no I/O) |
| `src/dynasty_mcp/tools/` | One file per tool group |
| `src/dynasty_mcp/sources/` | Sleeper + FantasyCalc API clients |
| `.claude/notes.md` | Current state, blockers, prioritized backlog |
| `.claude/sessions/` | Per-session journal, one file per session |
| `SESSION_NOTES.md` | Frozen archive — historical reference only |
| `STATUS.md` | Frozen archive — historical reference only |

**Don't load without a reason:** `tests/fixtures/*.json` — large recorded API responses; only useful when debugging specific fixture data.

## Definition of Done

Before declaring any fix complete:
- Enumerate the edge cases the change must handle (missing/zero values, empty sets, excluded/filtered records, boundary & off-by-one cases) and confirm each is covered — make the enumeration visible, not implicit.
- Validate behavior against the real data source or live app, not just unit tests — a green test is not a working feature.
- Name the root cause, not just the surface patch; if the fix papers over a deeper data/pipeline gap, say so.
