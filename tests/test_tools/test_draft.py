import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.draft import get_draft

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="dakeif", league_id="L1")


@pytest.mark.asyncio
async def test_get_draft_returns_picks_and_pool(ctx) -> None:
    drafts = load("sleeper_drafts.json")
    assert drafts, "need at least one draft in fixture"
    draft_id = drafts[0]["draft_id"]

    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fc_mock:
        sleeper_mock.get("/league/L1").respond(json=load("sleeper_league.json"))
        sleeper_mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
        sleeper_mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
        sleeper_mock.get("/league/L1/drafts").respond(json=load("sleeper_drafts.json"))
        sleeper_mock.get("/league/L1/traded_picks").respond(
            json=load("sleeper_traded_picks.json")
        )
        sleeper_mock.get(f"/draft/{draft_id}").respond(json=load("sleeper_draft.json"))
        sleeper_mock.get(f"/draft/{draft_id}/picks").respond(
            json=load("sleeper_draft_picks.json")
        )
        sleeper_mock.get("/players/nfl").respond(json=load("sleeper_players.json"))
        fc_mock.get("/values/current").respond(json=load("fantasycalc_values.json"))

        result = await get_draft(ctx)

    assert result.draft_id == draft_id
    assert result.status in ("pre_draft", "drafting", "completed")
    assert isinstance(result.my_picks, list)
    assert isinstance(result.rookie_pool, list)
