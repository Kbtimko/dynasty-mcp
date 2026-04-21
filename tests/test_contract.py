"""
Live contract test. Skipped unless DYNASTY_LIVE=1 is set.

Run:
    DYNASTY_LIVE=1 .venv/bin/pytest tests/test_contract.py -v -s

Verifies that the real Sleeper + FantasyCalc APIs still match our client assumptions
by running get_league_context and get_roster against the user's real league.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.league import get_league_context
from dynasty_mcp.tools.rosters import get_roster

pytestmark = pytest.mark.skipif(
    os.environ.get("DYNASTY_LIVE") != "1",
    reason="live contract test — opt in with DYNASTY_LIVE=1",
)


@pytest.mark.asyncio
async def test_live_league_context(tmp_path: Path) -> None:
    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    result = await get_league_context(ctx)
    assert result.league_id == league_id
    assert result.num_teams >= 2


@pytest.mark.asyncio
async def test_live_my_roster_returns_players(tmp_path: Path) -> None:
    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    view = await get_roster(ctx, team="me")
    assert view.entries


@pytest.mark.asyncio
async def test_live_reset_optimizer_returns_options(tmp_path: Path) -> None:
    from dynasty_mcp.tools.reset_optimizer import reset_optimizer

    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    result = await reset_optimizer(ctx)
    assert result.options, "expected at least one slate option"
    assert result.options[0].protected_value > 0
    assert result.options == sorted(result.options, key=lambda o: o.protected_value, reverse=True)
    result.model_dump(mode="json")


@pytest.mark.asyncio
async def test_live_reset_trades_returns_result(tmp_path: Path) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    result = await reset_trades(ctx, partner=1, min_edge=0, top_n=5)
    assert isinstance(result.proposals, list)
    assert result.considered_partners == [1]
    result.model_dump(mode="json")
