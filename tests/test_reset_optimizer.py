from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.reset_optimizer import reset_optimizer

FIX = Path(__file__).parent / "fixtures"
LEAGUE_ID = "1335327387256119296"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    cache.put_values_snapshot(load("fantasycalc_values.json"), fetched_at=datetime.now(timezone.utc))
    cache.put_players(load("sleeper_players.json"), fetched_at=datetime.now(timezone.utc))
    return build_test_context(cache=cache, username="dakeif", league_id=LEAGUE_ID)


def _seed(mock: respx.Router) -> None:
    mock.get(f"/league/{LEAGUE_ID}").respond(json=load("sleeper_league.json"))
    mock.get(f"/league/{LEAGUE_ID}/rosters").respond(json=load("sleeper_rosters.json"))
    mock.get(f"/league/{LEAGUE_ID}/users").respond(json=load("sleeper_users.json"))


@pytest.mark.asyncio
async def test_reset_optimizer_returns_five_options(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    assert result.roster_id == 7
    assert len(result.options) == 5
    assert result.options == sorted(result.options, key=lambda o: o.protected_value, reverse=True)


@pytest.mark.asyncio
async def test_reset_optimizer_rank1_swaps_empty(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    assert result.options[0].swaps_from_top == []


@pytest.mark.asyncio
async def test_reset_optimizer_value_at_risk_positive(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    assert result.options[0].value_at_risk > 0


@pytest.mark.asyncio
async def test_reset_optimizer_team_int_matches_me(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result_me = await reset_optimizer(ctx, team="me")

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result_7 = await reset_optimizer(ctx, team=7)

    assert result_me.roster_id == result_7.roster_id == 7
    assert result_me.options[0].protected_value == result_7.options[0].protected_value


@pytest.mark.asyncio
async def test_reset_optimizer_result_serializable(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    dumped = result.model_dump(mode="json")
    assert isinstance(dumped["options"], list)
    assert "protected" in dumped["options"][0]
    assert "swaps_from_top" in dumped["options"][0]
