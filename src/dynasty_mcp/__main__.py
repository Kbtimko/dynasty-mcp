from __future__ import annotations

import asyncio

from dynasty_mcp.cache import Cache
from dynasty_mcp.config import load_config
from dynasty_mcp.context import Context
from dynasty_mcp.server import build_server
from dynasty_mcp.sources.fantasycalc import FantasyCalcClient
from dynasty_mcp.sources.sleeper import SleeperClient


async def _resolve_league_id(sleeper: SleeperClient, username: str, season: str) -> str:
    user = await sleeper.get_user(username)
    leagues = await sleeper.get_user_leagues(user["user_id"], season)
    if len(leagues) == 1:
        return leagues[0]["league_id"]
    names = ", ".join(f"{l['league_id']}:{l['name']}" for l in leagues)
    raise SystemExit(
        f"Ambiguous league for {username!r} (found {len(leagues)}). "
        f"Set sleeper.league_id in config. Options: {names}"
    )


def main() -> None:
    config = load_config()
    cache = Cache.open(config.cache_path)
    sleeper = SleeperClient(cache=cache, refresh_days=config.players_refresh_days)
    fantasycalc = FantasyCalcClient(cache=cache, refresh_hours=config.values_refresh_hours)

    state = asyncio.run(sleeper.get_state())
    season = str(state.get("season") or "2025")
    league_id = config.sleeper_league_id or asyncio.run(
        _resolve_league_id(sleeper, config.sleeper_username, season)
    )

    ctx = Context(
        cache=cache, sleeper=sleeper, fantasycalc=fantasycalc,
        username=config.sleeper_username, league_id=league_id, season=season,
    )
    server = build_server(ctx)
    server.run()


if __name__ == "__main__":
    main()
