import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.league import get_league_context

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
async def test_get_league_context_shape(tmp_path: Path) -> None:
    cache = Cache.open(tmp_path / "c.db")
    # The sleeper_users.json fixture has no `username` field — only `display_name`.
    # _resolve_your_roster_id falls back to display_name matching, so we use
    # "dakeif" (which appears as display_name in the fixture, roster_id=7).
    ctx = build_test_context(
        cache=cache, username="dakeif", league_id="L1", season="2025"
    )
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
        mock.get("/state/nfl").respond(json=load("sleeper_state.json"))

        result = await get_league_context(ctx)

    assert result.league_id == "L1"
    assert result.num_qbs in (1, 2)
    assert result.taxi_slots >= 0
    assert "QB" in result.roster_slots
    assert result.your_roster_id  # nonzero
    assert result.season_phase in ("pre", "regular", "post", "offseason")
