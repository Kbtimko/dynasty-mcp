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
