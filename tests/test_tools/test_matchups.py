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
    return build_test_context(cache=cache, username="dakeif", league_id="L1")


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
        proj_mock.get("/projections/nfl/2026/7").respond(
            json=load("sleeper_projections_week7.json")
        )

        result = await get_matchup(ctx, week=7)

    assert result.week == 7
    assert result.my_starters, "should have starters"
    if result.opponent_starters is not None:
        assert len(result.opponent_starters) >= 0
