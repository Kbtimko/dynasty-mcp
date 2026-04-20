from pathlib import Path

import pytest

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import Context
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient
from dynasty_mcp.sources.sleeper import SleeperClient
from dynasty_mcp.server import build_server


@pytest.mark.asyncio
async def test_server_registers_expected_tools(tmp_path: Path) -> None:
    cache = Cache.open(tmp_path / "c.db")
    ctx = Context(
        cache=cache,
        sleeper=SleeperClient(cache=cache),
        fantasycalc=FantasyCalcClient(cache=cache),
        username="alice",
        league_id="L1",
        season="2025",
    )
    server = build_server(ctx)
    # FastMCP 2.x/3.x: list_tools() is async
    tools = await server.list_tools()
    names = {t.name for t in tools}
    expected = {
        "get_league_context",
        "get_roster",
        "list_rosters",
        "get_team_value_breakdown",
        "get_player_values",
        "get_matchup",
        "get_free_agents",
        "get_trending",
        "get_transactions",
        "get_draft",
        "refresh_cache",
    }
    assert expected <= names
