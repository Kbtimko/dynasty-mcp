from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from dynasty_mcp.context import Context


class RefreshResult(BaseModel):
    refreshed: list[str]


async def refresh_cache(
    ctx: Context, *, what: Literal["players", "values", "all"] = "all"
) -> RefreshResult:
    refreshed: list[str] = []
    if what in ("players", "all"):
        await ctx.sleeper.get_players(force=True)
        refreshed.append("players")
    if what in ("values", "all"):
        if not ctx.league_id:
            raise ValueError("league_id required to refresh values")
        league = await ctx.sleeper.get_league(ctx.league_id)
        await ctx.fantasycalc.get_current(league, force=True)
        refreshed.append("values")
    return RefreshResult(refreshed=refreshed)
