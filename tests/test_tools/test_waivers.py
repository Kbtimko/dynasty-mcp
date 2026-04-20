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
