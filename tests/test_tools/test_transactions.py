import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.transactions import get_transactions

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="alice", league_id="L1")


@pytest.mark.asyncio
async def test_get_transactions(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sleeper_mock:
        sleeper_mock.get("/state/nfl").respond(json=load("sleeper_state.json"))
        sleeper_mock.get(url__regex=r"/league/L1/transactions/\d+").respond(
            json=load("sleeper_transactions_week7.json")
        )
        out = await get_transactions(ctx, days=14)

    assert isinstance(out, list)
    for tx in out:
        assert "type" in tx
        assert "status" in tx
