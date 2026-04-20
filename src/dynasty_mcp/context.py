from __future__ import annotations

from dataclasses import dataclass

from dynasty_mcp.cache import Cache
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient
from dynasty_mcp.sources.sleeper import SleeperClient


@dataclass
class Context:
    cache: Cache
    sleeper: SleeperClient
    fantasycalc: FantasyCalcClient
    username: str
    league_id: str | None
    season: str


def build_test_context(
    *,
    cache: Cache,
    username: str,
    league_id: str | None,
    season: str = "2025",
) -> Context:
    return Context(
        cache=cache,
        sleeper=SleeperClient(cache=cache, refresh_days=7),
        fantasycalc=FantasyCalcClient(cache=cache, refresh_hours=24),
        username=username,
        league_id=league_id,
        season=season,
    )
