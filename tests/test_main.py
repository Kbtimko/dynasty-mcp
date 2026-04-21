from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.config import ConfigError
from dynasty_mcp.sources.sleeper import SleeperClient
from dynasty_mcp.__main__ import _resolve_league_id

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
async def test_resolve_league_id_raises_on_unknown_user(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/user/nobody").respond(content=b"null", headers={"content-type": "application/json"})
        with pytest.raises(ConfigError, match="nobody"):
            await _resolve_league_id(client, "nobody", "2025")


@pytest.mark.asyncio
async def test_resolve_league_id_returns_single_league(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/user/dakeif").respond(json=load("sleeper_user.json"))
        user_id = load("sleeper_user.json")["user_id"]
        leagues = load("sleeper_user_leagues.json")[:1]
        mock.get(f"/user/{user_id}/leagues/nfl/2025").respond(json=leagues)
        result = await _resolve_league_id(client, "dakeif", "2025")
        assert result == leagues[0]["league_id"]
