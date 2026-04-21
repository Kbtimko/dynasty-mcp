from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.reset_optimizer import reset_optimizer

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
async def test_reset_optimizer_returns_five_options(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    assert result.roster_id == 7
    assert len(result.options) == 5
    assert result.options == sorted(result.options, key=lambda o: o.protected_value, reverse=True)


@pytest.mark.asyncio
async def test_reset_optimizer_rank1_rb_te_is_achane(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    # De'Von Achane (player_id "9226") is highest-value RB/TE on dakeif's roster
    assert result.options[0].protected.rb_te.player.player_id == "9226"


@pytest.mark.asyncio
async def test_reset_optimizer_value_at_risk_is_positive(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    assert result.options[0].value_at_risk > 0


@pytest.mark.asyncio
async def test_reset_optimizer_team_me_equals_team_7(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result_me = await reset_optimizer(ctx, team="me")

    with respx.mock(base_url="https://api.sleeper.app/v1", assert_all_called=False) as sm, respx.mock(
        base_url="https://api.fantasycalc.com", assert_all_called=False
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result_7 = await reset_optimizer(ctx, team=7)

    assert result_me.roster_id == result_7.roster_id == 7


@pytest.mark.asyncio
async def test_reset_optimizer_rank1_swaps_empty(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    assert result.options[0].swaps_from_top == []


@pytest.mark.asyncio
async def test_reset_optimizer_lower_ranks_have_swaps(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    # At least one of ranks 2-5 should differ from rank 1 in some starter slot
    swapped_options = [o for o in result.options[1:] if o.swaps_from_top]
    assert len(swapped_options) >= 1


@pytest.mark.asyncio
async def test_reset_optimizer_result_is_serializable(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    dumped = result.model_dump(mode="json")
    assert isinstance(dumped["options"], list)
    assert "protected" in dumped["options"][0]


@pytest.mark.asyncio
async def test_reset_optimizer_no_duplicate_swap_targets(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    for option in result.options:
        to_players = [s.to_player for s in option.swaps_from_top]
        assert len(to_players) == len(set(to_players)), (
            f"Duplicate swap targets in rank {option.rank}: {to_players}"
        )
