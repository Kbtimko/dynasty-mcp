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
