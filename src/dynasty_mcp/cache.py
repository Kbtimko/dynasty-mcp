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
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
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
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
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
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
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
