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
