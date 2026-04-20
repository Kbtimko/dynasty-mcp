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
