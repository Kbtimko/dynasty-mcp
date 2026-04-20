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
    return build_test_context(cache=cache, username="dakeif", league_id="L1")


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
    target_username = users[0].get("username") or users[0]["display_name"]

    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        await _seed(sleeper_mock)
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))
        view = await get_roster(ctx, team=target_username)

    assert view.owner_username == target_username


@pytest.mark.asyncio
async def test_get_roster_unknown_raises(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1", assert_all_called=False) as sleeper_mock:
        await _seed(sleeper_mock)
        with pytest.raises(ValueError, match="team"):
            await get_roster(ctx, team="nobody_like_this")
