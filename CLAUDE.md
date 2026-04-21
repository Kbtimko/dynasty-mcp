# dynasty-mcp

Local MCP server giving Claude access to Keith's Sleeper dynasty fantasy football league.

## Session start

Read `NOTES.md` first — it has current state, outstanding work, and carry-forward items.

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

## Key files

| File | Purpose |
|---|---|
| `src/dynasty_mcp/server.py` | Tool registration (`@mcp.tool()` wiring) |
| `src/dynasty_mcp/models.py` | All Pydantic models |
| `src/dynasty_mcp/reset_scoring.py` | Pure reset math (no I/O) |
| `src/dynasty_mcp/tools/` | One file per tool group |
| `src/dynasty_mcp/sources/` | Sleeper + FantasyCalc API clients |
| `NOTES.md` | Session log + current state |

**Don't load without a reason:** `tests/fixtures/*.json` — large recorded API responses; only useful when debugging specific fixture data.
