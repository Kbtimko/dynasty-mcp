# dynasty-mcp v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python MCP server that exposes 11 read-only tools over Sleeper's API + FantasyCalc dynasty values, so Claude can answer trade, lineup, waiver, draft, and long-term strategy questions about the user's empire dynasty league.

**Architecture:** FastMCP stdio server. API clients in `sources/` wrap Sleeper and FantasyCalc; a SQLite cache at `platformdirs.user_data_dir("dynasty-mcp")/cache.db` stores the player dataset, value snapshots, and roster history. Each tool module pulls from the cache and clients and returns typed pydantic models. TDD with recorded-fixture tests (replayed via respx) — no live HTTP in the test suite.

**Tech Stack:** Python 3.12+, FastMCP, httpx, pydantic, platformdirs, pytest, respx, SQLite (stdlib), tomllib (stdlib).

**Spec:** `docs/superpowers/specs/2026-04-19-dynasty-mcp-design.md`

---

## Conventions used in this plan

- All shell commands assume `cwd = ~/projects/dynasty-mcp` unless noted.
- All Python packages are installed into a project venv at `~/projects/dynasty-mcp/.venv`.
- Run tests with `pytest -v` unless the task specifies a narrower target.
- Commit after every task. Use conventional commits (`feat:`, `test:`, `chore:`, `docs:`, `refactor:`).

---

## Phase 1 — Foundation

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`
- Create: `src/dynasty_mcp/__init__.py`
- Create: `src/dynasty_mcp/__main__.py` (stub)
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1: Create project directory layout**

```bash
mkdir -p src/dynasty_mcp/sources src/dynasty_mcp/tools tests/fixtures tests/test_tools
touch src/dynasty_mcp/__init__.py \
      src/dynasty_mcp/sources/__init__.py \
      src/dynasty_mcp/tools/__init__.py \
      tests/__init__.py \
      tests/test_tools/__init__.py \
      tests/fixtures/.gitkeep
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dynasty-mcp"
version = "0.1.0"
description = "Local MCP server for Sleeper dynasty fantasy football management"
requires-python = ">=3.12"
dependencies = [
  "fastmcp>=2.0",
  "httpx>=0.27",
  "pydantic>=2.7",
  "platformdirs>=4.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "respx>=0.21",
]

[project.scripts]
dynasty-mcp = "dynasty_mcp.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/dynasty_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
dist/
build/
*.egg-info/
.DS_Store
```

- [ ] **Step 4: Write `README.md` (skeleton — fleshed out in final task)**

```markdown
# dynasty-mcp

Local Model Context Protocol server for Sleeper dynasty fantasy football league management.

See `docs/superpowers/specs/` for the design spec and `docs/superpowers/plans/` for the implementation plan.
```

- [ ] **Step 5: Write stub `src/dynasty_mcp/__main__.py`**

```python
def main() -> None:
    raise NotImplementedError("server not yet wired — see Task 19")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Create venv and install**

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Expected: successful install, no errors.

- [ ] **Step 7: Verify pytest runs (zero tests is a pass)**

Run: `.venv/bin/pytest -v`
Expected: `no tests ran in Xs` (exit 5 — that's OK for this step; next tasks add tests).

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "chore: scaffold dynasty-mcp project"
```

---

### Task 2: Config loader

**Files:**
- Create: `src/dynasty_mcp/config.py`
- Create: `tests/test_config.py`

The config loader reads `~/.config/dynasty-mcp/config.toml`, validates required fields, and exposes a typed `Config` object. Cache path defaults to `platformdirs.user_data_dir("dynasty-mcp") + "/cache.db"` but can be overridden.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
from pathlib import Path
import tomllib

import pytest

from dynasty_mcp.config import Config, ConfigError, load_config


def write_toml(path: Path, body: str) -> None:
    path.write_text(body)


def test_loads_minimal_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.sleeper_username == "alice"
    assert cfg.sleeper_league_id is None
    assert cfg.values_source == "fantasycalc"
    assert cfg.players_refresh_days == 7
    assert cfg.values_refresh_hours == 24
    assert cfg.cache_path.name == "cache.db"


def test_loads_full_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(
        cfg_file,
        """
        [sleeper]
        username = "alice"
        league_id = "123"

        [values]
        source = "fantasycalc"

        [cache]
        path = "/tmp/override.db"
        players_refresh_days = 3
        values_refresh_hours = 6
        """,
    )
    cfg = load_config(cfg_file)
    assert cfg.sleeper_league_id == "123"
    assert cfg.cache_path == Path("/tmp/override.db")
    assert cfg.players_refresh_days == 3
    assert cfg.values_refresh_hours == 6


def test_missing_username_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, "[sleeper]\n")
    with pytest.raises(ConfigError, match="sleeper.username"):
        load_config(cfg_file)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")
```

- [ ] **Step 2: Run the test — expect failures**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: `ImportError: cannot import name 'Config'` (or similar — module doesn't exist yet).

- [ ] **Step 3: Implement `src/dynasty_mcp/config.py`**

```python
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import platformdirs


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "dynasty-mcp" / "config.toml"


@dataclass(frozen=True)
class Config:
    sleeper_username: str
    sleeper_league_id: str | None
    values_source: str
    cache_path: Path
    players_refresh_days: int
    values_refresh_hours: int


def _default_cache_path() -> Path:
    return Path(platformdirs.user_data_dir("dynasty-mcp")) / "cache.db"


def load_config(path: Path | None = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise ConfigError(f"Config file not found at {cfg_path}")

    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)

    sleeper = raw.get("sleeper", {})
    username = sleeper.get("username")
    if not username:
        raise ConfigError("Missing required field: sleeper.username")

    values = raw.get("values", {})
    cache = raw.get("cache", {})

    cache_path_raw = cache.get("path")
    cache_path = Path(cache_path_raw).expanduser() if cache_path_raw else _default_cache_path()

    return Config(
        sleeper_username=username,
        sleeper_league_id=sleeper.get("league_id"),
        values_source=values.get("source", "fantasycalc"),
        cache_path=cache_path,
        players_refresh_days=int(cache.get("players_refresh_days", 7)),
        values_refresh_hours=int(cache.get("values_refresh_hours", 24)),
    )
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/config.py tests/test_config.py
git commit -m "feat: add TOML config loader"
```

---

### Task 3: SQLite cache layer

**Files:**
- Create: `src/dynasty_mcp/cache.py`
- Create: `tests/test_cache.py`

Cache responsibilities: open/close SQLite connection, initialize schema, store & retrieve Sleeper player dataset, store & retrieve FantasyCalc value snapshots, store roster snapshots, track HTTP ETag/Last-Modified per URL, and indicate staleness based on age.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cache.py
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dynasty_mcp.cache import Cache


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache.open(tmp_path / "cache.db")


def test_initializes_schema(cache: Cache) -> None:
    tables = cache.list_tables()
    assert {"players", "values", "league_snapshot", "http_cache"} <= set(tables)


def test_store_and_retrieve_players(cache: Cache) -> None:
    players = {"4046": {"full_name": "Patrick Mahomes", "position": "QB"}}
    cache.put_players(players, fetched_at=datetime.now(timezone.utc))
    got, fetched_at = cache.get_players()
    assert got == players
    assert fetched_at is not None


def test_players_stale_after_refresh_window(cache: Cache) -> None:
    long_ago = datetime.now(timezone.utc) - timedelta(days=10)
    cache.put_players({"1": {}}, fetched_at=long_ago)
    assert cache.players_stale(refresh_days=7) is True


def test_values_snapshot_stored_with_timestamp(cache: Cache) -> None:
    now = datetime.now(timezone.utc)
    cache.put_values_snapshot(
        [{"player_id": "4046", "value": 8500}],
        fetched_at=now,
    )
    latest = cache.get_latest_values()
    assert latest is not None
    snapshot, fetched_at = latest
    assert snapshot[0]["value"] == 8500
    assert fetched_at == now


def test_http_cache_round_trip(cache: Cache) -> None:
    cache.put_http_headers("https://x", etag="abc", last_modified=None)
    headers = cache.get_http_headers("https://x")
    assert headers == {"etag": "abc", "last_modified": None}


def test_get_players_empty_returns_none(cache: Cache) -> None:
    got, fetched_at = cache.get_players()
    assert got is None
    assert fetched_at is None
```

- [ ] **Step 2: Run the test — expect failures**

Run: `.venv/bin/pytest tests/test_cache.py -v`
Expected: `ImportError: cannot import name 'Cache'`.

- [ ] **Step 3: Implement `src/dynasty_mcp/cache.py`**

```python
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS values_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS league_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id TEXT NOT NULL,
    week INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    data TEXT NOT NULL,
    UNIQUE (league_id, week)
);
CREATE TABLE IF NOT EXISTS http_cache (
    url TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT
);
"""


@dataclass
class Cache:
    conn: sqlite3.Connection

    @classmethod
    def open(cls, path: Path) -> "Cache":
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        conn.commit()
        return cls(conn=conn)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        # Map the internal table name to the spec names where they differ.
        names = {r[0] for r in rows}
        if "values_snapshots" in names:
            names.add("values")
        return sorted(names)

    # --- players ---
    def put_players(self, players: dict[str, Any], fetched_at: datetime) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO players (id, data, fetched_at) VALUES (1, ?, ?)",
            (json.dumps(players), fetched_at.isoformat()),
        )
        self.conn.commit()

    def get_players(self) -> tuple[dict[str, Any] | None, datetime | None]:
        row = self.conn.execute(
            "SELECT data, fetched_at FROM players WHERE id = 1"
        ).fetchone()
        if not row:
            return None, None
        return json.loads(row[0]), datetime.fromisoformat(row[1])

    def players_stale(self, refresh_days: int) -> bool:
        _, fetched_at = self.get_players()
        if fetched_at is None:
            return True
        return datetime.now(timezone.utc) - fetched_at > timedelta(days=refresh_days)

    # --- values ---
    def put_values_snapshot(
        self, values: list[dict[str, Any]], fetched_at: datetime
    ) -> None:
        self.conn.execute(
            "INSERT INTO values_snapshots (fetched_at, data) VALUES (?, ?)",
            (fetched_at.isoformat(), json.dumps(values)),
        )
        self.conn.commit()

    def get_latest_values(
        self,
    ) -> tuple[list[dict[str, Any]], datetime] | None:
        row = self.conn.execute(
            "SELECT data, fetched_at FROM values_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return json.loads(row[0]), datetime.fromisoformat(row[1])

    def values_stale(self, refresh_hours: int) -> bool:
        latest = self.get_latest_values()
        if latest is None:
            return True
        _, fetched_at = latest
        return datetime.now(timezone.utc) - fetched_at > timedelta(hours=refresh_hours)

    # --- league snapshots ---
    def put_league_snapshot(
        self, league_id: str, week: int, data: dict[str, Any], fetched_at: datetime
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO league_snapshot (league_id, week, fetched_at, data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(league_id, week) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                data = excluded.data
            """,
            (league_id, week, fetched_at.isoformat(), json.dumps(data)),
        )
        self.conn.commit()

    # --- http cache ---
    def put_http_headers(
        self, url: str, etag: str | None, last_modified: str | None
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO http_cache (url, etag, last_modified) VALUES (?, ?, ?)",
            (url, etag, last_modified),
        )
        self.conn.commit()

    def get_http_headers(self, url: str) -> dict[str, str | None] | None:
        row = self.conn.execute(
            "SELECT etag, last_modified FROM http_cache WHERE url = ?", (url,)
        ).fetchone()
        if not row:
            return None
        return {"etag": row[0], "last_modified": row[1]}
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_cache.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/cache.py tests/test_cache.py
git commit -m "feat: add SQLite cache layer"
```

---

### Task 4: Data models

**Files:**
- Create: `src/dynasty_mcp/models.py`
- Create: `tests/test_models.py`

Pydantic models shared across tools. Keep them minimal — only fields tools actually return.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models.py
from dynasty_mcp.models import (
    LeagueContext,
    Player,
    RosterEntry,
    RosterView,
    SlotType,
    Value,
)


def test_player_minimal() -> None:
    p = Player(player_id="4046", full_name="Patrick Mahomes", position="QB", team="KC")
    assert p.age is None
    assert p.status is None


def test_roster_entry_carries_slot_and_value() -> None:
    entry = RosterEntry(
        player=Player(player_id="1", full_name="X", position="WR", team="SF"),
        slot_type=SlotType.TAXI,
        value=Value(current=1200, delta_7d=100),
    )
    assert entry.slot_type == SlotType.TAXI
    assert entry.value.delta_7d == 100


def test_roster_view_totals() -> None:
    view = RosterView(
        roster_id=1,
        owner_username="alice",
        entries=[],
        total_value_active=0,
        total_value_taxi=0,
        total_value_ir=0,
    )
    assert view.roster_id == 1


def test_league_context_has_taxi_slots() -> None:
    ctx = LeagueContext(
        league_id="L",
        season="2026",
        current_week=7,
        season_phase="regular",
        num_teams=12,
        num_qbs=2,
        ppr=1.0,
        roster_slots={"QB": 1, "RB": 2, "WR": 3, "TE": 1, "FLEX": 2},
        taxi_slots=4,
        bench_slots=7,
        ir_slots=2,
        your_roster_id=3,
    )
    assert ctx.taxi_slots == 4
    assert ctx.num_qbs == 2
```

- [ ] **Step 2: Run the test — expect failures**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/models.py`**

```python
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SlotType(str, Enum):
    ACTIVE = "active"
    BENCH = "bench"
    TAXI = "taxi"
    IR = "ir"


class Player(BaseModel):
    player_id: str
    full_name: str
    position: str
    team: str | None = None
    age: int | None = None
    status: str | None = None  # "Active", "IR", "Questionable", etc.


class Value(BaseModel):
    current: int | None
    delta_7d: int | None = None
    delta_30d: int | None = None


class RosterEntry(BaseModel):
    player: Player
    slot_type: SlotType
    value: Value
    starter: bool = False
    projection: float | None = None  # weekly points projection, set by get_matchup


class RosterView(BaseModel):
    roster_id: int
    owner_username: str
    owner_display_name: str | None = None
    entries: list[RosterEntry]
    total_value_active: int
    total_value_taxi: int
    total_value_ir: int


class LeagueContext(BaseModel):
    league_id: str
    season: str
    current_week: int
    season_phase: Literal["pre", "regular", "post", "offseason"]
    num_teams: int
    num_qbs: int  # 1 or 2 (superflex)
    ppr: float
    roster_slots: dict[str, int]
    taxi_slots: int
    bench_slots: int
    ir_slots: int
    your_roster_id: int


class StaleFlag(BaseModel):
    stale: bool = False
    as_of: str | None = None  # ISO-8601 UTC
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/models.py tests/test_models.py
git commit -m "feat: add shared pydantic models"
```

---

## Phase 2 — API Clients

### Task 5: Fixture recording script + recorded fixtures

**Files:**
- Create: `scripts/record_fixtures.py`
- Create: `tests/fixtures/sleeper_league.json`
- Create: `tests/fixtures/sleeper_rosters.json`
- Create: `tests/fixtures/sleeper_users.json`
- Create: `tests/fixtures/sleeper_matchups_week7.json`
- Create: `tests/fixtures/sleeper_transactions_week7.json`
- Create: `tests/fixtures/sleeper_traded_picks.json`
- Create: `tests/fixtures/sleeper_drafts.json`
- Create: `tests/fixtures/sleeper_draft.json`
- Create: `tests/fixtures/sleeper_draft_picks.json`
- Create: `tests/fixtures/sleeper_players.json` (trimmed — see below)
- Create: `tests/fixtures/sleeper_trending_add.json`
- Create: `tests/fixtures/sleeper_state.json`
- Create: `tests/fixtures/sleeper_user.json`
- Create: `tests/fixtures/sleeper_user_leagues.json`
- Create: `tests/fixtures/fantasycalc_values.json`

This task records real API responses once. Subsequent tool tests replay these via `respx`. The full Sleeper players dataset is trimmed to the ~200 players that appear in the user's league + fixtures, to keep repo size manageable.

- [ ] **Step 1: Write the recording script**

```python
# scripts/record_fixtures.py
"""Record live API responses to tests/fixtures/ for replay-based testing.

Usage:
    SLEEPER_USERNAME=... SLEEPER_LEAGUE_ID=... .venv/bin/python scripts/record_fixtures.py

Re-run quarterly, after NFL season transitions, or when API shapes change.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
SLEEPER = "https://api.sleeper.app/v1"
FANTASYCALC = "https://api.fantasycalc.com/values/current"


def save(name: str, data: object) -> None:
    path = FIXTURES / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True))
    print(f"wrote {path}")


def main() -> None:
    username = os.environ.get("SLEEPER_USERNAME")
    league_id = os.environ.get("SLEEPER_LEAGUE_ID")
    if not username or not league_id:
        print("Set SLEEPER_USERNAME and SLEEPER_LEAGUE_ID", file=sys.stderr)
        sys.exit(2)

    season = os.environ.get("SEASON", "2025")
    week = os.environ.get("WEEK", "7")

    with httpx.Client(timeout=30) as c:
        state = c.get(f"{SLEEPER}/state/nfl").json()
        save("sleeper_state.json", state)

        user = c.get(f"{SLEEPER}/user/{username}").json()
        save("sleeper_user.json", user)

        leagues = c.get(
            f"{SLEEPER}/user/{user['user_id']}/leagues/nfl/{season}"
        ).json()
        save("sleeper_user_leagues.json", leagues)

        save("sleeper_league.json", c.get(f"{SLEEPER}/league/{league_id}").json())
        save("sleeper_rosters.json", c.get(f"{SLEEPER}/league/{league_id}/rosters").json())
        save("sleeper_users.json", c.get(f"{SLEEPER}/league/{league_id}/users").json())
        save(
            f"sleeper_matchups_week{week}.json",
            c.get(f"{SLEEPER}/league/{league_id}/matchups/{week}").json(),
        )
        save(
            f"sleeper_transactions_week{week}.json",
            c.get(f"{SLEEPER}/league/{league_id}/transactions/{week}").json(),
        )
        save(
            "sleeper_traded_picks.json",
            c.get(f"{SLEEPER}/league/{league_id}/traded_picks").json(),
        )
        drafts = c.get(f"{SLEEPER}/league/{league_id}/drafts").json()
        save("sleeper_drafts.json", drafts)
        if drafts:
            draft_id = drafts[0]["draft_id"]
            save("sleeper_draft.json", c.get(f"{SLEEPER}/draft/{draft_id}").json())
            save(
                "sleeper_draft_picks.json",
                c.get(f"{SLEEPER}/draft/{draft_id}/picks").json(),
            )
        save(
            "sleeper_trending_add.json",
            c.get(
                f"{SLEEPER}/players/nfl/trending/add",
                params={"lookback_hours": 24, "limit": 25},
            ).json(),
        )

        # Trim the full players dataset to players that appear in this league's
        # rosters, the trending list, and the draft — keeps the fixture small.
        rosters = json.loads((FIXTURES / "sleeper_rosters.json").read_text())
        trending = json.loads((FIXTURES / "sleeper_trending_add.json").read_text())
        draft_picks = json.loads((FIXTURES / "sleeper_draft_picks.json").read_text())
        keep_ids: set[str] = set()
        for r in rosters:
            keep_ids.update(r.get("players") or [])
            keep_ids.update(r.get("taxi") or [])
            keep_ids.update(r.get("reserve") or [])
        keep_ids.update(t["player_id"] for t in trending)
        keep_ids.update(p.get("player_id") for p in draft_picks if p.get("player_id"))
        all_players = c.get(f"{SLEEPER}/players/nfl").json()
        trimmed = {pid: all_players[pid] for pid in keep_ids if pid in all_players}
        save("sleeper_players.json", trimmed)

        # FantasyCalc — params derived from league later, but record one shape now.
        league = json.loads((FIXTURES / "sleeper_league.json").read_text())
        num_qbs = 2 if "SUPER_FLEX" in (league.get("roster_positions") or []) else 1
        num_teams = league.get("total_rosters", 12)
        ppr = float((league.get("scoring_settings") or {}).get("rec", 1.0))
        fc = c.get(
            FANTASYCALC,
            params={
                "isDynasty": "true",
                "numQbs": num_qbs,
                "numTeams": num_teams,
                "ppr": ppr,
            },
        ).json()
        save("fantasycalc_values.json", fc)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the recording script against the user's live league**

```bash
SLEEPER_USERNAME=<your_username> SLEEPER_LEAGUE_ID=<your_league_id> \
    .venv/bin/python scripts/record_fixtures.py
```

Expected: each `wrote tests/fixtures/…` message prints; 16 files exist in `tests/fixtures/`.

- [ ] **Step 3: Verify fixture sizes are reasonable**

```bash
du -sh tests/fixtures/*
```

Expected: `sleeper_players.json` under ~200KB (should be, after trimming); others small.

- [ ] **Step 4: Commit**

```bash
git add scripts/ tests/fixtures/
git commit -m "chore: record Sleeper + FantasyCalc fixtures for replay tests"
```

---

### Task 6: Sleeper API client

**Files:**
- Create: `src/dynasty_mcp/sources/sleeper.py`
- Create: `tests/test_sleeper.py`

Async httpx client. Wraps the endpoints used by tools. Returns parsed JSON (not models) — tool modules are responsible for shaping. Uses the cache for the players dataset and honors ETag / Last-Modified for polite usage.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sleeper.py
import json
from pathlib import Path

import httpx
import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.sources.sleeper import SleeperClient

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache.open(tmp_path / "cache.db")


@pytest.fixture
def client(cache: Cache) -> SleeperClient:
    return SleeperClient(cache=cache, refresh_days=7)


@pytest.mark.asyncio
async def test_get_league(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        league = await client.get_league("L1")
        assert league["league_id"] == load("sleeper_league.json")["league_id"]


@pytest.mark.asyncio
async def test_get_rosters(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        rosters = await client.get_rosters("L1")
        assert isinstance(rosters, list)
        assert rosters == load("sleeper_rosters.json")


@pytest.mark.asyncio
async def test_resolve_user_and_league(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/user/alice").respond(json=load("sleeper_user.json"))
        user = await client.get_user("alice")
        assert "user_id" in user


@pytest.mark.asyncio
async def test_players_dataset_cached(client: SleeperClient, cache: Cache) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        route = mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        # First call fetches
        players = await client.get_players()
        assert route.call_count == 1
        assert "4046" in players or len(players) > 0
        # Second call hits the cache
        players2 = await client.get_players()
        assert route.call_count == 1
        assert players == players2


@pytest.mark.asyncio
async def test_trending(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/players/nfl/trending/add").respond(
            json=load("sleeper_trending_add.json")
        )
        trending = await client.get_trending("add", lookback_hours=24, limit=25)
        assert isinstance(trending, list)
```

- [ ] **Step 2: Run tests — expect failures**

Run: `.venv/bin/pytest tests/test_sleeper.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/sources/sleeper.py`**

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dynasty_mcp.cache import Cache

BASE_URL = "https://api.sleeper.app/v1"

# Transient-error classes we retry once with backoff.
_TRANSIENT = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)


@dataclass
class SleeperClient:
    cache: Cache
    refresh_days: int = 7
    timeout: float = 30.0

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=self.timeout) as c:
            try:
                resp = await c.get(path, params=params)
            except _TRANSIENT:
                await asyncio.sleep(1.0)
                resp = await c.get(path, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_state(self) -> dict[str, Any]:
        return await self._get("/state/nfl")

    async def get_user(self, username_or_id: str) -> dict[str, Any]:
        return await self._get(f"/user/{username_or_id}")

    async def get_user_leagues(self, user_id: str, season: str) -> list[dict[str, Any]]:
        return await self._get(f"/user/{user_id}/leagues/nfl/{season}")

    async def get_league(self, league_id: str) -> dict[str, Any]:
        return await self._get(f"/league/{league_id}")

    async def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/rosters")

    async def get_league_users(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/users")

    async def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/matchups/{week}")

    async def get_transactions(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/transactions/{week}")

    async def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/traded_picks")

    async def get_drafts(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/drafts")

    async def get_draft(self, draft_id: str) -> dict[str, Any]:
        return await self._get(f"/draft/{draft_id}")

    async def get_draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/draft/{draft_id}/picks")

    async def get_trending(
        self, kind: str, *, lookback_hours: int = 24, limit: int = 25
    ) -> list[dict[str, Any]]:
        return await self._get(
            f"/players/nfl/trending/{kind}",
            params={"lookback_hours": lookback_hours, "limit": limit},
        )

    async def get_players(self, *, force: bool = False) -> dict[str, Any]:
        cached, _ = self.cache.get_players()
        if cached is not None and not force and not self.cache.players_stale(
            self.refresh_days
        ):
            return cached
        try:
            data = await self._get("/players/nfl")
        except (httpx.HTTPError, *_TRANSIENT):
            # Upstream unreachable or erroring: fall back to stale cache if we
            # have one, otherwise re-raise. Callers inspect players_stale() if
            # they need to report staleness to the user.
            if cached is not None:
                return cached
            raise
        self.cache.put_players(data, fetched_at=datetime.now(timezone.utc))
        return data
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_sleeper.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/sources/sleeper.py tests/test_sleeper.py
git commit -m "feat: add Sleeper API client"
```

---

### Task 7: FantasyCalc client

**Files:**
- Create: `src/dynasty_mcp/sources/fantasycalc.py`
- Create: `tests/test_fantasycalc.py`

Client derives query params from the league's scoring settings and roster positions, fetches current values, and caches them in the `values_snapshots` table so week-over-week deltas work.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fantasycalc.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient, derive_params

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


def test_derive_params_from_superflex_league() -> None:
    league = load("sleeper_league.json")
    params = derive_params(league)
    assert params["isDynasty"] == "true"
    assert params["numQbs"] in (1, 2)
    assert params["numTeams"] == league["total_rosters"]
    assert isinstance(params["ppr"], float)


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache.open(tmp_path / "cache.db")


@pytest.mark.asyncio
async def test_get_current_caches_snapshot(cache: Cache) -> None:
    client = FantasyCalcClient(cache=cache, refresh_hours=24)
    league = load("sleeper_league.json")
    with respx.mock(base_url="https://api.fantasycalc.com") as mock:
        route = mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        values = await client.get_current(league)
        assert route.call_count == 1
        assert isinstance(values, list)
        # Second call returns cached, no new HTTP
        values2 = await client.get_current(league)
        assert route.call_count == 1
        assert values == values2
```

- [ ] **Step 2: Run tests — expect failures**

Run: `.venv/bin/pytest tests/test_fantasycalc.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/sources/fantasycalc.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dynasty_mcp.cache import Cache

BASE_URL = "https://api.fantasycalc.com"


def derive_params(league: dict[str, Any]) -> dict[str, Any]:
    positions = league.get("roster_positions") or []
    num_qbs = 2 if "SUPER_FLEX" in positions else 1
    num_teams = league.get("total_rosters", 12)
    ppr = float((league.get("scoring_settings") or {}).get("rec", 1.0))
    return {
        "isDynasty": "true",
        "numQbs": num_qbs,
        "numTeams": num_teams,
        "ppr": ppr,
    }


@dataclass
class FantasyCalcClient:
    cache: Cache
    refresh_hours: int = 24
    timeout: float = 30.0

    async def get_current(
        self, league: dict[str, Any], *, force: bool = False
    ) -> list[dict[str, Any]]:
        if not force and not self.cache.values_stale(self.refresh_hours):
            latest = self.cache.get_latest_values()
            if latest is not None:
                values, _ = latest
                return values

        params = derive_params(league)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=self.timeout) as c:
            resp = await c.get("/values/current", params=params)
            resp.raise_for_status()
            data = resp.json()
        self.cache.put_values_snapshot(data, fetched_at=datetime.now(timezone.utc))
        return data
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_fantasycalc.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/sources/fantasycalc.py tests/test_fantasycalc.py
git commit -m "feat: add FantasyCalc values client"
```

---

## Phase 3 — Tools

Each tool task follows the same TDD pattern: write a test that constructs the tool with fixture-backed clients, calls it, and asserts on the shape of the return value. Then implement the tool. Then commit.

Tools accept a `Context` object holding the clients, cache, and config. Define this small helper first.

### Task 8: Tool Context helper + `get_league_context`

**Files:**
- Create: `src/dynasty_mcp/context.py`
- Create: `src/dynasty_mcp/tools/league.py`
- Create: `tests/test_tools/test_league.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_league.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.league import get_league_context

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
async def test_get_league_context_shape(tmp_path: Path) -> None:
    cache = Cache.open(tmp_path / "c.db")
    ctx = build_test_context(
        cache=cache, username="alice", league_id="L1", season="2025"
    )
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
        mock.get("/state/nfl").respond(json=load("sleeper_state.json"))

        result = await get_league_context(ctx)

    assert result.league_id == "L1"
    assert result.num_qbs in (1, 2)
    assert result.taxi_slots >= 0
    assert "QB" in result.roster_slots
    assert result.your_roster_id  # nonzero
    assert result.season_phase in ("pre", "regular", "post", "offseason")
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_league.py -v`
Expected: `ImportError` for `build_test_context` or `get_league_context`.

- [ ] **Step 3: Implement `src/dynasty_mcp/context.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dynasty_mcp.cache import Cache
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient
from dynasty_mcp.sources.sleeper import SleeperClient


@dataclass
class Context:
    cache: Cache
    sleeper: SleeperClient
    fantasycalc: FantasyCalcClient
    username: str
    league_id: str | None
    season: str


def build_test_context(
    *,
    cache: Cache,
    username: str,
    league_id: str | None,
    season: str = "2025",
) -> Context:
    return Context(
        cache=cache,
        sleeper=SleeperClient(cache=cache, refresh_days=7),
        fantasycalc=FantasyCalcClient(cache=cache, refresh_hours=24),
        username=username,
        league_id=league_id,
        season=season,
    )
```

- [ ] **Step 4: Implement `src/dynasty_mcp/tools/league.py`**

```python
from __future__ import annotations

from typing import Any

from dynasty_mcp.context import Context
from dynasty_mcp.models import LeagueContext


def _season_phase(state: dict[str, Any]) -> str:
    st = (state.get("season_type") or "").lower()
    if st in ("pre", "regular", "post"):
        return st
    return "offseason"


def _taxi_slots(league: dict[str, Any]) -> int:
    settings = league.get("settings") or {}
    return int(settings.get("taxi_slots", 0))


def _ir_slots(league: dict[str, Any]) -> int:
    settings = league.get("settings") or {}
    return int(settings.get("reserve_slots", 0))


def _count_position_slots(positions: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in positions:
        if p == "BN":
            continue
        counts[p] = counts.get(p, 0) + 1
    return counts


def _bench_slots(positions: list[str]) -> int:
    return sum(1 for p in positions if p == "BN")


async def _resolve_your_roster_id(
    ctx: Context, league_id: str
) -> int:
    users = await ctx.sleeper.get_league_users(league_id)
    user = next(
        (u for u in users if (u.get("username") or "").lower() == ctx.username.lower()),
        None,
    )
    if user is None:
        raise ValueError(
            f"Username {ctx.username!r} not found among league members"
        )
    rosters = await ctx.sleeper.get_rosters(league_id)
    mine = next((r for r in rosters if r.get("owner_id") == user["user_id"]), None)
    if mine is None:
        raise ValueError(f"No roster for user {user['user_id']} in league {league_id}")
    return int(mine["roster_id"])


async def get_league_context(ctx: Context) -> LeagueContext:
    if not ctx.league_id:
        raise ValueError("league_id must be set — config or resolve from username")
    league = await ctx.sleeper.get_league(ctx.league_id)
    state = await ctx.sleeper.get_state()
    positions = league.get("roster_positions") or []
    scoring = league.get("scoring_settings") or {}
    your_roster_id = await _resolve_your_roster_id(ctx, ctx.league_id)

    return LeagueContext(
        league_id=ctx.league_id,
        season=str(league.get("season") or ctx.season),
        current_week=int(state.get("week") or 0),
        season_phase=_season_phase(state),  # type: ignore[arg-type]
        num_teams=int(league.get("total_rosters") or 12),
        num_qbs=2 if "SUPER_FLEX" in positions else 1,
        ppr=float(scoring.get("rec", 1.0)),
        roster_slots=_count_position_slots(positions),
        taxi_slots=_taxi_slots(league),
        bench_slots=_bench_slots(positions),
        ir_slots=_ir_slots(league),
        your_roster_id=your_roster_id,
    )
```

- [ ] **Step 5: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_league.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dynasty_mcp/context.py src/dynasty_mcp/tools/league.py tests/test_tools/test_league.py
git commit -m "feat: add get_league_context tool"
```

---

### Task 9: `get_roster` tool

**Files:**
- Create: `src/dynasty_mcp/tools/rosters.py`
- Create: `tests/test_tools/test_rosters.py`

Resolves `team` = `"me"` | `roster_id:int` | Sleeper username; attaches slot_type, Player, and Value to each player; reports total value by slot type. Unknown value → `value.current = None` (never throws).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_rosters.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.models import SlotType
from dynasty_mcp.tools.rosters import get_roster

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


async def _seed(mock: respx.Router) -> None:
    mock.get("/league/L1").respond(json=load("sleeper_league.json"))
    mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
    mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
    mock.get("/players/nfl").respond(json=load("sleeper_players.json"))


@pytest.mark.asyncio
async def test_get_roster_me(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        await _seed(sleeper_mock)
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        view = await get_roster(ctx, team="me")

    assert view.entries, "roster should have entries"
    slot_types = {e.slot_type for e in view.entries}
    assert slot_types & {SlotType.ACTIVE, SlotType.BENCH, SlotType.TAXI, SlotType.IR}
    assert view.total_value_active >= 0
    assert view.total_value_taxi >= 0


@pytest.mark.asyncio
async def test_get_roster_by_username(ctx) -> None:
    users = load("sleeper_users.json")
    assert users, "fixture has at least one user"
    target_username = users[0]["username"]

    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        await _seed(sleeper_mock)
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        view = await get_roster(ctx, team=target_username)

    assert view.owner_username == target_username


@pytest.mark.asyncio
async def test_get_roster_unknown_raises(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        await _seed(sleeper_mock)
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        with pytest.raises(ValueError, match="team"):
            await get_roster(ctx, team="nobody_like_this")
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_rosters.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/tools/rosters.py`**

```python
from __future__ import annotations

from typing import Any

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, RosterEntry, RosterView, SlotType, Value


TeamSpec = int | str  # "me" | roster_id | username


async def _resolve_roster(
    ctx: Context, league_id: str, team: TeamSpec
) -> tuple[dict[str, Any], dict[str, Any]]:
    rosters = await ctx.sleeper.get_rosters(league_id)
    users = await ctx.sleeper.get_league_users(league_id)

    def user_by_id(uid: str | None) -> dict[str, Any]:
        return next((u for u in users if u.get("user_id") == uid), {})

    if team == "me":
        me = next(
            (u for u in users if (u.get("username") or "").lower() == ctx.username.lower()),
            None,
        )
        if me is None:
            raise ValueError(f"username {ctx.username!r} not in league")
        roster = next((r for r in rosters if r.get("owner_id") == me["user_id"]), None)
        if roster is None:
            raise ValueError(f"no roster for {ctx.username!r}")
        return roster, me

    if isinstance(team, int):
        roster = next((r for r in rosters if int(r.get("roster_id", 0)) == team), None)
        if roster is None:
            raise ValueError(f"unknown team roster_id={team}")
        return roster, user_by_id(roster.get("owner_id"))

    # string: treat as username
    target_user = next(
        (u for u in users if (u.get("username") or "").lower() == team.lower()), None
    )
    if target_user is None:
        raise ValueError(f"unknown team username={team!r}")
    roster = next(
        (r for r in rosters if r.get("owner_id") == target_user["user_id"]), None
    )
    if roster is None:
        raise ValueError(f"no roster for username={team!r}")
    return roster, target_user


def _classify(
    player_id: str, roster: dict[str, Any]
) -> SlotType:
    if player_id in (roster.get("taxi") or []):
        return SlotType.TAXI
    if player_id in (roster.get("reserve") or []):
        return SlotType.IR
    if player_id in (roster.get("starters") or []):
        return SlotType.ACTIVE
    return SlotType.BENCH


def _player_from_sleeper(pid: str, data: dict[str, Any]) -> Player:
    full_name = (
        data.get("full_name")
        or " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
        or pid
    )
    return Player(
        player_id=pid,
        full_name=full_name,
        position=(data.get("position") or "UNK"),
        team=data.get("team"),
        age=data.get("age"),
        status=data.get("status"),
    )


def _value_map(fc_values: list[dict[str, Any]]) -> dict[str, int]:
    # FantasyCalc payloads use nested {"player": {"sleeperId": "..."}, "value": ...}
    out: dict[str, int] = {}
    for row in fc_values:
        player = row.get("player") or {}
        sid = str(player.get("sleeperId") or "")
        val = row.get("value")
        if sid and val is not None:
            out[sid] = int(val)
    return out


async def get_roster(ctx: Context, *, team: TeamSpec = "me") -> RosterView:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    roster, owner = await _resolve_roster(ctx, ctx.league_id, team)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    entries: list[RosterEntry] = []
    total_active = total_taxi = total_ir = 0
    all_pids: list[str] = list(roster.get("players") or [])

    for pid in all_pids:
        data = players.get(pid, {})
        slot = _classify(pid, roster)
        val = values.get(pid)
        entries.append(
            RosterEntry(
                player=_player_from_sleeper(pid, data),
                slot_type=slot,
                value=Value(current=val),
                starter=pid in (roster.get("starters") or []),
            )
        )
        if val is None:
            continue
        if slot == SlotType.ACTIVE or slot == SlotType.BENCH:
            total_active += val
        elif slot == SlotType.TAXI:
            total_taxi += val
        elif slot == SlotType.IR:
            total_ir += val

    return RosterView(
        roster_id=int(roster.get("roster_id", 0)),
        owner_username=owner.get("username", ""),
        owner_display_name=owner.get("display_name"),
        entries=entries,
        total_value_active=total_active,
        total_value_taxi=total_taxi,
        total_value_ir=total_ir,
    )
```

- [ ] **Step 4: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_rosters.py -v`
Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/tools/rosters.py tests/test_tools/test_rosters.py
git commit -m "feat: add get_roster tool"
```

---

### Task 10: `list_rosters` and `get_team_value_breakdown` tools

**Files:**
- Modify: `src/dynasty_mcp/tools/rosters.py` (append)
- Modify: `tests/test_tools/test_rosters.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_tools/test_rosters.py`:

```python
from dynasty_mcp.tools.rosters import get_team_value_breakdown, list_rosters


@pytest.mark.asyncio
async def test_list_rosters(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        await _seed(sleeper_mock)
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        summaries = await list_rosters(ctx)

    assert len(summaries) >= 1
    for s in summaries:
        assert s.roster_id
        assert s.total_value >= 0
        assert len(s.top_assets) <= 5


@pytest.mark.asyncio
async def test_team_value_breakdown_has_age_cohorts(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        await _seed(sleeper_mock)
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        breakdown = await get_team_value_breakdown(ctx, team="me")

    # Expect keys for age cohorts and positions
    assert set(breakdown.by_age_cohort.keys()) >= {"under_25", "25_28", "29_plus"}
    assert "taxi_stash_value" in breakdown.model_dump()
```

- [ ] **Step 2: Add models used by these tools**

Append to `src/dynasty_mcp/models.py`:

```python
class RosterSummary(BaseModel):
    roster_id: int
    owner_username: str
    total_value: int
    top_assets: list[str]  # player names


class TeamValueBreakdown(BaseModel):
    roster_id: int
    by_position: dict[str, int]
    by_age_cohort: dict[str, int]  # keys: under_25, 25_28, 29_plus, unknown
    taxi_stash_value: int
    ir_value: int
    active_value: int
```

- [ ] **Step 3: Run the tests — expect failures**

Run: `.venv/bin/pytest tests/test_tools/test_rosters.py -v`
Expected: tests referring to `list_rosters` and `get_team_value_breakdown` fail with `ImportError` or `AttributeError`.

- [ ] **Step 4: Append implementations to `src/dynasty_mcp/tools/rosters.py`**

```python
from dynasty_mcp.models import RosterSummary, TeamValueBreakdown


async def list_rosters(ctx: Context) -> list[RosterSummary]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters = await ctx.sleeper.get_rosters(league_id=ctx.league_id)
    users = await ctx.sleeper.get_league_users(ctx.league_id)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    by_user = {u["user_id"]: u for u in users}
    out: list[RosterSummary] = []
    for r in rosters:
        pids = r.get("players") or []
        total = sum(values.get(pid, 0) for pid in pids)
        ranked = sorted(pids, key=lambda pid: values.get(pid, 0), reverse=True)[:5]
        top = [
            _player_from_sleeper(pid, players.get(pid, {})).full_name
            for pid in ranked
        ]
        owner = by_user.get(r.get("owner_id"), {})
        out.append(
            RosterSummary(
                roster_id=int(r["roster_id"]),
                owner_username=owner.get("username", ""),
                total_value=total,
                top_assets=top,
            )
        )
    return out


def _age_cohort(age: int | None) -> str:
    if age is None:
        return "unknown"
    if age < 25:
        return "under_25"
    if age <= 28:
        return "25_28"
    return "29_plus"


async def get_team_value_breakdown(
    ctx: Context, *, team: TeamSpec = "me"
) -> TeamValueBreakdown:
    view = await get_roster(ctx, team=team)
    by_pos: dict[str, int] = {}
    by_age: dict[str, int] = {"under_25": 0, "25_28": 0, "29_plus": 0, "unknown": 0}
    for entry in view.entries:
        val = entry.value.current or 0
        by_pos[entry.player.position] = by_pos.get(entry.player.position, 0) + val
        by_age[_age_cohort(entry.player.age)] += val
    return TeamValueBreakdown(
        roster_id=view.roster_id,
        by_position=by_pos,
        by_age_cohort=by_age,
        taxi_stash_value=view.total_value_taxi,
        ir_value=view.total_value_ir,
        active_value=view.total_value_active,
    )
```

- [ ] **Step 5: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_rosters.py -v`
Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dynasty_mcp/tools/rosters.py src/dynasty_mcp/models.py tests/test_tools/test_rosters.py
git commit -m "feat: add list_rosters and team value breakdown tools"
```

---

### Task 11: `get_player_values` tool

**Files:**
- Create: `src/dynasty_mcp/tools/values.py`
- Create: `tests/test_tools/test_values.py`

Returns a ranked list of players with current FantasyCalc value, filterable by position and rookie status, with optional week-over-week delta. Delta is computed when at least one older snapshot is in the cache; otherwise `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_values.py
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.values import get_player_values

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_top_rb_values(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        out = await get_player_values(ctx, position="RB", limit=5)

    assert len(out) <= 5
    for row in out:
        assert row.player.position == "RB"
        assert row.value.current is not None


@pytest.mark.asyncio
async def test_delta_7d_computed_from_prior_snapshot(ctx) -> None:
    # Seed an older snapshot manually
    fc = load("fantasycalc_values.json")
    # Reduce every value by 100 for the older snapshot to give a stable delta
    older = [{**row, "value": int(row["value"]) - 100} for row in fc]
    ctx.cache.put_values_snapshot(
        older, fetched_at=datetime.now(timezone.utc) - timedelta(days=7)
    )
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        fc_mock.get("/values/current").respond(json=fc)
        out = await get_player_values(ctx, limit=3)

    assert all(row.value.delta_7d == 100 for row in out)
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_values.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/tools/values.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, Value


class PlayerValueRow(BaseModel):
    player: Player
    value: Value


def _build_index(fc_rows: list[dict[str, Any]]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for row in fc_rows:
        sid = str((row.get("player") or {}).get("sleeperId") or "")
        if sid and row.get("value") is not None:
            idx[sid] = int(row["value"])
    return idx


def _older_snapshot(ctx: Context, window: timedelta) -> dict[str, int] | None:
    # Pull the most recent snapshot older than `window` ago.
    target = datetime.now(timezone.utc) - window
    row = ctx.cache.conn.execute(
        "SELECT data FROM values_snapshots WHERE fetched_at <= ? "
        "ORDER BY fetched_at DESC LIMIT 1",
        (target.isoformat(),),
    ).fetchone()
    if not row:
        return None
    import json as _json

    return _build_index(_json.loads(row[0]))


async def get_player_values(
    ctx: Context,
    *,
    position: str | None = None,
    rookies_only: bool = False,
    limit: int = 50,
) -> list[PlayerValueRow]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    fc = await ctx.fantasycalc.get_current(league)
    players = await ctx.sleeper.get_players()
    now_idx = _build_index(fc)
    prior_idx = _older_snapshot(ctx, timedelta(days=7)) or {}

    rows: list[PlayerValueRow] = []
    for pid, val in sorted(now_idx.items(), key=lambda kv: kv[1], reverse=True):
        data = players.get(pid)
        if data is None:
            continue
        if position and data.get("position") != position:
            continue
        if rookies_only and int(data.get("years_exp") or 99) != 0:
            continue
        delta_7d = (val - prior_idx[pid]) if pid in prior_idx else None
        rows.append(
            PlayerValueRow(
                player=Player(
                    player_id=pid,
                    full_name=(
                        data.get("full_name")
                        or " ".join(
                            p for p in (data.get("first_name"), data.get("last_name")) if p
                        )
                        or pid
                    ),
                    position=data.get("position") or "UNK",
                    team=data.get("team"),
                    age=data.get("age"),
                    status=data.get("status"),
                ),
                value=Value(current=val, delta_7d=delta_7d),
            )
        )
        if len(rows) >= limit:
            break
    return rows
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_values.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/tools/values.py tests/test_tools/test_values.py
git commit -m "feat: add get_player_values tool with week-over-week delta"
```

---

### Task 12: `get_matchup` tool

**Files:**
- Create: `src/dynasty_mcp/tools/matchups.py`
- Create: `tests/test_tools/test_matchups.py`

Returns your roster's matchup for the given (or current) week: your starters, opponent's starters, both sides' bench value. Projections: best-effort from Sleeper's `api.sleeper.com/projections/nfl/<season>/<week>` endpoint; if that fails, projections are `None` on each player.

- [ ] **Step 1: Record projections fixture**

```bash
# Add to scripts/record_fixtures.py temporarily or run one-off:
.venv/bin/python -c "
import httpx, json, pathlib, os
season = os.environ.get('SEASON', '2025')
week = os.environ.get('WEEK', '7')
r = httpx.get(f'https://api.sleeper.com/projections/nfl/{season}/{week}', params={'season_type':'regular','position[]':['QB','RB','WR','TE','K','DEF']}, timeout=30)
pathlib.Path(f'tests/fixtures/sleeper_projections_week{week}.json').write_text(json.dumps(r.json(), indent=2)[:200000])
print('wrote', f'tests/fixtures/sleeper_projections_week{week}.json')
"
```

If the projections endpoint returns an error or empty, save `[]` instead so the test can still exercise the `projections=None` fallback branch.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_tools/test_matchups.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.matchups import get_matchup

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_get_matchup_shape(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock, respx.mock(
        base_url="https://api.sleeper.com"
    ) as proj_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        sleeper_mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
        sleeper_mock.get("/league/L1/matchups/7").respond(
            json=load("sleeper_matchups_week7.json")
        )
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        sleeper_mock.get("/state/nfl").respond(json=load("sleeper_state.json"))
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        proj_mock.get("/projections/nfl/2025/7").respond(
            json=load("sleeper_projections_week7.json")
        )

        result = await get_matchup(ctx, week=7)

    assert result.week == 7
    assert result.my_starters, "should have starters"
    if result.opponent_starters is not None:
        assert len(result.opponent_starters) >= 0
```

- [ ] **Step 3: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_matchups.py -v`
Expected: `ImportError`.

- [ ] **Step 4: Implement `src/dynasty_mcp/tools/matchups.py`**

```python
from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, RosterEntry, SlotType, Value
from dynasty_mcp.tools.league import _resolve_your_roster_id
from dynasty_mcp.tools.rosters import _player_from_sleeper, _value_map


class MatchupView(BaseModel):
    week: int
    my_roster_id: int
    opponent_roster_id: int | None
    my_starters: list[RosterEntry]
    opponent_starters: list[RosterEntry] | None
    my_bench_value: int
    opponent_bench_value: int | None


async def _fetch_projections(season: str, week: int) -> dict[str, float]:
    try:
        async with httpx.AsyncClient(
            base_url="https://api.sleeper.com", timeout=15
        ) as c:
            resp = await c.get(
                f"/projections/nfl/{season}/{week}",
                params=[
                    ("season_type", "regular"),
                    ("position[]", "QB"),
                    ("position[]", "RB"),
                    ("position[]", "WR"),
                    ("position[]", "TE"),
                    ("position[]", "K"),
                    ("position[]", "DEF"),
                ],
            )
            resp.raise_for_status()
            rows = resp.json() or []
    except (httpx.HTTPError, ValueError):
        return {}
    out: dict[str, float] = {}
    for row in rows:
        pid = str(row.get("player_id") or "")
        stats = row.get("stats") or {}
        pts = stats.get("pts_ppr") or stats.get("pts_half_ppr") or stats.get("pts_std")
        if pid and pts is not None:
            out[pid] = float(pts)
    return out


async def get_matchup(ctx: Context, *, week: int | None = None) -> MatchupView:
    if not ctx.league_id:
        raise ValueError("league_id required")
    state = await ctx.sleeper.get_state()
    resolved_week = int(week if week is not None else state.get("week") or 1)

    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters = await ctx.sleeper.get_rosters(ctx.league_id)
    matchups = await ctx.sleeper.get_matchups(ctx.league_id, resolved_week)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)
    my_roster_id = await _resolve_your_roster_id(ctx, ctx.league_id)
    projections = await _fetch_projections(
        str(league.get("season") or ctx.season), resolved_week
    )

    my_match = next(
        (m for m in matchups if int(m.get("roster_id", 0)) == my_roster_id), None
    )
    if my_match is None:
        raise ValueError(f"no matchup for roster {my_roster_id} in week {resolved_week}")
    matchup_id = my_match.get("matchup_id")
    opp_match = next(
        (
            m
            for m in matchups
            if m.get("matchup_id") == matchup_id
            and int(m.get("roster_id", 0)) != my_roster_id
        ),
        None,
    )

    def build(match: dict[str, Any]) -> tuple[list[RosterEntry], int]:
        starters = [pid for pid in (match.get("starters") or []) if pid]
        all_players = match.get("players") or []
        starter_set = set(starters)
        entries = [
            RosterEntry(
                player=_player_from_sleeper(pid, players.get(pid, {})),
                slot_type=SlotType.ACTIVE,
                value=Value(current=values.get(pid), delta_7d=None),
                starter=True,
                projection=projections.get(pid),
            )
            for pid in starters
        ]
        bench_value = sum(
            values.get(pid, 0) for pid in all_players if pid not in starter_set
        )
        return entries, bench_value

    my_entries, my_bench = build(my_match)
    if opp_match is None:
        return MatchupView(
            week=resolved_week,
            my_roster_id=my_roster_id,
            opponent_roster_id=None,
            my_starters=my_entries,
            opponent_starters=None,
            my_bench_value=my_bench,
            opponent_bench_value=None,
        )
    opp_entries, opp_bench = build(opp_match)
    return MatchupView(
        week=resolved_week,
        my_roster_id=my_roster_id,
        opponent_roster_id=int(opp_match.get("roster_id", 0)),
        my_starters=my_entries,
        opponent_starters=opp_entries,
        my_bench_value=my_bench,
        opponent_bench_value=opp_bench,
    )
```

- [ ] **Step 5: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_matchups.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dynasty_mcp/tools/matchups.py tests/test_tools/test_matchups.py tests/fixtures/sleeper_projections_week7.json
git commit -m "feat: add get_matchup tool with best-effort projections"
```

---

### Task 13: `get_free_agents` tool

**Files:**
- Create: `src/dynasty_mcp/tools/waivers.py`
- Create: `tests/test_tools/test_waivers.py`

"Unrostered" = any player_id present in the Sleeper players dataset that does not appear in any roster's `players` array. Ranked by FantasyCalc value.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_waivers.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.waivers import get_free_agents

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_free_agents_excludes_rostered_players(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        fas = await get_free_agents(ctx, limit=10)

    rostered = {
        pid
        for r in load("sleeper_rosters.json")
        for pid in (r.get("players") or [])
    }
    for row in fas:
        assert row.player.player_id not in rostered
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_waivers.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/tools/waivers.py`**

```python
from __future__ import annotations

from dynasty_mcp.context import Context
from dynasty_mcp.tools.rosters import _player_from_sleeper, _value_map
from dynasty_mcp.tools.values import PlayerValueRow
from dynasty_mcp.models import Value


async def get_free_agents(
    ctx: Context,
    *,
    position: str | None = None,
    min_value: int = 0,
    limit: int = 25,
) -> list[PlayerValueRow]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters = await ctx.sleeper.get_rosters(ctx.league_id)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    rostered: set[str] = set()
    for r in rosters:
        rostered.update(r.get("players") or [])

    rows: list[PlayerValueRow] = []
    for pid, val in sorted(values.items(), key=lambda kv: kv[1], reverse=True):
        if pid in rostered:
            continue
        if val < min_value:
            continue
        data = players.get(pid)
        if data is None:
            continue
        if position and data.get("position") != position:
            continue
        rows.append(
            PlayerValueRow(
                player=_player_from_sleeper(pid, data),
                value=Value(current=val),
            )
        )
        if len(rows) >= limit:
            break
    return rows
```

- [ ] **Step 4: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_waivers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/tools/waivers.py tests/test_tools/test_waivers.py
git commit -m "feat: add get_free_agents tool"
```

---

### Task 14: `get_trending` tool

**Files:**
- Modify: `src/dynasty_mcp/tools/waivers.py` (append)
- Modify: `tests/test_tools/test_waivers.py` (append)

- [ ] **Step 1: Append failing test**

Append to `tests/test_tools/test_waivers.py`:

```python
from dynasty_mcp.tools.waivers import get_trending


@pytest.mark.asyncio
async def test_get_trending_add(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock:
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        sleeper_mock.get("/players/nfl/trending/add").respond(
            json=load("sleeper_trending_add.json")
        )
        trending = await get_trending(ctx, window="24h", type="add")

    assert len(trending) > 0
    for row in trending:
        assert row.count > 0
        assert row.player.full_name
```

- [ ] **Step 2: Add model**

Append to `src/dynasty_mcp/models.py`:

```python
class TrendingRow(BaseModel):
    player: Player
    count: int
```

- [ ] **Step 3: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_waivers.py::test_get_trending_add -v`
Expected: `ImportError` or `AttributeError`.

- [ ] **Step 4: Append implementation to `src/dynasty_mcp/tools/waivers.py`**

```python
from typing import Literal

from dynasty_mcp.models import TrendingRow


async def get_trending(
    ctx: Context,
    *,
    window: Literal["24h", "7d"] = "24h",
    type: Literal["add", "drop"] = "add",
    limit: int = 25,
) -> list[TrendingRow]:
    lookback = 24 if window == "24h" else 24 * 7
    raw = await ctx.sleeper.get_trending(type, lookback_hours=lookback, limit=limit)
    players = await ctx.sleeper.get_players()
    out: list[TrendingRow] = []
    for row in raw:
        pid = str(row.get("player_id") or "")
        data = players.get(pid)
        if data is None:
            continue
        out.append(
            TrendingRow(
                player=_player_from_sleeper(pid, data),
                count=int(row.get("count") or 0),
            )
        )
    return out
```

The module already imports `_player_from_sleeper` at the top from Task 13 — no additional import needed.

- [ ] **Step 5: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_waivers.py -v`
Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dynasty_mcp/tools/waivers.py src/dynasty_mcp/models.py tests/test_tools/test_waivers.py
git commit -m "feat: add get_trending tool"
```

---

### Task 15: `get_transactions` tool

**Files:**
- Create: `src/dynasty_mcp/tools/transactions.py`
- Create: `tests/test_tools/test_transactions.py`

Fetches recent transactions. Since Sleeper returns transactions keyed by week, we iterate weeks within the `days` window (roughly: days / 7 weeks back, capped at the current season).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_transactions.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.transactions import get_transactions

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_get_transactions(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock:
        sleeper_mock.get("/state/nfl").respond(json=load("sleeper_state.json"))
        # Respond to any week-based transactions URL with the week 7 fixture
        sleeper_mock.get(url__regex=r"/league/L1/transactions/\d+").respond(
            json=load("sleeper_transactions_week7.json")
        )
        out = await get_transactions(ctx, days=14)

    assert isinstance(out, list)
    for tx in out:
        assert "type" in tx
        assert "status" in tx
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_transactions.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/tools/transactions.py`**

```python
from __future__ import annotations

import math
from typing import Any, Literal

from dynasty_mcp.context import Context


async def get_transactions(
    ctx: Context,
    *,
    days: int = 7,
    type: Literal["trade", "waiver", "free_agent"] | None = None,
) -> list[dict[str, Any]]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    state = await ctx.sleeper.get_state()
    current_week = int(state.get("week") or 1)
    weeks_back = max(1, math.ceil(days / 7))
    weeks = [
        w for w in range(current_week, current_week - weeks_back - 1, -1) if w >= 1
    ]

    out: list[dict[str, Any]] = []
    for w in weeks:
        batch = await ctx.sleeper.get_transactions(ctx.league_id, w)
        for tx in batch:
            if type and tx.get("type") != type:
                continue
            out.append(tx)
    return out
```

- [ ] **Step 4: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_transactions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/tools/transactions.py tests/test_tools/test_transactions.py
git commit -m "feat: add get_transactions tool"
```

---

### Task 16: `get_draft` tool

**Files:**
- Create: `src/dynasty_mcp/tools/draft.py`
- Create: `tests/test_tools/test_draft.py`

Returns the next scheduled draft for the league (or most recent completed), the user's owned picks (after applying traded picks), and the rookie pool with values.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_draft.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.draft import get_draft

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_get_draft_returns_picks_and_pool(ctx) -> None:
    drafts = load("sleeper_drafts.json")
    assert drafts, "need at least one draft in fixture"
    draft_id = drafts[0]["draft_id"]

    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        sleeper_mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
        sleeper_mock.get("/league/L1/drafts").respond(json=load("sleeper_drafts.json"))
        sleeper_mock.get("/league/L1/traded_picks").respond(
            json=load("sleeper_traded_picks.json")
        )
        sleeper_mock.get(f"/draft/{draft_id}").respond(json=load("sleeper_draft.json"))
        sleeper_mock.get(f"/draft/{draft_id}/picks").respond(
            json=load("sleeper_draft_picks.json")
        )
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))

        result = await get_draft(ctx)

    assert result.draft_id == draft_id
    assert result.status in ("pre_draft", "drafting", "completed")
    # If pre_draft, my_picks should be computed from traded_picks; if completed, from picks
    assert isinstance(result.my_picks, list)
    assert isinstance(result.rookie_pool, list)
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_draft.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/tools/draft.py`**

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, Value
from dynasty_mcp.tools.league import _resolve_your_roster_id
from dynasty_mcp.tools.rosters import _player_from_sleeper, _value_map


class DraftPick(BaseModel):
    season: str
    round: int
    # Original owner (roster_id) the pick came from
    original_roster_id: int
    # Current owner (roster_id) after all trades
    current_roster_id: int
    # Overall pick number if drafted; None if upcoming
    pick_number: int | None = None
    # Player drafted with this pick; None if upcoming
    player: Player | None = None


class DraftView(BaseModel):
    draft_id: str
    status: Literal["pre_draft", "drafting", "completed"]
    season: str
    type: str  # "snake" | "auction" | "linear" etc from Sleeper
    my_picks: list[DraftPick]
    all_picks: list[DraftPick]
    rookie_pool: list[Player]  # unrostered rookies ranked by value


async def get_draft(
    ctx: Context, *, year: str | None = None
) -> DraftView:
    if not ctx.league_id:
        raise ValueError("league_id required")

    drafts = await ctx.sleeper.get_drafts(ctx.league_id)
    if not drafts:
        raise ValueError("no drafts found for league")
    # Prefer requested year, else the most-recent / next draft
    if year:
        draft = next((d for d in drafts if str(d.get("season")) == str(year)), None)
        if draft is None:
            raise ValueError(f"no draft for year {year}")
    else:
        # Sleeper returns drafts most-recent first; pick the first pre_draft,
        # else the most recent.
        draft = next((d for d in drafts if d.get("status") == "pre_draft"), drafts[0])

    draft_id = draft["draft_id"]
    draft_full = await ctx.sleeper.get_draft(draft_id)
    picks_raw = await ctx.sleeper.get_draft_picks(draft_id)
    traded = await ctx.sleeper.get_traded_picks(ctx.league_id)
    my_roster_id = await _resolve_your_roster_id(ctx, ctx.league_id)

    league = await ctx.sleeper.get_league(ctx.league_id)
    players = await ctx.sleeper.get_players()
    rosters = await ctx.sleeper.get_rosters(ctx.league_id)
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    status = draft.get("status") or "pre_draft"
    season = str(draft.get("season") or "")
    draft_type = draft.get("type") or "snake"

    all_picks: list[DraftPick] = []
    if status == "completed" or picks_raw:
        for p in picks_raw:
            pid = p.get("player_id")
            all_picks.append(
                DraftPick(
                    season=season,
                    round=int(p.get("round") or 0),
                    original_roster_id=int(p.get("roster_id") or 0),
                    current_roster_id=int(p.get("roster_id") or 0),
                    pick_number=p.get("pick_no"),
                    player=_player_from_sleeper(pid, players.get(pid, {}))
                    if pid
                    else None,
                )
            )
    else:
        # Build pre-draft picks from draft.settings + traded_picks
        rounds = int((draft_full.get("settings") or {}).get("rounds") or 4)
        num_teams = int(league.get("total_rosters") or 12)
        # Start with each roster owning its own pick in each round
        pick_owner: dict[tuple[str, int, int], int] = {
            (season, r, roster_id): roster_id
            for r in range(1, rounds + 1)
            for roster_id in range(1, num_teams + 1)
        }
        # Apply traded picks for this season
        for tp in traded:
            if str(tp.get("season")) != season:
                continue
            key = (season, int(tp["round"]), int(tp["roster_id"]))
            if key in pick_owner:
                pick_owner[key] = int(tp["owner_id"])
        for (s, r, orig), curr in pick_owner.items():
            all_picks.append(
                DraftPick(
                    season=s,
                    round=r,
                    original_roster_id=orig,
                    current_roster_id=curr,
                    pick_number=None,
                    player=None,
                )
            )

    my_picks = [p for p in all_picks if p.current_roster_id == my_roster_id]

    rostered = {pid for r in rosters for pid in (r.get("players") or [])}
    rookie_pool: list[Player] = []
    for pid, val in sorted(values.items(), key=lambda kv: kv[1], reverse=True):
        data = players.get(pid)
        if data is None or pid in rostered:
            continue
        if int(data.get("years_exp") or 99) != 0:
            continue
        rookie_pool.append(_player_from_sleeper(pid, data))

    return DraftView(
        draft_id=draft_id,
        status=status,  # type: ignore[arg-type]
        season=season,
        type=draft_type,
        my_picks=my_picks,
        all_picks=all_picks,
        rookie_pool=rookie_pool,
    )
```

- [ ] **Step 4: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_draft.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/tools/draft.py tests/test_tools/test_draft.py
git commit -m "feat: add get_draft tool"
```

---

### Task 17: `refresh_cache` admin tool

**Files:**
- Create: `src/dynasty_mcp/tools/admin.py`
- Create: `tests/test_tools/test_admin.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_admin.py
import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.admin import refresh_cache

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_refresh_players_only(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        route = mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        result = await refresh_cache(ctx, what="players")
        assert route.call_count == 1
        assert result.refreshed == ["players"]


@pytest.mark.asyncio
async def test_refresh_all(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await refresh_cache(ctx, what="all")
        assert set(result.refreshed) == {"players", "values"}
```

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_tools/test_admin.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/tools/admin.py`**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from dynasty_mcp.context import Context


class RefreshResult(BaseModel):
    refreshed: list[str]


async def refresh_cache(
    ctx: Context, *, what: Literal["players", "values", "all"] = "all"
) -> RefreshResult:
    refreshed: list[str] = []
    if what in ("players", "all"):
        await ctx.sleeper.get_players(force=True)
        refreshed.append("players")
    if what in ("values", "all"):
        if not ctx.league_id:
            raise ValueError("league_id required to refresh values")
        league = await ctx.sleeper.get_league(ctx.league_id)
        await ctx.fantasycalc.get_current(league, force=True)
        refreshed.append("values")
    return RefreshResult(refreshed=refreshed)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/bin/pytest tests/test_tools/test_admin.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/tools/admin.py tests/test_tools/test_admin.py
git commit -m "feat: add refresh_cache admin tool"
```

---

## Phase 4 — Server wiring

### Task 18: FastMCP server and entrypoint

**Files:**
- Create: `src/dynasty_mcp/server.py`
- Modify: `src/dynasty_mcp/__main__.py`
- Create: `tests/test_server.py`

Wires all tools into a FastMCP instance. At startup, loads config, opens cache, resolves `league_id` from username if not provided, builds a Context.

- [ ] **Step 1: Write the failing test (server can list tools)**

```python
# tests/test_server.py
from pathlib import Path

import pytest

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import Context
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient
from dynasty_mcp.sources.sleeper import SleeperClient
from dynasty_mcp.server import build_server


def test_server_registers_expected_tools(tmp_path: Path) -> None:
    cache = Cache.open(tmp_path / "c.db")
    ctx = Context(
        cache=cache,
        sleeper=SleeperClient(cache=cache),
        fantasycalc=FantasyCalcClient(cache=cache),
        username="alice",
        league_id="L1",
        season="2025",
    )
    server = build_server(ctx)
    names = {t.name for t in server.list_tools()}
    expected = {
        "get_league_context",
        "get_roster",
        "list_rosters",
        "get_team_value_breakdown",
        "get_player_values",
        "get_matchup",
        "get_free_agents",
        "get_trending",
        "get_transactions",
        "get_draft",
        "refresh_cache",
    }
    assert expected <= names
```

Note: the exact FastMCP API for listing tools may be `.list_tools()`, `.tools`, or require an async call depending on FastMCP 2.x version. If the assertion fails because the accessor is different, adjust the test to use `server._tools` or whatever FastMCP 2.x exposes — but keep the same 11 names.

- [ ] **Step 2: Run the test — expect failure**

Run: `.venv/bin/pytest tests/test_server.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `src/dynasty_mcp/server.py`**

```python
from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from dynasty_mcp.context import Context
from dynasty_mcp.tools.admin import refresh_cache as tool_refresh_cache
from dynasty_mcp.tools.draft import get_draft as tool_get_draft
from dynasty_mcp.tools.league import get_league_context as tool_get_league_context
from dynasty_mcp.tools.matchups import get_matchup as tool_get_matchup
from dynasty_mcp.tools.rosters import (
    get_roster as tool_get_roster,
    get_team_value_breakdown as tool_get_team_value_breakdown,
    list_rosters as tool_list_rosters,
)
from dynasty_mcp.tools.transactions import get_transactions as tool_get_transactions
from dynasty_mcp.tools.values import get_player_values as tool_get_player_values
from dynasty_mcp.tools.waivers import (
    get_free_agents as tool_get_free_agents,
    get_trending as tool_get_trending,
)


def build_server(ctx: Context) -> FastMCP:
    mcp = FastMCP("dynasty-mcp")

    @mcp.tool()
    async def get_league_context() -> Any:
        return (await tool_get_league_context(ctx)).model_dump()

    @mcp.tool()
    async def get_roster(team: str | int = "me") -> Any:
        # FastMCP serializes str|int; keep "me" string path
        return (await tool_get_roster(ctx, team=team)).model_dump()

    @mcp.tool()
    async def list_rosters() -> Any:
        return [r.model_dump() for r in await tool_list_rosters(ctx)]

    @mcp.tool()
    async def get_team_value_breakdown(team: str | int = "me") -> Any:
        return (await tool_get_team_value_breakdown(ctx, team=team)).model_dump()

    @mcp.tool()
    async def get_player_values(
        position: str | None = None,
        rookies_only: bool = False,
        limit: int = 50,
    ) -> Any:
        rows = await tool_get_player_values(
            ctx, position=position, rookies_only=rookies_only, limit=limit
        )
        return [r.model_dump() for r in rows]

    @mcp.tool()
    async def get_matchup(week: int | None = None) -> Any:
        return (await tool_get_matchup(ctx, week=week)).model_dump()

    @mcp.tool()
    async def get_free_agents(
        position: str | None = None,
        min_value: int = 0,
        limit: int = 25,
    ) -> Any:
        rows = await tool_get_free_agents(
            ctx, position=position, min_value=min_value, limit=limit
        )
        return [r.model_dump() for r in rows]

    @mcp.tool()
    async def get_trending(
        window: Literal["24h", "7d"] = "24h",
        type: Literal["add", "drop"] = "add",
        limit: int = 25,
    ) -> Any:
        rows = await tool_get_trending(ctx, window=window, type=type, limit=limit)
        return [r.model_dump() for r in rows]

    @mcp.tool()
    async def get_transactions(
        days: int = 7,
        type: Literal["trade", "waiver", "free_agent"] | None = None,
    ) -> Any:
        return await tool_get_transactions(ctx, days=days, type=type)

    @mcp.tool()
    async def get_draft(year: str | None = None) -> Any:
        return (await tool_get_draft(ctx, year=year)).model_dump()

    @mcp.tool()
    async def refresh_cache(
        what: Literal["players", "values", "all"] = "all",
    ) -> Any:
        return (await tool_refresh_cache(ctx, what=what)).model_dump()

    return mcp
```

- [ ] **Step 4: Implement `src/dynasty_mcp/__main__.py`**

```python
from __future__ import annotations

import asyncio

from dynasty_mcp.cache import Cache
from dynasty_mcp.config import load_config
from dynasty_mcp.context import Context
from dynasty_mcp.server import build_server
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient
from dynasty_mcp.sources.sleeper import SleeperClient


async def _resolve_league_id(
    sleeper: SleeperClient, username: str, season: str
) -> str:
    user = await sleeper.get_user(username)
    leagues = await sleeper.get_user_leagues(user["user_id"], season)
    if len(leagues) == 1:
        return leagues[0]["league_id"]
    names = ", ".join(f"{l['league_id']}:{l['name']}" for l in leagues)
    raise SystemExit(
        f"Ambiguous league for {username!r} (found {len(leagues)}). "
        f"Set sleeper.league_id in config. Options: {names}"
    )


def main() -> None:
    config = load_config()
    cache = Cache.open(config.cache_path)
    sleeper = SleeperClient(cache=cache, refresh_days=config.players_refresh_days)
    fantasycalc = FantasyCalcClient(
        cache=cache, refresh_hours=config.values_refresh_hours
    )

    state = asyncio.run(sleeper.get_state())
    season = str(state.get("season") or "2025")
    league_id = config.sleeper_league_id or asyncio.run(
        _resolve_league_id(sleeper, config.sleeper_username, season)
    )

    ctx = Context(
        cache=cache,
        sleeper=sleeper,
        fantasycalc=fantasycalc,
        username=config.sleeper_username,
        league_id=league_id,
        season=season,
    )
    server = build_server(ctx)
    server.run()  # stdio transport is the FastMCP default


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_server.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/pytest -v`
Expected: every test passes.

- [ ] **Step 7: Commit**

```bash
git add src/dynasty_mcp/server.py src/dynasty_mcp/__main__.py tests/test_server.py
git commit -m "feat: wire FastMCP server and entrypoint"
```

---

### Task 19: README, config example, Claude Code registration

**Files:**
- Modify: `README.md`
- Create: `examples/config.toml`

- [ ] **Step 1: Write `examples/config.toml`**

```toml
[sleeper]
username = "your_sleeper_username"
# league_id is optional if your user has exactly one NFL league this season
# league_id = "123456789012345678"

[values]
source = "fantasycalc"

[cache]
# path defaults to ~/Library/Application Support/dynasty-mcp/cache.db on macOS
players_refresh_days = 7
values_refresh_hours = 24
```

- [ ] **Step 2: Rewrite `README.md`**

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add README.md examples/config.toml
git commit -m "docs: add README and example config"
```

---

### Task 20: Manual contract test against live league

**Files:**
- Create: `tests/test_contract.py`

Optional, manually-run. Not in default pytest run.

- [ ] **Step 1: Write the contract test**

```python
# tests/test_contract.py
"""
Live contract test. Skipped unless DYNASTY_LIVE=1 is set.

Run:
    DYNASTY_LIVE=1 .venv/bin/pytest tests/test_contract.py -v -s

Verifies that the real Sleeper + FantasyCalc APIs still match our client assumptions
by running get_league_context and get_roster against the user's real league.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.league import get_league_context
from dynasty_mcp.tools.rosters import get_roster

pytestmark = pytest.mark.skipif(
    os.environ.get("DYNASTY_LIVE") != "1",
    reason="live contract test — opt in with DYNASTY_LIVE=1",
)


@pytest.mark.asyncio
async def test_live_league_context(tmp_path: Path) -> None:
    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    result = await get_league_context(ctx)
    assert result.league_id == league_id
    assert result.num_teams >= 2


@pytest.mark.asyncio
async def test_live_my_roster_returns_players(tmp_path: Path) -> None:
    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    view = await get_roster(ctx, team="me")
    assert view.entries
```

- [ ] **Step 2: Run it once manually against the real league**

```bash
DYNASTY_LIVE=1 SLEEPER_USERNAME=<you> SLEEPER_LEAGUE_ID=<id> \
    .venv/bin/pytest tests/test_contract.py -v -s
```

Expected: both tests pass against the live APIs.

- [ ] **Step 3: Verify the default test run still skips this file**

Run: `.venv/bin/pytest -v`
Expected: the two contract tests report as `SKIPPED`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_contract.py
git commit -m "test: add manual live contract tests (opt-in via DYNASTY_LIVE=1)"
```

---

## Post-implementation validation

After Task 20:

- [ ] **Register with Claude Code** (copy `examples/config.toml` to `~/.config/dynasty-mcp/config.toml`, add the `mcpServers` entry to `~/.claude.json`).
- [ ] **Start Claude Code**, confirm the `dynasty` server connects and lists 11 tools.
- [ ] **Smoke test one prompt per use case** (listed in the spec's success criteria) and confirm Claude can answer using only the exposed tools.

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| Read-only MCP over Sleeper + FantasyCalc | 6, 7 |
| Python + FastMCP, stdio transport | 1, 18 |
| SQLite cache at platformdirs user data dir | 3 |
| Config via `~/.config/dynasty-mcp/config.toml` | 2 |
| No auth (public APIs) | 6, 7 |
| Ten primitive tools + refresh_cache | 8–17 |
| Taxi squad flagged in `get_roster`, separated in breakdown | 9, 10 |
| Shared `team` param semantics | 9, 10 |
| `week`, `year` defaults with offseason handling | 8, 12, 16 |
| Recorded-fixture tests via respx | 5, 6, 7, all tool tests |
| Contract test opt-in via env var | 20 |
| Weekly player dataset refresh | 6 |
| 24h values refresh + timestamped snapshots for deltas | 7, 11 |
| Error handling: stale cache, missing FC values, invalid config, bounded retry | 2, 3, 6, 7, 9 (value=None path) |
| Claude Code registration docs | 19 |
