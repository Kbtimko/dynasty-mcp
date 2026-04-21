from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context

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
    mock.get(f"/league/{LEAGUE_ID}/traded_picks").respond(json=load("sleeper_traded_picks.json"))


@pytest.mark.asyncio
async def test_reset_trades_result_schema(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, min_edge=0, top_n=5)

    assert isinstance(result.proposals, list)
    assert isinstance(result.considered_partners, list)
    assert isinstance(result.notes, list)
    assert len(result.considered_partners) == 13  # 14 teams minus me


@pytest.mark.asyncio
async def test_reset_trades_partner_arg_narrows_partners(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=5)

    assert result.considered_partners == [1]


@pytest.mark.asyncio
async def test_reset_trades_high_min_edge_empties_proposals(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=9_999_999, top_n=5)

    assert result.proposals == []


@pytest.mark.asyncio
async def test_reset_trades_proposals_satisfy_mutual_gain_filter(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=20)

    for p in result.proposals:
        assert p.my_net_edge >= 0
        assert p.partner_net_edge >= 0


@pytest.mark.asyncio
async def test_reset_trades_proposals_sorted_by_my_net_edge(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=20)

    edges = [p.my_net_edge for p in result.proposals]
    assert edges == sorted(edges, reverse=True)


@pytest.mark.asyncio
async def test_reset_trades_result_serializable(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=5)

    dumped = result.model_dump(mode="json")
    assert "proposals" in dumped
    assert "considered_partners" in dumped
    assert "notes" in dumped
