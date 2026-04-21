# dynasty-mcp — Implementation Status

## CURRENT STATE (2026-04-21)

**Branch:** `main` (v1 shipped + reset_optimizer merged)

**Next task:** Tool-storage app scoping memo (`docs/decisions/`) or league-scoring-adjusted values spec — both need brainstorm first.

**Uncommitted changes on main:**
- `src/dynasty_mcp/__main__.py` + `tests/test_main.py` (TODO #1 NoneType fix)
- `docs/superpowers/specs/2026-04-20-reset-tools-design.md`
- `docs/superpowers/plans/2026-04-20-reset-optimizer.md`

**Outstanding TODOs:**
1. ✅ NoneType crash fix — done, uncommitted (commit first)
2. ✅ reset_trades — PR #2 merged
3. 🔲 Tool-storage app scoping memo — no spec yet
4. 🔲 League-scoring-adjusted values — no spec yet

**Quick resume:**
```bash
cd ~/projects/dynasty-mcp && git status && pytest -v
```

---



**As of:** 2026-04-19
**Branch:** `implement-v1`
**Plan:** `docs/superpowers/plans/2026-04-19-dynasty-mcp-v1.md`
**Spec:** `docs/superpowers/specs/2026-04-19-dynasty-mcp-design.md`

## Done

- **Task 1 — Project scaffold** (`5373589`, `c7038f3`): `pyproject.toml` (fastmcp, httpx, pydantic, platformdirs; dev: pytest, pytest-asyncio, respx), `.gitignore`, `src/` layout with empty `__init__.py` files, stub `__main__.py`, venv at `.venv/` (Python 3.12 via Homebrew).
- **Task 2 — TOML config loader** (`94ba278`, `c0db335`): `src/dynasty_mcp/config.py` with `Config` frozen dataclass, `load_config()`, `ConfigError`. Rejects missing or whitespace-only username, wraps int-cast errors as `ConfigError`. 6 tests in `tests/test_config.py`.
- **Task 3 — SQLite cache layer** (`19c16be`, `9dcd711`): `src/dynasty_mcp/cache.py` — `Cache` dataclass, 4-table schema (players, values_snapshots, league_snapshot, http_cache), round-trip methods, `players_stale()` / `values_stale()` helpers. Rejects naive datetimes at write time. 8 tests in `tests/test_cache.py`.
- **Task 4 — Pydantic models** (`e2d9718`): `src/dynasty_mcp/models.py` — `SlotType` enum, `Player`, `Value`, `RosterEntry`, `RosterView`, `LeagueContext`, `StaleFlag`. 4 tests in `tests/test_models.py`.
- **Task 5 — Fixture recording script** (`a02c149`): `scripts/record_fixtures.py` + 15 JSON fixtures under `tests/fixtures/` recorded against the live Sleeper + FantasyCalc APIs using `dakeif` / `1335327387256119296`. `matchups_week7`, `transactions_week7`, `draft_picks` are empty (April timing, past 2025 season) — acceptable per plan.
- **Task 6 — Sleeper API client** (`13c8378`): `src/dynasty_mcp/sources/sleeper.py` — `SleeperClient` dataclass, retry-once on transient errors, `get_players` cache + stale fallback. 5 respx-mocked tests in `tests/test_sleeper.py`.
- **Task 7 — FantasyCalc client** (`ed94eb7`): `src/dynasty_mcp/sources/fantasycalc.py` — `derive_params` module function, `FantasyCalcClient` dataclass, cache-first `get_current`. Intentional asymmetry with `SleeperClient`: no stale-cache fallback on HTTP error. 2 tests in `tests/test_fantasycalc.py`.

**Full suite:** 25 passing (6 config + 8 cache + 4 models + 5 sleeper + 2 fantasycalc).

Each task went through implementer → spec reviewer → code quality reviewer loop; fixes applied where latent bugs were found (tz-aware datetimes, ConfigError contract, whitespace username).

## Left

- **Tasks 8–17** — 10 primitive MCP tools + `refresh_cache`: `get_league_context`, `get_roster`, `list_rosters`, `get_player_values`, `get_matchup`, `get_free_agents`, `get_trending`, `get_transactions`, `get_draft`, `get_team_value_breakdown`, `refresh_cache`. Starts with a `Context` helper (plan Phase 3 preamble + Task 8).
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
- **ETag / Last-Modified not wired in `SleeperClient`** — plan preamble (line 869) claims the client "honors ETag / Last-Modified for polite usage," but neither the plan's reference code nor the implementation actually sends `If-None-Match` / `If-Modified-Since` headers or stores response headers. `http_cache` table sits unused. Decide whether to defer to a later task or drop the claim from the spec.
- **`get_players` redundant except clause** — `except (httpx.HTTPError, *_TRANSIENT)` is semantically redundant since all `_TRANSIENT` classes subclass `httpx.HTTPError`. Plan-verbatim; no behavior change. Simplify to `except httpx.HTTPError:` during final cleanup.
- **Thin test coverage on `SleeperClient`** — missing tests for: retry-on-transient path in `_get`, `get_players` stale-cache fallback on HTTP error, `get_players(force=True)` cache-bypass, `get_players` re-raise when no cache. Plan-deferred but these are the client's most fragile branches; add before wiring into live MCP tools (Tasks 8–17).
- **`derive_params` (FantasyCalc) superflex detection** — only recognizes the literal `"SUPER_FLEX"` token in `roster_positions`. A league that runs 2 true `"QB"` slots without the SUPER_FLEX token would resolve to `numQbs=1`. Sleeper's own league schema uses `SUPER_FLEX`, so fine for this league; revisit if the client is ever reused across leagues.
- **`derive_params` (FantasyCalc) thin test coverage** — no tests for `force=True` refetch path or the stale-cache-triggers-refetch branch. Plan-accepted; add when values client is wired into `get_player_values` (Task 11).

## How to Resume

```bash
cd ~/projects/dynasty-mcp
git status                      # confirm clean on implement-v1
git log --oneline -10           # confirm head at 9dcd711 or e2d9718
.venv/bin/pytest -v             # confirm 18 passing
```

Then in Claude: "resume subagent-driven execution of the dynasty-mcp plan at Task 5." The controller re-reads the plan + this file and dispatches the Task 5 implementer.

---

## Session 2026-04-19 (post-ship)

**Context:** All v1 tasks (1–20) are shipped; server is wired and connected.

### Updates

- MCP server registered in `~/.claude.json` (stdio: `.venv/bin/python -m dynasty_mcp`), previously showing "Failed" because `~/.config/dynasty-mcp/config.toml` still had the example placeholder `username = "your_sleeper_username"`. Fixed by setting `username = "dakeif"` and `league_id = "1335327387256119296"`.
- Verified server reaches `server.run()` cleanly; all 11 tools load and respond (`get_league_context`, `list_rosters`, `get_roster` all exercised end-to-end).
- Confirmed league is 14-team superflex, 0.5 PPR, roster_id 7 (dakeif). Current team value 44,791 (#7 of 14 by FantasyCalc).

### Follow-ups / open TODOs

- **Improve error when Sleeper user lookup returns `None`** — [`__main__.py:15`](src/dynasty_mcp/__main__.py#L15) crashes with `TypeError: 'NoneType' object is not subscriptable` if `sleeper.get_user(username)` returns `None` (e.g. placeholder/typo username). Should raise a clear `ConfigError` naming the offending username. This cost 15 min of debugging when the server first showed "Failed".
- **Investigate creating an app to store tools.** Persistent UI/app layer for dynasty-mcp tools outside an active Claude Code session — scoping only.
- **Reset team optimizer.** New MCP tool that, given the semi-hard-reset protections (1 QB, 1 RB/TE, 1 WR/TE, 3 TAXI), computes the optimal protection slate for dakeif and reports the value gap vs. everything that would hit the re-draft pool. TAXI-eligible rookies get a bonus for protecting without burning a starter slot. Depends on the league-rules memory ([project_league_rules.md](../../.claude/projects/-Users-keithtimko-projects-dynasty-mcp/memory/project_league_rules.md)) and FantasyCalc values.
- **Reset-aware trade finder.** New MCP tool that weights trade proposals by a reset-probability knob: discounts traded future picks toward zero (they don't carry over), discounts unprotectable bench depth (in-season contribution only), upweights protectable starters and TAXI-eligible rookies, and assumes a larger post-reset free-agent pool. Depends on the protection-optimizer math from the reset team optimizer above.

### Rules imported (2026-04-20)

League rules PDF imported into memory as [project_league_rules.md](../../.claude/projects/-Users-keithtimko-projects-dynasty-mcp/memory/project_league_rules.md). Key facts driving the two new TODOs: 0.5 per-1st-down bonuses + TE premium (full 1.0 PPR for TEs) mean FantasyCalc values systematically under-price workhorse backs, possession WRs, and TEs; semi-hard reset protects only 1 QB / 1 RB-TE / 1 WR-TE / 3 TAXI per team with traded future picks voided; Empire pot triggers are back-to-back championships or 2-of-3 championships plus 1-seed in 2-of-3.

---

## Session 2026-04-20 (reset-tools brainstorming)

**Done this session:**
- Imported league rules PDF → `project_league_rules.md` memory.
- Added TODOs #3 (reset team optimizer) and #4 (reset-aware trade finder) to both NOTES.md and `project_open_todos.md`.
- Brainstormed and wrote design spec: [docs/superpowers/specs/2026-04-20-reset-tools-design.md](docs/superpowers/specs/2026-04-20-reset-tools-design.md).
  - Approach 2 approved: pure `reset_scoring.py` module + two tool wrappers (`tools/reset_optimizer.py`, `tools/reset_trades.py`).
  - Locked decisions: FantasyCalc values as-is (Q1-C scoring adjustments deferred as follow-up); `reset_probability: float` param on both tools; optimizer returns top-5 slates with swap deltas; trade finder is shop-me default with `partner` knob for deep-dive; TAXI-eligible = currently on any team's TAXI; picks included in trade search (future-year discounted by `probability`, current-year unaffected); 1-for-1 and 2-for-1 only; mutual-gain filter on both sides (`min_edge=500` default).

**Left to do (next session):**

1. **Invoke `superpowers:writing-plans`** against [docs/superpowers/specs/2026-04-20-reset-tools-design.md](docs/superpowers/specs/2026-04-20-reset-tools-design.md) to produce an implementation plan at `docs/superpowers/plans/2026-04-20-reset-tools.md`. Spec self-review not yet done — do that first, then plan-writing.
2. **TODO #1 — NoneType crash fix** in [src/dynasty_mcp/__main__.py:14-15](src/dynasty_mcp/__main__.py#L14-L15). Current file has TWO bugs: (a) line 14 reads `sleeper.get_user(dakeif)` — `dakeif` is a bare name causing `NameError`; should be `username`. (b) After fixing (a), the original bug surfaces: `sleeper.get_user(username)` can return `None`, and `user["user_id"]` then raises `TypeError`. Fix both: defensive `if user is None: raise ConfigError(f"Sleeper has no user {username!r}")`. Small test in `tests/test_main.py` (new file) via respx.
3. **TODO #2 — Tool-storage app scoping memo.** Not started. Deliverable is a short comparison memo (web app / desktop app / reuse FastMCP HTTP transport / other) with a recommendation; no code. Can live at `docs/decisions/2026-04-XX-tool-storage-app-scoping.md`.
4. **TODOs #3 + #4** — execute the implementation plan produced in step 1. TDD flow per existing task-by-task convention.

**How to resume:**
```bash
cd ~/projects/dynasty-mcp
git status
# then in Claude:
# "spec self-review on docs/superpowers/specs/2026-04-20-reset-tools-design.md, then invoke writing-plans"
```

---

## Session 2026-04-20 (reset_optimizer implementation + merge)

**Branch:** `implement-v1` → merged to `main` via PR #1.

### Completed this session

- **TODO #1 — NoneType crash fix** (`__main__.py`): fixed bare `dakeif` name → `username`; added `if user is None: raise ConfigError(...)` guard. Tests in `tests/test_main.py` (uncommitted — see below).
- **TODO #3 — `reset_optimizer` MCP tool** (commits `a30667e`…`a24eec2`):
  - `src/dynasty_mcp/reset_scoring.py` — pure scoring module, zero I/O: `enumerate_slates`, `rank_slates`, `value_at_risk`, `pick_value_under_reset`, `asset_value_under_reset`.
  - `src/dynasty_mcp/tools/reset_optimizer.py` — async tool wrapper; top-N slates with per-slot swap deltas and `value_at_risk`.
  - `src/dynasty_mcp/models.py` — added `ProtectionSlot`, `ProtectionSlate`, `Swap`, `SlateOption`, `ResetOptimizerResult`.
  - `src/dynasty_mcp/server.py` — `reset_optimizer` registered.
  - `tests/test_reset_scoring.py` — 24 unit tests (100% line coverage target).
  - `tests/test_tools/test_reset_optimizer.py` — 8 integration tests.
  - `tests/test_contract.py` — live smoke check added (DYNASTY_LIVE=1 guard).
  - **75 tests passing** on merge.
- **PR #1 created and merged** to `main`.

### Uncommitted working-tree changes (carry forward)

These were present before this session's feature work and were stashed/restored around the merge. Commit them separately:

| File | What it is |
|---|---|
| `src/dynasty_mcp/__main__.py` | TODO #1 NoneType fix |
| `tests/test_main.py` | Tests for the TODO #1 fix |
| `NOTES.md` | This file |
| `docs/superpowers/specs/2026-04-20-reset-tools-design.md` | Design spec (reference) |
| `docs/superpowers/plans/2026-04-20-reset-optimizer.md` | Implementation plan (reference) |

```bash
git add src/dynasty_mcp/__main__.py tests/test_main.py \
        docs/superpowers/specs/2026-04-20-reset-tools-design.md \
        docs/superpowers/plans/2026-04-20-reset-optimizer.md \
        NOTES.md
git commit -m "fix: raise ConfigError on unknown Sleeper user; add reset-tools docs"
```

### Outstanding TODOs

1. **TODO #4 — `reset_trades` MCP tool** — DESIGNED, not implemented. Spec: [docs/superpowers/specs/2026-04-20-reset-tools-design.md § Component 3](docs/superpowers/specs/2026-04-20-reset-tools-design.md). Depends on `asset_value_under_reset` (already implemented). Resume: invoke `superpowers:writing-plans` against the Component 3 section of the spec, then `superpowers:subagent-driven-development` to execute.

2. **TODO #2 — Tool-storage app scoping memo** — Not started. Deliverable: short comparison memo (web app / desktop / FastMCP HTTP transport / other) at `docs/decisions/YYYY-MM-DD-tool-storage-app-scoping.md`. No code.

3. **TODO #5 — League-scoring-adjusted values** — No spec yet. Correct FantasyCalc's format bias using Sleeper scoring settings + historical stats; swap in behind `league_adjust: bool = False`. Start with brainstorming when other TODOs are cleared.

### How to resume next session

```bash
cd ~/projects/dynasty-mcp
git status                    # should show 5 uncommitted changes above
pytest -v                     # 75 passing (no --tb needed)
```

Then in Claude: "commit the outstanding changes, then write an implementation plan for reset_trades using the Component 3 section of docs/superpowers/specs/2026-04-20-reset-tools-design.md."

---

## Efficiency notes (2026-04-20 retrospective)

Patterns that slowed down this session and how to avoid them next time:

### What worked well
- **Subagent-driven development** — fresh context per task kept each implementer focused; the two-stage review (spec compliance → code quality) caught real bugs (TAXI swap pairing, tiebreak weakness, truncation test).
- **Pure module isolation** — `reset_scoring.py` having zero I/O made its 24 unit tests fast and deterministic; no mocking needed.
- **Spec locked decisions before planning** — the design spec's "locked decisions" table prevented re-litigating choices (FantasyCalc values as-is, probability knob, top-5 slates) during implementation.

### What slowed things down
- **`respx` null-body gotcha** — `respond(json=None)` sends empty body, not JSON `null`. Using `content=b"null", headers={"content-type": "application/json"}` is the correct form. Worth remembering for future Sleeper tests.
- **TAXI swap pairing bug found late** — the nested-loop swap diffing was written before tests covered the multi-TAXI-change case. Writing the "lower ranks have swaps" test *before* the swap logic would have caught this earlier.
- **`zip` vs `zip_longest` silent drop** — `zip` silently discards unmatched tail entries; `zip_longest` is always safer when lengths may differ. Default to `zip_longest` for any paired-list iteration in this codebase.
- **Context window compaction mid-PR** — session ran out of context just before the git push. The PR creation and merge happened in the resumed session. For long implementation sessions, consider committing a session-state note earlier so resumption is cleaner.
- **Uncommitted files across the merge** — `__main__.py` fix and `tests/test_main.py` were completed during the session but not committed before the PR. They ended up stashed around the merge. Commit small fixes immediately rather than letting them accumulate.
