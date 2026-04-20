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
    fc = load("fantasycalc_values.json")
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
